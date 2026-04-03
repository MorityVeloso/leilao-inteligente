"""Roda APENAS a passada 4 (detecção de carimbo VENDIDO) nos vídeos existentes.

Usa lotes já consolidados no banco + frames do vídeo em disco.
Não re-baixa nem reprocessa overlay — só busca carimbo visual.

Uso: python scripts/passada4.py
"""

import logging
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import cv2

from leilao_inteligente.config import get_settings, DATA_DIR, FRAMES_DIR
from leilao_inteligente.models.schemas import LoteConsolidado
from leilao_inteligente.pipeline.processor import LoteComFrame, _calcular_janelas_carimbo
from leilao_inteligente.pipeline.frame_extractor import extrair_frames_janela, frame_timestamp
from leilao_inteligente.pipeline.vision import (
    _preparar_frame, _cache_key, _cache_get,
    detectar_carimbo_arrematacao,
)
from leilao_inteligente.pipeline.stamp_profile import (
    obter_perfil, calibrar_carimbo, detectar_com_perfil,
    change_score_frame_inteiro, DETECCAO_DEFAULT_THRESHOLD,
)
from leilao_inteligente.pipeline.validator import validar_lote
from leilao_inteligente.storage.db import get_session, init_db
from leilao_inteligente.models.database import Leilao, Lote

# Pular fallback Supabase (usa só cache local)
import leilao_inteligente.pipeline.vision as _vision
_vision._skip_remote_cache = True

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def reconstruir_lotes_com_frame(video_id: str) -> list[LoteComFrame]:
    """Reconstrói lotes_com_frame do cache local (sem Gemini)."""
    settings = get_settings()
    frame_dir = FRAMES_DIR / video_id

    all_frames = sorted(frame_dir.glob("frame_*.jpg"))
    refine_dir = frame_dir / "refine"
    if refine_dir.exists():
        all_frames.extend(sorted(refine_dir.glob("refine_*.jpg")))

    lotes_com_frame: list[LoteComFrame] = []
    for fp in all_frames:
        try:
            overlay_bytes = _preparar_frame(fp)
        except Exception:
            continue
        key = _cache_key(overlay_bytes)
        cached = _cache_get(key)
        if cached is None:
            continue
        ts_seg = frame_timestamp(fp, settings.frame_interval_seconds)
        ts = datetime.now(tz=timezone.utc) + timedelta(seconds=ts_seg)
        lote = validar_lote(cached, timestamp_frame=ts)
        if lote is not None:
            lotes_com_frame.append(LoteComFrame(lote, fp))

    return lotes_com_frame


def lotes_db_para_consolidados(lotes_db: list[Lote]) -> list[LoteConsolidado]:
    """Converte lotes do banco para LoteConsolidado."""
    consolidados = []
    for l in lotes_db:
        c = LoteConsolidado(
            lote_numero=l.lote_numero,
            quantidade=l.quantidade,
            raca=l.raca,
            sexo=l.sexo,
            condicao=l.condicao,
            idade_meses=l.idade_meses,
            pelagem=l.pelagem,
            preco_inicial=l.preco_inicial,
            preco_final=l.preco_final,
            preco_por_cabeca=l.preco_por_cabeca,
            timestamp_inicio=l.timestamp_inicio,
            timestamp_fim=l.timestamp_fim,
            frames_analisados=l.frames_analisados,
            confianca_media=l.confianca_media,
            aparicoes=l.aparicoes,
            status=l.status,
            frame_paths=[],
            segundo_video=l.segundo_video,
        )
        consolidados.append(c)
    return consolidados


def rodar_passada4(video_path: Path, video_id: str, leilao: Leilao) -> None:
    """Roda passada 4 para um vídeo e atualiza status no banco."""
    settings = get_settings()
    canal = leilao.canal_youtube

    session = get_session()
    try:
        lotes_db = session.query(Lote).filter(Lote.leilao_id == leilao.id).all()
        lotes_sem_video = [l for l in lotes_db if l.segundo_video is None]
        lotes_com_video = [l for l in lotes_db if l.segundo_video is not None]

        if not lotes_com_video:
            logger.info("  Sem lotes com segundo_video, pulando")
            return

        consolidados = lotes_db_para_consolidados(lotes_com_video)
        incertos = [c for c in consolidados if c.status == "incerto"]

        logger.info("  %d lotes total, %d incertos (candidatos)", len(consolidados), len(incertos))

        if not incertos:
            logger.info("  Nenhum lote incerto, pulando")
            return

        # Reconstruir lotes_com_frame do cache
        logger.info("  Reconstruindo frames do cache...")
        lotes_com_frame = reconstruir_lotes_com_frame(video_id)
        logger.info("  %d frames com dados", len(lotes_com_frame))

        # Obter ou calibrar perfil
        perfil = obter_perfil(canal) if canal else None
        if perfil is None and canal:
            arrematados = [c for c in consolidados if c.status == "arrematado"]
            if len(arrematados) >= 2:
                logger.info("  Calibrando carimbo para '%s'...", canal)
                perfil = calibrar_carimbo(
                    video_path, canal, arrematados, lotes_com_frame, settings.frame_interval_seconds,
                )

        if perfil and perfil.get("confianca", 0) == 0:
            logger.info("  Canal sem carimbo detectável, pulando")
            return

        # Calcular janelas
        janelas = _calcular_janelas_carimbo(consolidados, lotes_com_frame, settings.frame_interval_seconds)

        stamp_dir = FRAMES_DIR / video_id / "passada4"
        stamp_dir.mkdir(parents=True, exist_ok=True)

        detectados = 0
        total = 0

        # Só processar lotes incertos (os arrematados já estão corretos)
        for consolidado in incertos:
            janela = janelas.get(consolidado.lote_numero)
            if not janela:
                continue

            janela_inicio, janela_fim = janela
            total += 1

            # Extrair frames a cada 2s
            frames_stamp = extrair_frames_janela(
                video_path, janela_inicio, janela_fim, stamp_dir,
                intervalo_segundos=2,
            )
            if not frames_stamp:
                continue

            # Pré-filtrar + Gemini
            candidatos: list[Path] = []
            prev_frame = None
            for fp in frames_stamp:
                frame = cv2.imread(str(fp))
                if frame is None:
                    continue
                if prev_frame is not None:
                    if perfil and perfil.get("regiao"):
                        eh_candidato = detectar_com_perfil(frame, prev_frame, perfil)
                    else:
                        score = change_score_frame_inteiro(prev_frame, frame)
                        eh_candidato = score > DETECCAO_DEFAULT_THRESHOLD
                    if eh_candidato:
                        candidatos.append(fp)
                prev_frame = frame

            # Enviar candidatos ao Gemini
            tem_carimbo = False
            for fp in candidatos:
                if detectar_carimbo_arrematacao(fp):
                    tem_carimbo = True
                    break

            # Se não achou por pré-filtro, tentar direto (sampling mais esparso)
            if not tem_carimbo and not candidatos:
                for fp in frames_stamp[::3]:  # cada 6s
                    if detectar_carimbo_arrematacao(fp):
                        tem_carimbo = True
                        break

            if tem_carimbo:
                detectados += 1
                # Atualizar no banco
                lote_db = next((l for l in lotes_db if l.lote_numero == consolidado.lote_numero), None)
                if lote_db and lote_db.status != "arrematado":
                    lote_db.status = "arrematado"
                    logger.info("  ✅ Lote %s → arrematado (era incerto)", consolidado.lote_numero)

        session.commit()
        logger.info("  Passada 4: %d/%d incertos → arrematado", detectados, total)

    finally:
        session.close()


def main():
    init_db()
    session = get_session()
    try:
        leiloes = session.query(Leilao).order_by(Leilao.data_leilao).all()
        videos = []
        for l in leiloes:
            from leilao_inteligente.pipeline.downloader import extrair_video_id
            vid = extrair_video_id(l.url_video)
            video_path = Path(f"{DATA_DIR}/videos/{vid}.mp4")
            if video_path.exists():
                videos.append((video_path, vid, l))
            else:
                logger.warning("Vídeo não encontrado: %s", video_path)
    finally:
        session.close()

    logger.info("Rodando passada 4 em %d vídeos...\n", len(videos))

    for video_path, video_id, leilao in videos:
        logger.info("=== %s (%s) ===", leilao.titulo[:50], video_id)
        rodar_passada4(video_path, video_id, leilao)
        logger.info("")

    # Resumo final
    session = get_session()
    try:
        total = {}
        for l in session.query(Lote).all():
            total[l.status] = total.get(l.status, 0) + 1
        logger.info("=== RESULTADO FINAL: %s ===", total)
    finally:
        session.close()


if __name__ == "__main__":
    main()
