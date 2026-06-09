import os
import sys
import tempfile
import time
import socket
import webbrowser
from datetime import datetime, timezone
import qrcode
import httpx
from io import BytesIO

from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from watermark_app.config import cargar_config, Config
from watermark_app.database import Database
from watermark_app.marker_image import marcar_y_hashear, extraer_fingerprint_hex, generar_fingerprint, _fingerprint_a_hex
from watermark_app.marker_video import marcar_video_y_hashear, extraer_fingerprint_video
from watermark_app.payload import generar_id_unico
from watermark_app.sync import SyncClient
from watermark_app.version import __version__

GUI_DIR = None
STATIC_DIR = None
PROJECT_ROOT = None


def _to_local(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local = dt.astimezone()
        return local.strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        return iso_str[:19] if iso_str else ""


def _init_paths():
    global GUI_DIR, STATIC_DIR, PROJECT_ROOT
    if getattr(sys, 'frozen', False):
        GUI_DIR = os.path.join(sys._MEIPASS, 'watermark_app', 'gui')
        PROJECT_ROOT = os.path.dirname(sys._MEIPASS)
    else:
        GUI_DIR = os.path.join(os.path.dirname(__file__), "gui")
        PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    STATIC_DIR = GUI_DIR

_init_paths()

app = FastAPI(title="Watermark App")
active_ws: list[WebSocket] = []
_current_config: Config | None = None
_uvicorn_server = None


def _get_config():
    global _current_config
    if _current_config is None:
        from dotenv import load_dotenv
        env_path = os.path.join(PROJECT_ROOT, ".env")
        load_dotenv(env_path, override=True)
        _current_config = cargar_config()
        _current_config.db_path = os.path.join(PROJECT_ROOT, _current_config.db_path)
        if not _current_config.output_dir:
            _current_config.output_dir = os.path.join(os.path.expanduser("~"), "Watermark")
    return _current_config


def _get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


async def _broadcast(msg):
    for ws in active_ws:
        try:
            await ws.send_json(msg)
        except Exception:
            pass


@app.get("/")
async def index():
    html_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(html_path):
        return HTMLResponse(open(html_path, encoding="utf-8").read())
    return HTMLResponse("<h1>GUI not found</h1>", status_code=404)


@app.get("/api/qr")
async def qr_code(port: int = 8765):
    ip = _get_local_ip()
    url = f"http://{ip}:{port}"
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#e0e0e0", back_color="#1a1a2e")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


@app.get("/api/config")
async def get_config():
    cfg = _get_config()
    return {
        "scaling_w": cfg.vs_scaling_w,
        "video_frame_step": cfg.video_frame_step,
        "server_url": cfg.server_url,
        "api_key": cfg.api_key,
        "output_dir": cfg.output_dir or os.path.join(PROJECT_ROOT, "watermarked"),
        "local_ip": _get_local_ip(),
    }


@app.post("/api/config")
async def save_config(data: dict):
    global _current_config
    try:
        cfg = _get_config()
        env_path = os.path.join(PROJECT_ROOT, ".env")
        env_lines = []
        if os.path.exists(env_path):
            env_lines = open(env_path, encoding="utf-8").readlines()

        updates = {}
        if "scaling_w" in data:
            cfg.vs_scaling_w = float(data["scaling_w"])
            updates["WATERMARK_VS_SCALING_W"] = data["scaling_w"]
        if "video_frame_step" in data:
            cfg.video_frame_step = int(data["video_frame_step"])
            updates["WATERMARK_VIDEO_FRAME_STEP"] = data["video_frame_step"]
        if "server_url" in data:
            cfg.server_url = data["server_url"]
            updates["WATERMARK_SERVER_URL"] = data["server_url"]
        if "api_key" in data:
            cfg.api_key = data["api_key"]
            updates["WATERMARK_API_KEY"] = data["api_key"]
        if "output_dir" in data:
            cfg.output_dir = data["output_dir"]
            updates["WATERMARK_OUTPUT_DIR"] = data["output_dir"]

        new_lines = []
        written = set()
        for line in env_lines:
            stripped = line.strip()
            found = False
            for key, val in updates.items():
                if stripped.startswith(f"{key}="):
                    new_lines.append(f"{key}={val}\n")
                    written.add(key)
                    found = True
                    break
            if not found:
                new_lines.append(line)
        for key, val in updates.items():
            if key not in written:
                new_lines.append(f"{key}={val}\n")

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        return {"status": "ok"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.post("/api/mark")
async def mark_files(
    files: list[UploadFile] = File(...),
    id_unico: str = Form(""),
    vendido_a: str = Form(""),
    scaling_w: float = Form(0.3),
    video_step: int = Form(30),
    output_dir: str = Form(""),
):
    cfg = _get_config()
    db = Database(cfg.db_path)
    id_unico = id_unico or generar_id_unico()
    output_dir = output_dir or cfg.output_dir or os.path.join(PROJECT_ROOT, "watermarked")
    os.makedirs(output_dir, exist_ok=True)

    results = []
    total = len(files)
    start_time = time.time()

    await _broadcast({"type": "start", "total": total})

    for i, f in enumerate(files):
        file_start = time.time()
        ext = os.path.splitext(f.filename or "")[1].lower()
        is_video = ext in (".mp4", ".mov", ".avi", ".mkv", ".webm")

        tmp_path = None
        try:
            await _broadcast({"type": "progress", "current": i, "total": total,
                            "file": f.filename, "status": "preparing"})

            suffix = ext or ".png"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(await f.read())
                tmp_path = tmp.name

            await _broadcast({"type": "progress", "current": i, "total": total,
                            "file": f.filename, "status": "marking"})

            fp = generar_fingerprint()

            if is_video:
                result = marcar_video_y_hashear(
                    ruta_entrada=tmp_path,
                    fingerprint=fp,
                    output_dir=output_dir,
                    model_name=cfg.vs_model,
                    scaling_w=scaling_w,
                    frame_step=video_step,
                )
                tipo = "video"
            else:
                result = marcar_y_hashear(
                    ruta_entrada=tmp_path,
                    fingerprint=fp,
                    output_dir=output_dir,
                    model_name=cfg.vs_model,
                    scaling_w=scaling_w,
                )
                tipo = "imagen"

            db.registrar_marcado(
                id_unico=id_unico,
                fingerprint=result["fingerprint_hex"],
                ruta_original=f.filename or tmp_path,
                ruta_marcada=result["ruta_marcada"],
                phash=result["phash"],
                dhash=result["dhash"],
                tipo=tipo,
                vendido_a=vendido_a,
            )

            elapsed = time.time() - file_start
            results.append({"file": f.filename, "status": "ok", "time": round(elapsed, 1)})
            await _broadcast({
                "type": "progress",
                "current": i + 1,
                "total": total,
                "file": f.filename,
                "status": "ok",
                "time": round(elapsed, 1),
            })

        except Exception as e:
            import traceback
            print(f"ERROR marking {f.filename}: {e}")
            traceback.print_exc()
            results.append({"file": f.filename, "status": "error", "error": str(e)})
            await _broadcast({
                "type": "progress",
                "current": i + 1,
                "total": total,
                "file": f.filename,
                "status": "error",
                "error": str(e),
            })
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    total_time = time.time() - start_time
    await _broadcast({"type": "done", "results": results, "total_time": round(total_time, 1)})

    if cfg.api_key and cfg.server_url:
        try:
            client = SyncClient(cfg.server_url, cfg.api_key, db)
            synced = await client.sync_pendientes()
        except Exception:
            synced = 0
    else:
        synced = 0

    return {
        "id_unico": id_unico,
        "results": results,
        "total_time": round(total_time, 1),
        "synced": synced,
        "output_dir": output_dir,
    }


@app.post("/api/read")
async def read_file(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    is_video = ext in (".mp4", ".mov", ".avi", ".mkv", ".webm")

    tmp_path = None
    try:
        suffix = ext or ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        if is_video:
            fp = extraer_fingerprint_video(tmp_path)
            fp_hex = _fingerprint_a_hex(fp)
        else:
            fp_hex = extraer_fingerprint_hex(tmp_path)

        db = Database(_get_config().db_path)
        local_results = db.buscar_por_fingerprint(fp_hex, limite=5)

        best_local_dist = local_results[0]["_distancia"] if local_results else 999
        matches = [
            {
                "id_unico": r["id_unico"],
                "vendido_a": r.get("vendido_a") or "",
                "fecha_marcado": _to_local(r["fecha_marcado"]),
                "tipo": r["tipo"],
                "distancia": r["_distancia"],
                "ruta_original": r["ruta_original"],
                "origen": "local",
            }
            for r in local_results
        ]

        remote_results = []
        cfg = _get_config()
        if cfg.api_key and cfg.server_url and best_local_dist > 80:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(
                        f"{cfg.server_url.rstrip('/')}/api/watermark/fingerprint",
                        params={"fp": fp_hex, "limit": "5"},
                        headers={"X-API-Key": cfg.api_key},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("found") and data.get("results"):
                            for r in data["results"]:
                                remote_results.append({
                                    "id_unico": r.get("id_unico", ""),
                                    "vendido_a": r.get("vendido_a") or "",
                                    "fecha_marcado": _to_local(r.get("fecha_marcado", "")),
                                    "tipo": r.get("tipo", "imagen"),
                                    "distancia": r.get("distancia", 999),
                                    "ruta_original": "",
                                    "origen": "servidor",
                                })
            except Exception:
                pass

        matches.extend(remote_results)
        matches.sort(key=lambda m: m["distancia"])

        return {
            "fingerprint": fp_hex,
            "matches": matches,
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.get("/api/history")
async def get_history(id: str = "", vendido: str = "", limit: int = 100):
    db = Database(_get_config().db_path)
    if id:
        items = db.buscar_por_id(id)
    elif vendido:
        items = db.buscar_por_vendido(vendido)
    else:
        items = db.get_historial(limit)

    return {
        "items": [
            {
                "id": r["id"],
                "id_unico": r["id_unico"],
                "fingerprint": r["fingerprint"],
                "tipo": r["tipo"],
                "vendido_a": r.get("vendido_a") or "",
                "fecha_marcado": _to_local(r["fecha_marcado"]),
                "sync_status": r["sync_status"],
                "ruta_original": r["ruta_original"],
                "ruta_marcada": r["ruta_marcada"],
            }
            for r in items
        ]
    }


@app.get("/api/stats")
async def get_stats():
    db = Database(_get_config().db_path)
    return db.get_stats()


@app.get("/api/export")
async def export_data(format: str = "json"):
    import csv
    import json as json_mod

    db = Database(_get_config().db_path)
    items = db.get_historial(100000)

    if format == "csv":
        buf = BytesIO()
        if items:
            writer = csv.DictWriter(buf, fieldnames=items[0].keys())
            writer.writeheader()
            writer.writerows(items)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=watermarks.csv"},
        )
    else:
        data = json_mod.dumps(items, ensure_ascii=False, indent=2, default=str)
        return JSONResponse(json_mod.loads(data))


@app.websocket("/ws/progress")
async def ws_progress(ws: WebSocket):
    await ws.accept()
    active_ws.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        active_ws.remove(ws)


@app.post("/api/sync")
async def force_sync():
    cfg = _get_config()
    if not cfg.api_key or not cfg.server_url:
        return JSONResponse({"error": "Servidor o API key no configurados"}, status_code=400)
    db = Database(cfg.db_path)
    client = SyncClient(cfg.server_url, cfg.api_key, db)
    synced = await client.sync_pendientes()
    return {"synced": synced}


@app.post("/api/open-folder")
async def open_folder(data: dict):
    path = data.get("path", "")
    if not path or not os.path.isdir(path):
        return JSONResponse({"error": "Carpeta no encontrada"}, status_code=400)
    try:
        import subprocess
        import platform
        if platform.system() == "Windows":
            subprocess.run(["explorer", path])
        elif platform.system() == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.get("/api/version")
async def get_version():
    return {"version": __version__}


@app.post("/api/shutdown")
async def shutdown():
    global _uvicorn_server
    if _uvicorn_server:
        _uvicorn_server.should_exit = True
    return {"status": "shutting_down"}


@app.get("/api/check-update")
async def check_update():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                "https://api.github.com/repos/chilagranate/watermark/releases/latest",
                headers={"Accept": "application/vnd.github+json"},
            )
            if r.status_code == 200:
                data = r.json()
                latest = data.get("tag_name", "").lstrip("v")
                if latest and latest != __version__:
                    return {
                        "update_available": True,
                        "current": __version__,
                        "latest": latest,
                        "url": data.get("html_url", ""),
                    }
    except Exception:
        pass
    return {"update_available": False, "current": __version__}


if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


async def iniciar_servidor(host: str = "0.0.0.0", port: int = 8765):
    try:
        ip = _get_local_ip()
        url = f"http://{ip}:{port}"
        print(f"\n{'='*50}")
        print(f"  Watermark App v{__version__}")
        print(f"  Abrí en el navegador: {url}")
        print(f"  Para salir: cerrá esta ventana o Ctrl+C")
        print(f"{'='*50}\n")

        from watermark_app.marker_image import _cargar_modelo
        cfg = _get_config()
        print("  Cargando modelo VideoSeal...")
        _cargar_modelo(cfg.vs_model, cfg.vs_scaling_w)
        print("  Modelo cargado. Servidor iniciado.\n")

        webbrowser.open(f"http://localhost:{port}")

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(
                    "https://api.github.com/repos/chilagranate/watermark/releases/latest",
                    headers={"Accept": "application/vnd.github+json"},
                )
                if r.status_code == 200:
                    latest = r.json().get("tag_name", "").lstrip("v")
                    if latest and latest != __version__:
                        print(f"  [UPDATE] v{latest} disponible en GitHub Releases\n")
        except Exception:
            pass

        print()
        config = uvicorn.Config(app, host=host, port=port, log_level="warning")
        server = uvicorn.Server(config)
        global _uvicorn_server
        _uvicorn_server = server
        await server.serve()
        _uvicorn_server = None
    except Exception as e:
        import traceback
        log_path = os.path.join(os.path.expanduser("~"), "watermark_error.log")
        with open(log_path, "w") as f:
            f.write(f"Error starting Watermark App:\n{traceback.format_exc()}\n")
        print(f"\nERROR: {e}")
        print(f"Details written to: {log_path}")
        traceback.print_exc()


if __name__ == "__main__":
    import asyncio
    asyncio.run(iniciar_servidor())
