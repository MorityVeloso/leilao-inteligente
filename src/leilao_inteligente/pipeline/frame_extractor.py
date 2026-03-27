"""Extracao de frames de video usando ffmpeg."""

import logging
import subprocess
from pathlib import Path

from leilao_inteligente.config import FRAMES_DIR


logger = logging.getLogger(__name__)


def extrair_frames(
    video_path: Path,
    output_dir: Path | None = None,
    intervalo_segundos: int = 15,
) -> list[Path]:
    """Extrai frames de um video em intervalos regulares usando ffmpeg.

    Args:
        video_path: Caminho do arquivo de video.
        output_dir: Diretorio de saida dos frames. Padrao: data/frames/{video_name}/
        intervalo_segundos: Intervalo entre frames em segundos.

    Returns:
        Lista de Paths dos frames extraidos, ordenados por timestamp.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video nao encontrado: {video_path}")

    video_name = video_path.stem
    output_dir = output_dir or (FRAMES_DIR / video_name)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Verificar se frames ja foram extraidos
    existing_frames = sorted(output_dir.glob("frame_*.jpg"))
    if existing_frames:
        logger.info(
            "Frames ja extraidos (%d frames): %s", len(existing_frames), output_dir
        )
        return existing_frames

    output_pattern = str(output_dir / "frame_%06d.jpg")

    cmd = [
        "ffmpeg",
        "-i", str(video_path),
        "-vf", f"fps=1/{intervalo_segundos}",
        "-q:v", "2",  # qualidade JPEG (2 = alta)
        "-y",  # sobrescrever
        output_pattern,
    ]

    logger.info(
        "Extraindo frames a cada %ds de: %s", intervalo_segundos, video_path.name
    )

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou: {result.stderr[:500]}")

    frames = sorted(output_dir.glob("frame_*.jpg"))
    logger.info("Extraidos %d frames em: %s", len(frames), output_dir)
    return frames


def frame_timestamp(frame_path: Path, intervalo_segundos: int = 15) -> float:
    """Calcula o timestamp (em segundos) de um frame pelo seu nome.

    frame_000001.jpg → 0s (primeiro frame)
    frame_000002.jpg → 15s
    frame_000003.jpg → 30s
    """
    nome = frame_path.stem  # "frame_000042"
    numero = int(nome.split("_")[1])
    return (numero - 1) * intervalo_segundos
