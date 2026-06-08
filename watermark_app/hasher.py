from io import BytesIO

import imagehash
from PIL import Image


def calcular_phash(imagen: Image.Image) -> str:
    if imagen.mode in ("RGBA", "LA", "P"):
        imagen = imagen.convert("RGB")
    return str(imagehash.phash(imagen))


def calcular_dhash(imagen: Image.Image) -> str:
    if imagen.mode in ("RGBA", "LA", "P"):
        imagen = imagen.convert("RGB")
    return str(imagehash.dhash(imagen))


def calcular_hashes(imagen: Image.Image) -> tuple[str, str]:
    return calcular_phash(imagen), calcular_dhash(imagen)


def hashes_desde_archivo(ruta: str) -> tuple[str, str]:
    img = Image.open(ruta)
    return calcular_hashes(img)


def distancia_hamming(h1: str, h2: str) -> int:
    a = int(h1, 16)
    b = int(h2, 16)
    return bin(a ^ b).count("1")
