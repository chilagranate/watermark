import os
from dataclasses import dataclass

from dotenv import load_dotenv

_CONFIG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_env_path = os.path.join(_CONFIG_ROOT, ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path, override=True)
else:
    load_dotenv()


@dataclass
class Config:
    server_url: str = "http://127.0.0.1:8765"
    api_key: str = ""
    db_path: str = "data/watermarks.db"
    rs_bits: int = 16
    vs_model: str = "videoseal"
    vs_scaling_w: float = 0.3
    video_frame_step: int = 30
    output_dir: str = ""


def cargar_config() -> Config:
    return Config(
        server_url=os.getenv("WATERMARK_SERVER_URL", "http://127.0.0.1:8765"),
        api_key=os.getenv("WATERMARK_API_KEY", ""),
        db_path=os.getenv("WATERMARK_DB_PATH", "data/watermarks.db"),
        rs_bits=int(os.getenv("WATERMARK_RS_BITS", "16")),
        vs_model=os.getenv("WATERMARK_VS_MODEL", "videoseal"),
        vs_scaling_w=float(os.getenv("WATERMARK_VS_SCALING_W", "0.3")),
        video_frame_step=int(os.getenv("WATERMARK_VIDEO_FRAME_STEP", "30")),
        output_dir=os.getenv("WATERMARK_OUTPUT_DIR", ""),
    )
