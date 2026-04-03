"""Reconsolida lotes usando dados já no cache Gemini (sem novas requests).

Uso: python scripts/reconsolidar.py
"""

import logging
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from leilao_inteligente.config import get_settings, DATA_DIR
from leilao_inteligente.pipeline.vision import _preparar_frame, _cache_key, _cache_get
from leilao_inteligente.pipeline.validator import validar_lote
from leilao_inteligente.pipeline.frame_extractor import frame_timestamp
from leilao_inteligente.pipeline.processor import LoteComFrame, consolidar_lotes
from leilao_inteligente.pipeline.downloader import extrair_video_id
from leilao_inteligente.storage.db import get_session, init_db
from leilao_inteligente.models.database import Leilao, Lote

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

FRAMES_DIR = DATA_DIR / "frames"

# Pular fallback Supabase (usa só cache local, muito mais rápido)
import leilao_inteligente.pipeline.vision as _vision
_vision._skip_remote_cache = True


def reconsolidar_video(video_id: str) -> list:
    """Lê frames do disco, busca no cache, valida e reconsolida."""
    frame_dir = FRAMES_DIR / video_id
    if not frame_dir.exists():
        logger.error("Diretório de frames não encontrado: %s", frame_dir)
        return []

    # Coletar todos os frames (passada 1 + refine)
    all_frames = sorted(frame_dir.glob("frame_*.jpg"))
    refine_dir = frame_dir / "refine"
    if refine_dir.exists():
        all_frames.extend(sorted(refine_dir.glob("refine_*.jpg")))

    logger.info("Video %s: %d frames no disco", video_id, len(all_frames))

    settings = get_settings()
    lotes_com_frame: list[LoteComFrame] = []
    cache_hits = 0
    cache_misses = 0

    for fp in all_frames:
        try:
            overlay_bytes = _preparar_frame(fp)
        except (ValueError, Exception):
            continue

        key = _cache_key(overlay_bytes)
        cached = _cache_get(key)

        if cached is None:
            cache_misses += 1
            continue

        cache_hits += 1
        ts_seg = frame_timestamp(fp, settings.frame_interval_seconds)
        ts = datetime.now(tz=timezone.utc) + timedelta(seconds=ts_seg)
        lote = validar_lote(cached, timestamp_frame=ts)
        if lote is not None:
            lotes_com_frame.append(LoteComFrame(lote, fp))

    logger.info(
        "Video %s: cache hits=%d, misses=%d, lotes válidos=%d",
        video_id, cache_hits, cache_misses, len(lotes_com_frame),
    )

    if not lotes_com_frame:
        return []

    consolidados = consolidar_lotes(lotes_com_frame, video_id=video_id)
    logger.info("Video %s: %d lotes consolidados", video_id, len(consolidados))
    return consolidados


def salvar_no_banco(video_id: str, url: str, consolidados: list) -> None:
    """Atualiza os lotes no banco, substituindo os antigos."""
    session = get_session()
    try:
        leilao = session.query(Leilao).filter(Leilao.url_video == url).first()
        if not leilao:
            logger.error("Leilão não encontrado para URL: %s", url)
            return

        # Deletar lotes antigos
        antigos = session.query(Lote).filter(Lote.leilao_id == leilao.id).count()
        session.query(Lote).filter(Lote.leilao_id == leilao.id).delete()

        # Inserir novos
        for c in consolidados:
            lote = Lote(
                leilao_id=leilao.id,
                lote_numero=c.lote_numero,
                quantidade=c.quantidade,
                raca=c.raca,
                sexo=c.sexo,
                condicao=c.condicao,
                idade_meses=c.idade_meses,
                pelagem=c.pelagem,
                preco_inicial=float(c.preco_inicial) if c.preco_inicial else None,
                preco_final=float(c.preco_final) if c.preco_final else None,
                preco_por_cabeca=float(c.preco_por_cabeca) if c.preco_por_cabeca else None,
                fazenda_vendedor=c.fazenda_vendedor,
                timestamp_inicio=c.timestamp_inicio,
                timestamp_fim=c.timestamp_fim,
                frames_analisados=c.frames_analisados,
                confianca_media=c.confianca_media,
                aparicoes=c.aparicoes,
                status=c.status,
                frame_paths="|".join(c.frame_paths) if c.frame_paths else None,
                segundo_video=c.segundo_video,
            )
            session.add(lote)

        leilao.total_lotes = len(consolidados)
        session.commit()

        logger.info(
            "Leilão '%s': %d lotes antigos → %d novos",
            leilao.titulo, antigos, len(consolidados),
        )
    finally:
        session.close()


def main():
    init_db()
    session = get_session()
    try:
        leiloes = session.query(Leilao).all()
        videos = [(l.url_video, l.titulo) for l in leiloes]
    finally:
        session.close()

    logger.info("Reconsolidando %d vídeos...", len(videos))

    for url, titulo in videos:
        video_id = extrair_video_id(url)
        logger.info("\n=== %s (%s) ===", titulo, video_id)
        consolidados = reconsolidar_video(video_id)
        if consolidados:
            salvar_no_banco(video_id, url, consolidados)

    logger.info("\nReconsolidação concluída!")


if __name__ == "__main__":
    main()
