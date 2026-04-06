"""Download de videos do YouTube via yt-dlp."""

import logging
import os
import re
from datetime import datetime
from pathlib import Path

import yt_dlp

from leilao_inteligente.config import VIDEOS_DIR


logger = logging.getLogger(__name__)


def extrair_video_id(url: str) -> str:
    """Extrai o ID do video a partir de uma URL do YouTube."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:embed/)([a-zA-Z0-9_-]{11})",
        r"(?:/live/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Nao foi possivel extrair video ID de: {url}")


def _baixar_via_proxy(url: str, output_path: Path, proxy_url: str) -> bool:
    """Tenta baixar video via video-proxy remoto (sua maquina local)."""
    import urllib.request
    import shutil

    video_id = extrair_video_id(url)
    download_url = f"{proxy_url}/download?url={urllib.parse.quote(url)}"

    logger.info("Baixando via video-proxy: %s", proxy_url)
    try:
        req = urllib.request.Request(download_url)
        with urllib.request.urlopen(req, timeout=600) as response:
            with open(output_path, "wb") as f:
                shutil.copyfileobj(response, f)
        size_mb = output_path.stat().st_size / 1024 / 1024
        logger.info("Video baixado via proxy: %.1f MB", size_mb)
        return True
    except Exception as e:
        logger.warning("Falha no video-proxy: %s", e)
        if output_path.exists():
            output_path.unlink()
        return False


def baixar_video(
    url: str,
    output_dir: Path | None = None,
    cookies_file: str | None = None,
) -> Path:
    """Baixa video do YouTube e retorna o caminho do arquivo.

    Tenta na ordem:
    1. Video-proxy remoto (sua maquina via Cloudflare Tunnel)
    2. yt-dlp direto com cookies
    3. yt-dlp direto sem cookies
    """
    output_dir = output_dir or VIDEOS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    video_id = extrair_video_id(url)
    output_path = output_dir / f"{video_id}.mp4"

    if output_path.exists():
        logger.info("Video ja existe: %s", output_path)
        return output_path

    # 1. Tentar via video-proxy (maquina local com IP residencial)
    from leilao_inteligente.config import get_settings
    proxy_url = get_settings().video_proxy_url
    if proxy_url:
        if _baixar_via_proxy(url, output_path, proxy_url):
            return output_path

    # 2. Tentar yt-dlp direto
    ydl_opts: dict[str, object] = {
        "format": "best[height<=360][ext=mp4]/best[height<=360]",
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


def obter_info_video(url: str, cookies_file: str | None = None) -> dict[str, object]:
    """Obtem metadados do video sem baixar.

    Tenta via video-proxy primeiro, depois yt-dlp direto.
    """
    # 1. Tentar via video-proxy
    from leilao_inteligente.config import get_settings
    proxy_url = get_settings().video_proxy_url
    if proxy_url:
        try:
            import urllib.request
            import urllib.parse
            import json
            info_url = f"{proxy_url}/info?url={urllib.parse.quote(url)}"
            req = urllib.request.Request(info_url)
            with urllib.request.urlopen(req, timeout=60) as response:
                data = json.loads(response.read())
                if "error" not in data:
                    logger.info("Info obtida via video-proxy")
                    return data
        except Exception as e:
            logger.warning("Video-proxy info falhou: %s", e)

    # 2. yt-dlp direto
    ydl_opts: dict[str, object] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    if cookies_file:
        ydl_opts["cookiefile"] = cookies_file

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


def extrair_data_leilao(info: dict[str, object]) -> datetime | None:
    """Extrai a data real do leilao a partir do titulo, descricao ou upload_date.

    Prioridade:
    1. Data no titulo (ex: "LEILAO ... 26/03/2026")
    2. Data na descricao
    3. upload_date do YouTube (YYYYMMDD)
    """
    import re

    padrao_data = re.compile(r"(\d{2})/(\d{2})/(\d{4})")

    # 1. Tentar titulo
    titulo = str(info.get("title", ""))
    match = padrao_data.search(titulo)
    if match:
        dia, mes, ano = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            return datetime(ano, mes, dia)
        except ValueError:
            pass

    # 2. Tentar descricao
    descricao = str(info.get("description", ""))
    match = padrao_data.search(descricao)
    if match:
        dia, mes, ano = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            return datetime(ano, mes, dia)
        except ValueError:
            pass

    # 3. Fallback: upload_date do YouTube (YYYYMMDD)
    upload_date = str(info.get("upload_date", ""))
    if len(upload_date) == 8 and upload_date.isdigit():
        try:
            return datetime(int(upload_date[:4]), int(upload_date[4:6]), int(upload_date[6:8]))
        except ValueError:
            pass

    return None


# UFs validas para matching
_UFS = {
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO",
    "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR",
    "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
}


def extrair_local_leilao(info: dict[str, object]) -> tuple[str | None, str | None]:
    """Extrai cidade e estado do titulo ou descricao do video.

    Procura padroes como "RIANÁPOLIS-GO", "CRIXAS - GO", "GOIÂNIA/GO".

    Returns:
        Tupla (cidade, estado) ou (None, None).
    """
    # Procurar CIDADE-UF no final de segmentos (separados por espaço, hífen, barra)
    # Ex: "RIANÁPOLIS-GO", "CRIXAS-GO", "GOIÂNIA/GO"
    padrao = re.compile(r"([\w\u00C0-\u024F]+(?:\s+[\w\u00C0-\u024F]+)*)\s*[-/]\s*([A-Z]{2})\b")

    for campo in ["title", "description"]:
        texto = str(info.get(campo, ""))
        for match in padrao.finditer(texto):
            cidade_raw = match.group(1).strip()
            estado = match.group(2).upper()
            if estado in _UFS and len(cidade_raw) >= 3:
                # Pegar só a última palavra antes do UF (a cidade)
                # Ex: "SINDICATO RURAL DE CRIXAS" → pegar "CRIXAS"
                # Mas "RIANÁPOLIS" → pegar "RIANÁPOLIS"
                # Heurística: se tem mais de 2 palavras, pegar a última
                palavras = cidade_raw.split()
                if len(palavras) > 2:
                    # Procurar a última palavra que parece nome de cidade (>3 letras)
                    cidade = palavras[-1].title()
                else:
                    cidade = cidade_raw.title()
                return cidade, estado

    return None, None


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
