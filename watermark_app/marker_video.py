import os

import numpy as np


def marcar_video(ruta_entrada: str, fingerprint: np.ndarray | None = None,
                 output_dir: str = "",
                 model_name: str = "videoseal",
                 scaling_w: float = 0.3,
                 frame_step: int = 30) -> tuple[str, np.ndarray]:

    import torch
    import cv2

    from watermark_app.marker_image import _generar_fingerprint, _cargar_modelo

    if fingerprint is None:
        fingerprint = _generar_fingerprint()

    msg = torch.from_numpy(fingerprint).unsqueeze(0)

    cap = cv2.VideoCapture(ruta_entrada)
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    model = _cargar_modelo(model_name, scaling_w)

    if not output_dir:
        output_dir = os.path.dirname(ruta_entrada) or "."
    os.makedirs(output_dir, exist_ok=True)
    nombre_base = os.path.splitext(os.path.basename(ruta_entrada))[0]
    ruta_salida = os.path.join(output_dir, f"{nombre_base}_wm.mp4")

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(ruta_salida, fourcc, fps, (width, height))
    if not out.isOpened():
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        ruta_salida = ruta_salida.replace('.mp4', '.avi')
        out = cv2.VideoWriter(ruta_salida, fourcc, fps, (width, height))
    if not out.isOpened():
        raise RuntimeError("No se pudo inicializar el codec de video. Instalá OpenH264 o usá .avi")

    import torchvision.transforms as T
    transform = T.ToTensor()

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_idx = 0
    out_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1

        if (frame_idx - 1) % frame_step != 0:
            out.write(frame)
            out_idx += 1
            continue

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        tensor = transform(frame_rgb).unsqueeze(0)
        with torch.no_grad():
            outputs = model.embed(tensor, msgs=msg)
            wm = outputs["imgs_w"][0]
        wm_frame = (wm.permute(1, 2, 0).numpy() * 255).astype(np.uint8)
        wm_bgr = cv2.cvtColor(wm_frame, cv2.COLOR_RGB2BGR)
        out.write(wm_bgr)
        out_idx += 1

        if total_frames > 0 and frame_idx % max(1, total_frames // 10) == 0:
            pct = frame_idx * 100 // total_frames
            wm_count = (frame_idx + frame_step - 1) // frame_step
            print(f"\r    {pct}% ({frame_idx}/{total_frames} frames, {wm_count} marcados)...", end="", flush=True)

    print(f"\r    100% ({frame_idx} frames, {out_idx} escritos)          ")

    cap.release()
    out.release()

    return ruta_salida, fingerprint


def marcar_video_y_hashear(ruta_entrada: str,
                            fingerprint: np.ndarray | None = None,
                            output_dir: str = "",
                            model_name: str = "videoseal",
                            scaling_w: float = 0.3,
                            frame_step: int = 30) -> dict:

    from PIL import Image
    import cv2
    from watermark_app.marker_image import _fingerprint_a_hex
    from watermark_app.hasher import calcular_hashes

    ruta_salida, fp = marcar_video(
        ruta_entrada=ruta_entrada,
        fingerprint=fingerprint,
        output_dir=output_dir,
        model_name=model_name,
        scaling_w=scaling_w,
        frame_step=frame_step,
    )

    cap = cv2.VideoCapture(ruta_salida)
    ret, frame = cap.read()
    cap.release()
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(frame_rgb)
    phash, dhash = calcular_hashes(img)

    return {
        "ruta_original": os.path.abspath(ruta_entrada),
        "ruta_marcada": os.path.abspath(ruta_salida),
        "fingerprint": fp,
        "fingerprint_hex": _fingerprint_a_hex(fp),
        "phash": phash,
        "dhash": dhash,
    }


def extraer_fingerprint_video(ruta_video: str,
                                model_name: str = "videoseal",
                                frame_step: int = 10) -> np.ndarray:

    import torch
    import cv2
    import torchvision.transforms as T

    from watermark_app.marker_image import _cargar_modelo

    model = _cargar_modelo(model_name)
    transform = T.ToTensor()

    cap = cv2.VideoCapture(ruta_video)
    all_preds = []
    frame_idx = 0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1

        if (frame_idx - 1) % frame_step != 0:
            continue

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        tensor = transform(frame_rgb).unsqueeze(0)
        with torch.no_grad():
            detected = model.detect(tensor)
            all_preds.append(detected["preds"][0])

        if total_frames > 0 and frame_idx % max(1, total_frames // 5) == 0:
            pct = frame_idx * 100 // total_frames
            print(f"\r    {pct}% leido...", end="", flush=True)

    cap.release()
    print(f"\r    {len(all_preds)} frames analizados")

    if not all_preds:
        raise RuntimeError("No se pudieron leer frames del video")

    avg_preds = torch.stack(all_preds).mean(dim=0)
    return (avg_preds[1:] > 0).float().numpy()
