"""CRUD operations para leiloes e lotes."""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from leilao_inteligente.models.database import Leilao, Lote
from leilao_inteligente.models.schemas import LeilaoInfo, LoteConsolidado
from leilao_inteligente.storage.db import get_session, init_db


logger = logging.getLogger(__name__)


def _precisa_revisar(lote: LoteConsolidado) -> bool:
    """Detecta se lote tem indicadores de problema que precisa revisão manual.

    Heurísticas:
    1. Possível inversão lote/quantidade: lote 1-9 com qtd >= 10
    2. Poucos frames com baixa confiança
    3. Preço suspeitamente baixo (possível truncamento não corrigido)
    """
    try:
        lote_int = int(lote.lote_numero)
    except (ValueError, TypeError):
        lote_int = None

    # 1. Possível inversão lote ↔ quantidade
    if lote_int is not None and 1 <= lote_int <= 9 and lote.quantidade >= 10:
        return True

    # 2. Poucos frames + baixa confiança
    if lote.frames_analisados <= 2 and lote.confianca_media < 0.85:
        return True

    # 3. Preço inicial ou final zerado (mas o outro não)
    if lote.preco_inicial == 0 and lote.preco_final > 0:
        return True
    if lote.preco_final == 0 and lote.preco_inicial > 0:
        return True

    return False


def salvar_leilao(
    info: LeilaoInfo,
    lotes: list[LoteConsolidado],
) -> Leilao:
    """Salva um leilao completo com seus lotes no banco."""
    init_db()
    session = get_session()

    try:
        existente = (
            session.query(Leilao)
            .filter(Leilao.url_video == info.url_video)
            .first()
        )
        if existente:
            logger.info("Leilao ja existe (id=%d), atualizando...", existente.id)
            session.delete(existente)
            session.commit()

        leilao = Leilao(
            canal_youtube=info.canal_youtube,
            url_video=info.url_video,
            titulo=info.titulo,
            data_leilao=info.data_leilao,
            local_cidade=info.local_cidade or (lotes[0].local_cidade if lotes else None),
            local_estado=info.local_estado or (lotes[0].local_estado if lotes else None),
            total_lotes=len(lotes),
            processado_em=datetime.now(tz=timezone.utc),
            status="completo",
        )
        session.add(leilao)
        session.flush()

        for lote_data in lotes:
            lote = Lote(
                leilao_id=leilao.id,
                lote_numero=lote_data.lote_numero,
                quantidade=lote_data.quantidade,
                raca=lote_data.raca,
                sexo=lote_data.sexo,
                condicao=lote_data.condicao,
                idade_meses=lote_data.idade_meses,
                pelagem=lote_data.pelagem,
                preco_inicial=lote_data.preco_inicial,
                preco_final=lote_data.preco_final,
                preco_por_cabeca=lote_data.preco_por_cabeca,
                fazenda_vendedor=lote_data.fazenda_vendedor,
                timestamp_inicio=lote_data.timestamp_inicio,
                timestamp_fim=lote_data.timestamp_fim,
                timestamp_video_inicio=lote_data.timestamp_video_inicio,
                timestamp_video_fim=lote_data.timestamp_video_fim,
                frames_analisados=lote_data.frames_analisados,
                confianca_media=lote_data.confianca_media,
                aparicoes=lote_data.aparicoes,
                status=lote_data.status,
                frame_paths="|".join(lote_data.frame_paths) if lote_data.frame_paths else None,
                segundo_video=lote_data.segundo_video,
                revisar=int(_precisa_revisar(lote_data)),
            )
            session.add(lote)

        session.commit()
        logger.info("Salvo leilao id=%d com %d lotes", leilao.id, len(lotes))
        return leilao

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def listar_leiloes() -> list[Leilao]:
    """Retorna todos os leiloes ordenados por data."""
    init_db()
    session = get_session()
    try:
        return (
            session.query(Leilao)
            .order_by(Leilao.processado_em.desc())
            .all()
        )
    finally:
        session.close()


def obter_leilao(leilao_id: int) -> Leilao | None:
    """Retorna um leilao pelo ID."""
    init_db()
    session = get_session()
    try:
        return session.query(Leilao).filter(Leilao.id == leilao_id).first()
    finally:
        session.close()


def obter_lotes(leilao_id: int) -> list[Lote]:
    """Retorna lotes de um leilao ordenados por numero."""
    init_db()
    session = get_session()
    try:
        return (
            session.query(Lote)
            .filter(Lote.leilao_id == leilao_id)
            .order_by(Lote.lote_numero)
            .all()
        )
    finally:
        session.close()


def video_ja_processado(url_video: str) -> bool:
    """Verifica se um video ja foi processado."""
    init_db()
    session = get_session()
    try:
        return (
            session.query(Leilao)
            .filter(Leilao.url_video == url_video, Leilao.status == "completo")
            .first()
            is not None
        )
    finally:
        session.close()
