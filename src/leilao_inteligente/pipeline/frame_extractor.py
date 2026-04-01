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


def extrair_frames_janela(
    video_path: Path,
    inicio_segundos: float,
    fim_segundos: float,
    output_dir: Path,
    intervalo_segundos: int = 1,
) -> list[Path]:
    """Extrai frames de uma janela especifica do video.

    Usado na passada 2 pra refinar lotes com poucos frames.

    Args:
        video_path: Caminho do video.
        inicio_segundos: Segundo inicial da janela.
        fim_segundos: Segundo final da janela.
        output_dir: Diretorio de saida.
        intervalo_segundos: Intervalo entre frames (padrao 1s).

    Returns:
        Lista de Paths dos frames extraidos.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video nao encontrado: {video_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    duracao = fim_segundos - inicio_segundos
    if duracao <= 0:
        return []

    # Prefixo unico pra nao colidir com frames da passada 1
    prefix = f"refine_{int(inicio_segundos)}"
    output_pattern = str(output_dir / f"{prefix}_%04d.jpg")

    cmd = [
        "ffmpeg",
        "-ss", str(inicio_segundos),
        "-i", str(video_path),
        "-t", str(duracao),
        "-vf", f"fps=1/{intervalo_segundos}",
        "-q:v", "2",
        "-y",
        output_pattern,
    ]

    result = subprocess.run(
        cmd, capture_output=True, text=True, check=False,
    )

    if result.returncode != 0:
        logger.warning("ffmpeg falhou na janela %d-%ds: %s", inicio_segundos, fim_segundos, result.stderr[:200])
        return []

    frames = sorted(output_dir.glob(f"{prefix}_*.jpg"))
    logger.info(
        "Janela %d-%ds: extraidos %d frames a cada %ds",
        inicio_segundos, fim_segundos, len(frames), intervalo_segundos,
    )
    return frames


def frame_timestamp(frame_path: Path, intervalo_segundos: int = 15) -> float:
    """Calcula o timestamp (em segundos) de um frame pelo seu nome.

    Frames normais: frame_000042.jpg → (42-1) * intervalo
    Frames de refine: refine_1200_0003.jpg → 1200 + (3-1)
    """
    nome = frame_path.stem
    parts = nome.split("_")

    if parts[0] == "refine" and len(parts) >= 3:
        inicio_seg = int(parts[1])
        frame_num = int(parts[2])
        return inicio_seg + (frame_num - 1)

    numero = int(parts[1])
    return (numero - 1) * intervalo_segundos
