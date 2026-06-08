import os
from PIL import Image
import numpy as np

from watermark_app.marker_image import (
    marcar_y_hashear, extraer_fingerprint, extraer_fingerprint_hex,
    generar_fingerprint, _fingerprint_a_hex, _hex_a_fingerprint,
)
from watermark_app.database import Database
from watermark_app.hasher import calcular_hashes, distancia_hamming


SRC = 'C:/eve-firmainvisible/tests/test_foto.png'
OUT = 'C:/eve-firmainvisible/tests'
os.makedirs(OUT, exist_ok=True)
os.makedirs(f'{OUT}/test_data', exist_ok=True)

if not os.path.exists(SRC):
    img = Image.new("RGB", (512, 512), color=(73, 109, 137))
    img.save(SRC)


def test_roundtrip_identification():
    """Fingerprint se recupera y matchea al comprador correcto."""
    db = Database()
    fp = generar_fingerprint()
    fp_hex = _fingerprint_a_hex(fp)
    result = marcar_y_hashear(SRC, fingerprint=fp, output_dir=f'{OUT}/test_data')
    db.registrar_marcado(
        id_unico='test_rt', fingerprint=result['fingerprint_hex'],
        ruta_original=SRC, ruta_marcada=result['ruta_marcada'],
        phash=result['phash'], dhash=result['dhash'],
        tipo='imagen', vendido_a='Test',
    )

    ext_fp = extraer_fingerprint(result['ruta_marcada'])
    ext_hex = _fingerprint_a_hex(ext_fp)

    results = db.buscar_por_fingerprint(ext_hex, limite=1)
    assert len(results) > 0, "No se encontro coincidencia"
    best = results[0]
    assert best['id_unico'] == 'test_rt', f"ID incorrecto: {best['id_unico']}"
    assert best['_distancia'] < 100, f"Distancia muy alta: {best['_distancia']}"


def test_multi_buyer_separation():
    """Tres compradores mismo contenido, fingerprints distinguibles."""
    db = Database()
    buyers = ['Luis_T', 'Maria_T', 'Carlos_T']
    fps = {}
    paths = {}

    for nombre in buyers:
        fp = generar_fingerprint()
        fps[nombre] = _fingerprint_a_hex(fp)
        result = marcar_y_hashear(SRC, fingerprint=fp, output_dir=f'{OUT}/test_data')
        paths[nombre] = result['ruta_marcada']
        db.registrar_marcado(
            id_unico=f'test_mb_{nombre}', fingerprint=result['fingerprint_hex'],
            ruta_original=SRC, ruta_marcada=result['ruta_marcada'],
            phash=result['phash'], dhash=result['dhash'],
            tipo='imagen', vendido_a=nombre,
        )

    for nombre in buyers:
        ext_hex = extraer_fingerprint_hex(paths[nombre])
        results = db.buscar_por_fingerprint(ext_hex, limite=3)
        best = results[0]
        assert best['vendido_a'] == nombre, \
            f"Esperaba {nombre}, obtuvo {best['vendido_a']} (dist={best['_distancia']})"

        if len(results) > 1:
            second = results[1]
            gap = second['_distancia'] - best['_distancia']
            assert gap > 20, \
                f"Separacion insuficiente entre {nombre} y {second['vendido_a']}: gap={gap}"


def test_screenshot_resilience():
    """Fingerprint sobrevive resize (simulacion de screenshot)."""
    fp = generar_fingerprint()
    result = marcar_y_hashear(SRC, fingerprint=fp, output_dir=f'{OUT}/test_data')
    fp_hex = result['fingerprint_hex']

    img = Image.open(result['ruta_marcada']).convert('RGB')
    w, h = img.size

    # Simulate screenshot: resize down then up
    img_ss = img.resize((w * 3 // 4, h * 3 // 4), Image.LANCZOS)
    img_ss = img_ss.resize((w, h), Image.LANCZOS)
    ss_path = f'{OUT}/test_data/screenshot_test.png'
    img_ss.save(ss_path)

    clean_dist = sum(1 for a, b in
                     zip(extraer_fingerprint(result['ruta_marcada']), fp) if abs(a - b) > 0.5)
    ss_dist = sum(1 for a, b in
                  zip(extraer_fingerprint(ss_path), fp) if abs(a - b) > 0.5)

    gap = abs(ss_dist - clean_dist)
    assert gap <= 15, \
        f"Screenshot degrada demasiado el fingerprint: gap={gap} (clean={clean_dist}, ss={ss_dist})"


def test_jpeg_stability():
    """Fingerprint sobrevive JPEG 95 con poca degradacion."""
    fp = generar_fingerprint()
    result = marcar_y_hashear(SRC, fingerprint=fp, output_dir=f'{OUT}/test_data')

    img = Image.open(result['ruta_marcada']).convert('RGB')
    jpg_path = f'{OUT}/test_data/jpeg95_test.jpg'
    img.save(jpg_path, 'JPEG', quality=95)

    clean_dist = sum(1 for a, b in
                     zip(extraer_fingerprint(result['ruta_marcada']), fp) if abs(a - b) > 0.5)
    jpg_dist = sum(1 for a, b in
                   zip(extraer_fingerprint(jpg_path), fp) if abs(a - b) > 0.5)

    gap = jpg_dist - clean_dist
    assert gap <= 30, \
        f"JPEG 95 degrada demasiado: gap={gap} (clean={clean_dist}, jpg={jpg_dist})"


def test_hash_stability():
    """pHash/dHash del original vs marcado tienen distancia baja."""
    result = marcar_y_hashear(SRC, fingerprint=generar_fingerprint(),
                               output_dir=f'{OUT}/test_data')
    img_orig = Image.open(SRC)
    ph_orig, dh_orig = calcular_hashes(img_orig)
    ph_wm, dh_wm = calcular_hashes(Image.open(result['ruta_marcada']))
    min_dist = min(distancia_hamming(ph_orig, ph_wm),
                   distancia_hamming(dh_orig, dh_wm))
    assert min_dist <= 25, f"Hash cambiado demasiado: min_dist={min_dist}"


if __name__ == "__main__":
    tests = [
        ("Roundtrip + identificacion", test_roundtrip_identification),
        ("Multi-comprador separacion", test_multi_buyer_separation),
        ("Screenshot resilience", test_screenshot_resilience),
        ("JPEG 95 estabilidad", test_jpeg_stability),
        ("Hash estabilidad", test_hash_stability),
    ]

    for name, fn in tests:
        try:
            fn()
            print(f"[OK] {name}")
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
