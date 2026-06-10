import os
import secrets
import sys

import cv2
import numpy as np
import threading

from watermark_app.hasher import calcular_hashes


def _generar_fingerprint() -> np.ndarray:
    return np.random.RandomState(secrets.randbits(32)).randint(0, 2, 256).astype(np.float32)


def _fingerprint_a_hex(fp: np.ndarray) -> str:
    bits = fp.astype(np.uint8).tolist()
    hex_str = ""
    for i in range(0, len(bits), 4):
        nibble = (bits[i] << 3 | bits[i + 1] << 2 |
                  bits[i + 2] << 1 | bits[i + 3])
        hex_str += format(nibble, "x")
    return hex_str


def _hex_a_fingerprint(hex_str: str) -> np.ndarray:
    bits = []
    for ch in hex_str:
        nibble = int(ch, 16)
        for shift in (3, 2, 1, 0):
            bits.append(float((nibble >> shift) & 1))
    return np.array(bits, dtype=np.float32)


def _cargar_modelo(model_name: str = "videoseal", scaling_w: float = 0.3):
    global _modelo_cache

    base_key = (model_name,)
    if base_key not in _modelo_cache:
        with _modelo_lock:
            if base_key not in _modelo_cache:
                import videoseal
                cwd = os.getcwd()
                if getattr(sys, 'frozen', False):
                    import tempfile, shutil
                    meipass = sys._MEIPASS
                    tmpdir = tempfile.mkdtemp(prefix='wmcfg_')
                    for rel in ('configs', 'videoseal/cards'):
                        src = os.path.join(meipass, rel)
                        if os.path.exists(src):
                            shutil.copytree(src, os.path.join(tmpdir, rel), dirs_exist_ok=True)
                    os.chdir(tmpdir)
                else:
                    pkg_dir = os.path.dirname(videoseal.__file__)
                    site_packages = os.path.dirname(pkg_dir)
                    os.chdir(site_packages)
                try:
                    model = videoseal.load(model_name)
                finally:
                    os.chdir(cwd)
                _modelo_cache[base_key] = model

    model = _modelo_cache[base_key]
    model.blender.scaling_w = scaling_w
    return model


_modelo_cache = {}
_modelo_lock = threading.Lock()


def marcar_imagen(ruta_entrada: str, fingerprint: np.ndarray | None = None,
                  output_dir: str = "",
                  model_name: str = "videoseal",
                  scaling_w: float = 0.3) -> tuple[str, np.ndarray]:

    import torch
    import torchvision.transforms as T
    from PIL import Image

    if fingerprint is None:
        fingerprint = _generar_fingerprint()

    msg = torch.from_numpy(fingerprint).unsqueeze(0)
    img = Image.open(ruta_entrada).convert("RGB")
    img_tensor = T.ToTensor()(img).unsqueeze(0)

    model = _cargar_modelo(model_name, scaling_w)

    try:
        with torch.no_grad():
            outputs = model.embed(img_tensor, msgs=msg)
            wm = outputs["imgs_w"]
    except Exception as e:
        import traceback
        details = (
            f"\n{'='*60}\n"
            f"ERROR marcando: {os.path.basename(ruta_entrada)}\n"
            f"  Dimensiones: {img.width}x{img.height}\n"
            f"  Tensor shape: {img_tensor.shape}\n"
            f"  Fingerprint bits: {len(fingerprint)}\n"
            f"  Fingerprint unique values: {np.unique(fingerprint)}\n"
            f"  scaling_w: {scaling_w}\n"
            f"  model_name: {model_name}\n"
            f"  Error: {e}\n"
            f"{'='*60}\n"
        )
        print(details)
        traceback.print_exc()
        with open(os.path.join(os.path.expanduser("~"), "watermark_error.log"), "a", encoding="utf-8") as f:
            f.write(details)
            f.write(traceback.format_exc())
        raise

    if not output_dir:
        output_dir = os.path.dirname(ruta_entrada) or "."
    os.makedirs(output_dir, exist_ok=True)
    nombre_base = os.path.splitext(os.path.basename(ruta_entrada))[0]
    ruta_salida = os.path.join(output_dir, f"{nombre_base}_wm.png")

    T.ToPILImage()(wm[0]).save(ruta_salida, "PNG")
    return ruta_salida, fingerprint


def marcar_y_hashear(ruta_entrada: str, fingerprint: np.ndarray | None = None,
                     output_dir: str = "",
                     model_name: str = "videoseal",
                     scaling_w: float = 0.3) -> dict:

    ruta_salida, fp = marcar_imagen(
        ruta_entrada=ruta_entrada,
        fingerprint=fingerprint,
        output_dir=output_dir,
        model_name=model_name,
        scaling_w=scaling_w,
    )

    from PIL import Image
    img = Image.open(ruta_salida)
    phash, dhash = calcular_hashes(img)

    return {
        "ruta_original": os.path.abspath(ruta_entrada),
        "ruta_marcada": os.path.abspath(ruta_salida),
        "fingerprint": fp,
        "fingerprint_hex": _fingerprint_a_hex(fp),
        "phash": phash,
        "dhash": dhash,
    }


def extraer_fingerprint(ruta_imagen: str,
                         model_name: str = "videoseal") -> np.ndarray:

    import torch
    import torchvision.transforms as T
    from PIL import Image

    img = Image.open(ruta_imagen).convert("RGB")
    img_tensor = T.ToTensor()(img).unsqueeze(0)

    model = _cargar_modelo(model_name)

    with torch.no_grad():
        detected = model.detect(img_tensor)
        preds = detected["preds"][0, 1:]

    return (preds > 0).float().numpy()


def extraer_fingerprint_hex(ruta_imagen: str,
                              model_name: str = "videoseal") -> str:
    fp = extraer_fingerprint(ruta_imagen, model_name)
    return _fingerprint_a_hex(fp)


def generar_fingerprint() -> np.ndarray:
    return _generar_fingerprint()
