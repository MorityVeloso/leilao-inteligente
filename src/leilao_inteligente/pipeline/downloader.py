"""Download de videos do YouTube via yt-dlp."""

import logging
import re
from pathlib import Path

import yt_dlp

from leilao_inteligente.config import VIDEOS_DIR


logger = logging.getLogger(__name__)


def extrair_video_id(url: str) -> str:
    """Extrai o ID do video a partir de uma URL do YouTube."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:embed/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Nao foi possivel extrair video ID de: {url}")


def baixar_video(
    url: str,
    output_dir: Path | None = None,
    cookies_file: str | None = None,
) -> Path:
    """Baixa video do YouTube e retorna o caminho do arquivo.

    Args:
        url: URL do video no YouTube.
        output_dir: Diretorio de saida. Padrao: data/videos/
        cookies_file: Caminho para arquivo de cookies (opcional).

    Returns:
        Path do arquivo de video baixado.
    """
    output_dir = output_dir or VIDEOS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    video_id = extrair_video_id(url)
    output_path = output_dir / f"{video_id}.mp4"

    if output_path.exists():
        logger.info("Video ja existe: %s", output_path)
        return output_path

    ydl_opts: dict[str, object] = {
        "format": "best[ext=mp4]/best",
        "outtmpl": str(output_path),
        "quiet": False,
        "no_warnings": False,
    }

    if cookies_file:
        ydl_opts["cookiefile"] = cookies_file

    logger.info("Baixando video: %s", url)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    if not output_path.exists():
        raise FileNotFoundError(f"Falha ao baixar video: {output_path}")

    logger.info("Video salvo em: %s", output_path)
    return output_path


def obter_info_video(url: str) -> dict[str, object]:
    """Obtem metadados do video sem baixar."""
    ydl_opts: dict[str, object] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if info is None:
        raise ValueError(f"Nao foi possivel obter info do video: {url}")

    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "channel": info.get("channel"),
        "upload_date": info.get("upload_date"),
        "duration": info.get("duration"),
        "description": info.get("description", "")[:500],
    }


def listar_videos_canal(
    channel_url: str,
    limite: int = 50,
) -> list[dict[str, object]]:
    """Lista videos de um canal do YouTube.

    Args:
        channel_url: URL do canal.
        limite: Numero maximo de videos.

    Returns:
        Lista de dicts com id, title, url de cada video.
    """
    ydl_opts: dict[str, object] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": True,
        "playlistend": limite,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)

    if info is None or "entries" not in info:
        raise ValueError(f"Nao foi possivel listar videos do canal: {channel_url}")

    videos: list[dict[str, object]] = []
    for entry in info["entries"]:
        if entry is None:
            continue
        videos.append({
            "id": entry.get("id"),
            "title": entry.get("title"),
            "url": f"https://www.youtube.com/watch?v={entry.get('id')}",
        })

    logger.info("Encontrados %d videos no canal", len(videos))
    return videos
