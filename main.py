import argparse
import asyncio
import glob as glob_mod
import os
import sys
from datetime import datetime, timezone

from watermark_app.config import cargar_config
from watermark_app.database import Database
from watermark_app.payload import generar_id_unico
from watermark_app.marker_image import (
    marcar_y_hashear, extraer_fingerprint_hex, generar_fingerprint,
    _fingerprint_a_hex,
)
from watermark_app.marker_video import marcar_video_y_hashear, extraer_fingerprint_video
from watermark_app.hasher import distancia_hamming
from watermark_app.sync import SyncClient


def cmd_mark(args):
    config = cargar_config()
    db = Database(config.db_path)

    if args.server:
        config.server_url = args.server
    if args.api_key:
        config.api_key = args.api_key

    id_unico = args.id or generar_id_unico()
    vendido_a = args.vendido_a or ""
    output_dir = args.output or config.output_dir or ""
    frame_step = args.video_step if args.video_step is not None else config.video_frame_step

    patrones = args.files
    archivos = []

    for patron in patrones:
        if os.path.isfile(patron):
            archivos.append(patron)
        elif os.path.isdir(patron):
            for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp", "*.tiff",
                        "*.mp4", "*.mov", "*.avi", "*.mkv", "*.webm"):
                archivos.extend(glob_mod.glob(
                    os.path.join(patron, "**", ext), recursive=True))
        else:
            expandidos = glob_mod.glob(patron, recursive=True)
            if expandidos:
                archivos.extend(expandidos)
            else:
                print(f"  [WARN] No se encontraron archivos: {patron}")

    if not archivos:
        print("ERROR: No se encontraron archivos para marcar.")
        print("  Uso: python main.py mark --id WM001 --files foto.jpg")
        sys.exit(1)

    imagenes = [f for f in archivos
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"))]
    videos = [f for f in archivos
              if f.lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".webm"))]

    total = len(imagenes) + len(videos)

    print(f"ID: {id_unico}")
    print(f"Vendido a: {vendido_a or '(contenido publico)'}")
    print(f"Modelo: {config.vs_model}  (scaling_w={config.vs_scaling_w})")
    if videos:
        print(f"Video cada {frame_step} frames")
    print(f"Archivos: {len(imagenes)} imagenes + {len(videos)} videos")
    if output_dir:
        print(f"Output: {output_dir}")
    print()

    exitosos = 0
    fallidos = 0
    idx = 0

    for ruta in imagenes:
        idx += 1
        nombre = os.path.basename(ruta)
        print(f"[{idx}/{total}] {nombre}...", end=" ", flush=True)

        try:
            fp = generar_fingerprint()
            resultado = marcar_y_hashear(
                ruta_entrada=ruta,
                fingerprint=fp,
                output_dir=output_dir,
                model_name=config.vs_model,
                scaling_w=config.vs_scaling_w,
            )

            db.registrar_marcado(
                id_unico=id_unico,
                fingerprint=resultado["fingerprint_hex"],
                ruta_original=resultado["ruta_original"],
                ruta_marcada=resultado["ruta_marcada"],
                phash=resultado["phash"],
                dhash=resultado["dhash"],
                tipo="imagen",
                vendido_a=vendido_a,
            )

            print(f"[OK] {resultado['ruta_marcada']}")
            exitosos += 1
        except Exception as e:
            print(f"[FAIL] {e}")
            fallidos += 1

    for ruta in videos:
        idx += 1
        nombre = os.path.basename(ruta)
        print(f"[{idx}/{total}] [VIDEO] {nombre}...", end=" ", flush=True)

        try:
            fp = generar_fingerprint()
            resultado = marcar_video_y_hashear(
                ruta_entrada=ruta,
                fingerprint=fp,
                output_dir=output_dir,
                model_name=config.vs_model,
                scaling_w=config.vs_scaling_w,
                frame_step=frame_step,
            )

            db.registrar_marcado(
                id_unico=id_unico,
                fingerprint=resultado["fingerprint_hex"],
                ruta_original=resultado["ruta_original"],
                ruta_marcada=resultado["ruta_marcada"],
                phash=resultado["phash"],
                dhash=resultado["dhash"],
                tipo="video",
                vendido_a=vendido_a,
            )

            print(f"[OK] {resultado['ruta_marcada']}")
            exitosos += 1
        except Exception as e:
            print(f"[FAIL] {e}")
            fallidos += 1

    print(f"\n[OK] {exitosos} marcados | [FAIL] {fallidos} fallidos")

    if config.api_key and config.server_url:
        print(f"\nSincronizando con {config.server_url}...")
        client = SyncClient(config.server_url, config.api_key, db)
        synced = asyncio.run(client.sync_pendientes())
        print(f"  [OK] {synced} sincronizados")


def cmd_read(args):
    config = cargar_config()
    db = Database(config.db_path)

    archivo = args.file
    if not os.path.isfile(archivo):
        print(f"ERROR: Archivo no encontrado: {archivo}")
        sys.exit(1)

    print(f"Extrayendo fingerprint de: {archivo}")

    is_video = archivo.lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".webm"))

    try:
        if is_video:
            fp = extraer_fingerprint_video(archivo)
            fp_hex = _fingerprint_a_hex(fp)
        else:
            fp_hex = extraer_fingerprint_hex(archivo)
    except Exception as e:
        print(f"ERROR al extraer: {e}")
        print("La imagen podria no tener marca o estar muy degradada.")
        return

    print(f"Fingerprint extraido: {fp_hex[:32]}...")

    resultados = db.buscar_por_fingerprint(fp_hex, limite=3)

    if not resultados:
        print("\nNo se encontraron coincidencias en la DB local.")
        return

    print(f"\n{'Distancia':<12} {'ID Unico':<22} {'Vendido a':<15} {'Fecha'}")
    print("-" * 85)

    for r in resultados:
        dist = r["_distancia"]
        status = "IDENTIFICADO" if dist <= 60 else "POSIBLE" if dist <= 80 else "NO"
        print(f"{dist:<12} {r['id_unico']:<22} "
              f"{r['vendido_a'] or '':<15} "
              f"{r['fecha_marcado'][:19]}  [{status}]")

    best = resultados[0]
    print(f"\nMejor coincidencia: {best['id_unico']}")
    print(f"  Vendido a:     {best['vendido_a'] or '(contenido publico)'}")
    print(f"  Fecha marcado: {best['fecha_marcado'][:19]}")
    print(f"  Distancia:     {best['_distancia']} bits (de 256)")
    print(f"  Ruta original: {best['ruta_original']}")


def cmd_sync(args):
    config = cargar_config()
    db = Database(config.db_path)

    if args.server:
        config.server_url = args.server
    if args.api_key:
        config.api_key = args.api_key

    if not config.api_key:
        print("ERROR: API key no configurada. Usa --api-key o configura .env")
        sys.exit(1)

    if not config.server_url:
        print("ERROR: URL del servidor no configurada. Usa --server o configura .env")
        sys.exit(1)

    print(f"Sincronizando con {config.server_url}...")
    client = SyncClient(config.server_url, config.api_key, db)
    synced = client.sync_sync()
    print(f"  [OK] {synced} archivos sincronizados")


def cmd_history(args):
    config = cargar_config()
    db = Database(config.db_path)

    if args.id:
        items = db.buscar_por_id(args.id)
    elif args.vendido:
        items = db.buscar_por_vendido(args.vendido)
    else:
        items = db.get_historial(args.limite)

    if not items:
        print("No se encontraron registros.")
        return

    print(f"{'ID Unico':<22} {'Tipo':<8} {'Vendido a':<15} {'Sync':<10} {'Fecha'}")
    print("-" * 90)
    for item in items:
        print(f"{item['id_unico']:<22} {item['tipo']:<8} "
              f"{item['vendido_a'] or '':<15} {item['sync_status']:<10} "
              f"{item['fecha_marcado'][:19]}")


def cmd_stats(args):
    config = cargar_config()
    db = Database(config.db_path)
    stats = db.get_stats()

    print(f"Total marcados:     {stats['total']}")
    print(f"  Imagenes:         {stats['imagenes']}")
    print(f"  Videos:           {stats['videos']}")
    print(f"Sincronizados:      {stats['synced']}")
    print(f"Pendientes sync:    {stats['pendientes_sync']}")
    print(f"Fallidos sync:      {stats['failed']}")


def cmd_export(args):
    import csv
    import json

    config = cargar_config()
    db = Database(config.db_path)
    items = db.get_historial(10000)

    if not items:
        print("No hay registros para exportar.")
        return

    if args.formato == "csv" or args.output.endswith(".csv"):
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=items[0].keys())
            writer.writeheader()
            writer.writerows(items)
    else:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2, default=str)

    print(f"Exportados {len(items)} registros -> {args.output}")


def main():
    parser = argparse.ArgumentParser(
        description="Watermark App - Marcado digital invisible (VideoSeal)"
    )
    sub = parser.add_subparsers(dest="comando")

    p_mark = sub.add_parser("mark", help="Marcar archivos con fingerprint")
    p_mark.add_argument("--id", help="ID unico (se genera automatico si no se especifica)")
    p_mark.add_argument("--vendido-a", help="Nombre de la persona a quien se vendio")
    p_mark.add_argument("--output", "-o", help="Directorio de salida")
    p_mark.add_argument("--video-step", type=int, default=None,
                        help="Marcar 1 de cada N frames de video (default: 30)")
    p_mark.add_argument("--server", help="URL del servidor monitor")
    p_mark.add_argument("--api-key", help="API key del servidor")
    p_mark.add_argument("files", nargs="+", help="Archivos, carpetas o patrones glob")

    p_read = sub.add_parser("read", help="Leer fingerprint de una imagen y buscar en DB")
    p_read.add_argument("file", help="Archivo de imagen a leer")

    p_sync = sub.add_parser("sync", help="Sincronizar pendientes con el servidor")
    p_sync.add_argument("--server", help="URL del servidor monitor")
    p_sync.add_argument("--api-key", help="API key del servidor")

    p_history = sub.add_parser("history", help="Ver historial de marcados")
    p_history.add_argument("--id", help="Filtrar por ID unico")
    p_history.add_argument("--vendido", help="Filtrar por nombre de comprador")
    p_history.add_argument("--limite", "-n", type=int, default=50, help="Limite de resultados")

    p_stats = sub.add_parser("stats", help="Estadisticas locales")

    p_export = sub.add_parser("export", help="Exportar historial")
    p_export.add_argument("output", help="Archivo de salida (.csv o .json)")
    p_export.add_argument("--formato", choices=["csv", "json"], default="json")

    p_gui = sub.add_parser("gui", help="Iniciar interfaz web")
    p_gui.add_argument("--port", type=int, default=8765, help="Puerto (default: 8765)")
    p_gui.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")

    args = parser.parse_args()

    if args.comando == "mark":
        cmd_mark(args)
    elif args.comando == "read":
        cmd_read(args)
    elif args.comando == "sync":
        cmd_sync(args)
    elif args.comando == "history":
        cmd_history(args)
    elif args.comando == "stats":
        cmd_stats(args)
    elif args.comando == "export":
        cmd_export(args)
    elif args.comando == "gui":
        cmd_gui(args)
    else:
        parser.print_help()


def cmd_gui(args):
    import asyncio
    from watermark_app.server import iniciar_servidor
    asyncio.run(iniciar_servidor(host=args.host, port=args.port))


if __name__ == "__main__":
    main()
