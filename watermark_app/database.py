import os
import sqlite3
import threading
from datetime import datetime, timezone


class Database:
    def __init__(self, db_path: str = "data/watermarks.db"):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._inicializar()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _inicializar(self):
        with self._lock:
            conn = self._get_conn()
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS archivos_marcados (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    id_unico TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    ruta_original TEXT NOT NULL,
                    ruta_marcada TEXT,
                    phash TEXT NOT NULL,
                    dhash TEXT NOT NULL,
                    tipo TEXT NOT NULL DEFAULT 'imagen',
                    vendido_a TEXT,
                    fecha_marcado TIMESTAMP NOT NULL,
                    sync_status TEXT NOT NULL DEFAULT 'pending',
                    intentos_sync INTEGER DEFAULT 0,
                    ultimo_intento_sync TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_marcados_id_unico
                    ON archivos_marcados(id_unico);
                CREATE INDEX IF NOT EXISTS idx_marcados_fingerprint
                    ON archivos_marcados(fingerprint);
                CREATE INDEX IF NOT EXISTS idx_marcados_sync
                    ON archivos_marcados(sync_status);
                CREATE INDEX IF NOT EXISTS idx_marcados_vendido
                    ON archivos_marcados(vendido_a);
                CREATE INDEX IF NOT EXISTS idx_marcados_fecha
                    ON archivos_marcados(fecha_marcado);
            """)
            conn.commit()
            conn.close()

    def registrar_marcado(self, id_unico: str, fingerprint: str,
                          ruta_original: str, ruta_marcada: str,
                          phash: str, dhash: str,
                          tipo: str = "imagen", vendido_a: str = "") -> int:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute("""
                INSERT INTO archivos_marcados
                    (id_unico, fingerprint, ruta_original, ruta_marcada,
                     phash, dhash, tipo, vendido_a, fecha_marcado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                id_unico, fingerprint, ruta_original, ruta_marcada,
                phash, dhash, tipo,
                vendido_a if vendido_a else None,
                datetime.now(timezone.utc).isoformat(),
            ))
            conn.commit()
            row_id = cursor.lastrowid
            conn.close()
            return row_id

    def buscar_por_fingerprint(self, fingerprint_str: str,
                                limite: int = 5) -> list[dict]:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT * FROM archivos_marcados ORDER BY fecha_marcado DESC"
            )
            rows = cursor.fetchall()
            conn.close()

            results = []
            for row in rows:
                item = dict(row)
                dist = _hamming_hex(item["fingerprint"], fingerprint_str)
                item["_distancia"] = dist
                results.append(item)

            results.sort(key=lambda x: x["_distancia"])
            return results[:limite]

    def get_pendientes_sync(self, limite: int = 50) -> list[dict]:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute("""
                SELECT * FROM archivos_marcados
                WHERE sync_status = 'pending'
                ORDER BY fecha_marcado ASC
                LIMIT ?
            """, (limite,))
            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]

    def marcar_sync_ok(self, row_id: int):
        with self._lock:
            conn = self._get_conn()
            conn.execute("""
                UPDATE archivos_marcados
                SET sync_status = 'synced', ultimo_intento_sync = ?
                WHERE id = ?
            """, (datetime.now(timezone.utc).isoformat(), row_id))
            conn.commit()
            conn.close()

    def marcar_sync_error(self, row_id: int):
        with self._lock:
            conn = self._get_conn()
            conn.execute("""
                UPDATE archivos_marcados
                SET intentos_sync = intentos_sync + 1,
                    ultimo_intento_sync = ?,
                    sync_status = CASE WHEN intentos_sync >= 10 THEN 'failed' ELSE 'pending' END
                WHERE id = ?
            """, (datetime.now(timezone.utc).isoformat(), row_id))
            conn.commit()
            conn.close()

    def buscar_por_id(self, id_unico: str) -> list[dict]:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute("""
                SELECT * FROM archivos_marcados
                WHERE id_unico LIKE ?
                ORDER BY fecha_marcado DESC
            """, (f"%{id_unico}%",))
            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]

    def buscar_por_vendido(self, nombre: str) -> list[dict]:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute("""
                SELECT * FROM archivos_marcados
                WHERE vendido_a LIKE ?
                ORDER BY fecha_marcado DESC
            """, (f"%{nombre}%",))
            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]

    def get_historial(self, limite: int = 50) -> list[dict]:
        with self._lock:
            conn = self._get_conn()
            cursor = conn.execute("""
                SELECT * FROM archivos_marcados
                ORDER BY fecha_marcado DESC
                LIMIT ?
            """, (limite,))
            rows = cursor.fetchall()
            conn.close()
            return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        with self._lock:
            conn = self._get_conn()
            stats = {}
            stats["total"] = conn.execute(
                "SELECT COUNT(*) FROM archivos_marcados").fetchone()[0]
            stats["pendientes_sync"] = conn.execute(
                "SELECT COUNT(*) FROM archivos_marcados WHERE sync_status = 'pending'"
            ).fetchone()[0]
            stats["synced"] = conn.execute(
                "SELECT COUNT(*) FROM archivos_marcados WHERE sync_status = 'synced'"
            ).fetchone()[0]
            stats["failed"] = conn.execute(
                "SELECT COUNT(*) FROM archivos_marcados WHERE sync_status = 'failed'"
            ).fetchone()[0]
            stats["imagenes"] = conn.execute(
                "SELECT COUNT(*) FROM archivos_marcados WHERE tipo = 'imagen'"
            ).fetchone()[0]
            stats["videos"] = conn.execute(
                "SELECT COUNT(*) FROM archivos_marcados WHERE tipo = 'video'"
            ).fetchone()[0]
            conn.close()
            return stats


def _hamming_hex(h1: str, h2: str) -> int:
    if len(h1) != len(h2):
        m = max(len(h1), len(h2))
        h1 = h1.zfill(m)
        h2 = h2.zfill(m)
    return sum(bin(int(a, 16) ^ int(b, 16)).count("1")
               for a, b in zip(h1, h2))
