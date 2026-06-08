import uuid


def generar_id_unico(prefix: str = "wm") -> str:
    uid = uuid.uuid4().hex[:16]
    return f"{prefix}_{uid}"
