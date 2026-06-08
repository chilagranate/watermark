import asyncio

import httpx

from watermark_app.database import Database


class SyncClient:
    def __init__(self, server_url: str, api_key: str, db: Database):
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.db = db

    async def upload_watermark(self, id_unico: str, fingerprint: str,
                               phash: str, dhash: str,
                               fecha_marcado: str, tipo: str = "imagen",
                               vendido_a: str = "") -> bool:
        headers = {"X-API-Key": self.api_key}
        body = {
            "id_unico": id_unico,
            "fingerprint": fingerprint,
            "phash": phash,
            "dhash": dhash,
            "fecha_marcado": fecha_marcado,
            "tipo": tipo,
        }
        if vendido_a:
            body["vendido_a"] = vendido_a

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.server_url}/api/watermark/upload",
                    json=body,
                    headers=headers,
                )
                return resp.status_code in (200, 201)
        except Exception:
            return False

    async def sync_pendientes(self) -> int:
        pendientes = self.db.get_pendientes_sync()
        synced = 0

        for p in pendientes:
            ok = await self.upload_watermark(
                id_unico=p["id_unico"],
                fingerprint=p["fingerprint"],
                phash=p["phash"],
                dhash=p["dhash"],
                fecha_marcado=p["fecha_marcado"],
                tipo=p["tipo"],
                vendido_a=p.get("vendido_a") or "",
            )
            if ok:
                self.db.marcar_sync_ok(p["id"])
                synced += 1
            else:
                self.db.marcar_sync_error(p["id"])

        return synced
