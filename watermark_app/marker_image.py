import os
import secrets
import sys
from pathlib import Path

import cv2
import numpy as np
import threading
import requests as _requests

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
                    meipass = sys._MEIPASS
                    os.chdir(meipass)
                else:
                    pkg_dir = os.path.dirname(videoseal.__file__)
                    site_packages = os.path.dirname(pkg_dir)
                    os.chdir(site_packages)
                try:
                    from videoseal.utils.cfg import setup_model
                    from omegaconf import OmegaConf
                    import yaml
                    cards_dir = Path("videoseal/cards")
                    card_path = cards_dir / f"{model_name}_1.0.yaml" if model_name == "videoseal" and not (cards_dir / f"{model_name}.yaml").exists() else cards_dir / f"{model_name}.yaml"
                    if not card_path.exists():
                        avail = [c.stem for c in cards_dir.glob("*.yaml")]
                        card_path = cards_dir / f"{avail[0]}.yaml"
                    cfg = OmegaConf.load(card_path)
                    cfg.args.attenuation = "none"
                    ckpt_path = Path(cfg.checkpoint_path)
                    if not ckpt_path.is_file():
                        import urllib.request
                        ckpts_dir = Path("ckpts")
                        ckpts_dir.mkdir(exist_ok=True)
                        fname = os.path.basename(str(cfg.checkpoint_path).split("/")[-1])
                        ckpt_path = ckpts_dir / fname
                        if not ckpt_path.exists():
                            url = str(cfg.checkpoint_path)
                            urllib.request.urlretrieve(url, str(ckpt_path))
                            print(f"File {url} downloaded successfully to {ckpt_path}")
                    model = setup_model(cfg, str(ckpt_path))
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

    with torch.no_grad():
        outputs = model.embed(img_tensor, msgs=msg)
        wm = outputs["imgs_w"]

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
