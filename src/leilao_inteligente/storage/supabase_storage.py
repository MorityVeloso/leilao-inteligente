"""Upload de frames para Supabase Storage."""

import logging
from pathlib import Path

import httpx

from leilao_inteligente.config import get_settings

logger = logging.getLogger(__name__)

BUCKET = "lote-frames"


def _headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "image/jpeg",
        "x-upsert": "true",
    }


def upload_frame(storage_path: str, image_bytes: bytes) -> str | None:
    """Upload uma imagem para Supabase Storage.

    Args:
        storage_path: Path relativo no bucket (ex: video_id/lote/visual_1.jpg)
        image_bytes: Conteúdo JPEG da imagem

    Returns:
        URL pública da imagem, ou None em caso de erro.
    """
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        logger.warning("Supabase não configurado, frames não serão uploadados")
        return None

    url = f"{settings.supabase_url}/storage/v1/object/{BUCKET}/{storage_path}"

    try:
        resp = httpx.post(url, headers=_headers(), content=image_bytes, timeout=30)
        if resp.status_code == 200:
            return public_url(storage_path)
        logger.error("Upload falhou (%d): %s", resp.status_code, resp.text[:200])
        return None
    except httpx.HTTPError as e:
        logger.error("Erro no upload: %s", e)
        return None


def upload_frame_file(storage_path: str, file_path: Path) -> str | None:
    """Upload um arquivo JPEG do disco para Supabase Storage."""
    return upload_frame(storage_path, file_path.read_bytes())


def public_url(storage_path: str) -> str:
    """Retorna URL pública de um frame no Supabase Storage."""
    settings = get_settings()
    return f"{settings.supabase_url}/storage/v1/object/public/{BUCKET}/{storage_path}"
