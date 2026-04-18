"""API REST para o dashboard consumir."""

import logging
import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, case

from leilao_inteligente.config import DATA_DIR
from leilao_inteligente.models.database import CotacaoMercado, Leilao, Lote
from leilao_inteligente.storage.db import get_session, init_db

logger = logging.getLogger(__name__)


app = FastAPI(title="Leilao Inteligente API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


# --- Filtros ---


@app.get("/api/filtros")
def get_filtros():
    """Retorna opcoes disponiveis pra cada filtro."""
    session = get_session()
    try:
        racas = [r[0] for r in session.query(Lote.raca).distinct().order_by(Lote.raca).all()]
        sexos = [s[0] for s in session.query(Lote.sexo).distinct().order_by(Lote.sexo).all()]
        estados = [
            e[0] for e in session.query(Leilao.local_estado).filter(Leilao.local_estado.isnot(None)).distinct().order_by(Leilao.local_estado).all()
            if e[0]
        ]
        fazendas = [
            f[0] for f in session.query(Lote.fazenda_vendedor).filter(Lote.fazenda_vendedor.isnot(None)).distinct().order_by(Lote.fazenda_vendedor).all()
            if f[0]
        ]
        cidades = [
            c[0] for c in session.query(Leilao.local_cidade).filter(Leilao.local_cidade.isnot(None)).distinct().order_by(Leilao.local_cidade).all()
            if c[0]
        ]

        leiloes_list = [
            {
                "id": l.id,
                "titulo": l.titulo,
                "local_cidade": l.local_cidade,
                "local_estado": l.local_estado,
                "data": (l.data_leilao or l.processado_em).isoformat() if (l.data_leilao or l.processado_em) else None,
            }
            for l in session.query(Leilao).order_by(Leilao.processado_em.desc()).all()
        ]

        idades = [
            i[0] for i in session.query(Lote.idade_meses)
            .filter(Lote.idade_meses.isnot(None))
            .distinct()
            .order_by(Lote.idade_meses)
            .all()
        ]

        casas_raw = {}
        for l in session.query(Leilao).all():
            if l.titulo and l.titulo not in casas_raw:
                casas_raw[l.titulo] = {"titulo": l.titulo, "local_cidade": l.local_cidade, "local_estado": l.local_estado}
        casas_leilao = sorted(casas_raw.values(), key=lambda c: c["titulo"])

        return {
            "racas": racas,
            "sexos": sexos,
            "estados": estados,
            "cidades": cidades,
            "fazendas": fazendas,
            "leiloes": leiloes_list,
            "casas_leilao": casas_leilao,
            "idades": idades,
        }
    finally:
        session.close()


# --- Lotes com filtros ---


def _aplicar_filtros(
    query, raca=None, sexo=None, idade_min=None, idade_max=None,
    estado=None, cidade=None, fazenda=None, dias=None,
    data_inicio=None, data_fim=None,
    status=None,
    preco_min=None, preco_max=None, qtd_min=None, qtd_max=None,
    leilao_id=None, condicao=None, casa_leilao=None,
    leilao_joined=False,
):
    """Aplica filtros ao query de lotes."""
    joined_leilao = leilao_joined

    if raca:
        query = query.filter(Lote.raca == raca)
    if sexo:
        query = query.filter(Lote.sexo == sexo)
    if condicao:
        query = query.filter(Lote.condicao == condicao)
    if idade_min is not None:
        query = query.filter(Lote.idade_meses >= idade_min)
    if idade_max is not None:
        query = query.filter(Lote.idade_meses <= idade_max)
    if status:
        query = query.filter(Lote.status == status)
    if preco_min is not None:
        query = query.filter(Lote.preco_final >= preco_min)
    if preco_max is not None:
        query = query.filter(Lote.preco_final <= preco_max)
    if qtd_min is not None:
        query = query.filter(Lote.quantidade >= qtd_min)
    if qtd_max is not None:
        query = query.filter(Lote.quantidade <= qtd_max)
    if fazenda:
        query = query.filter(Lote.fazenda_vendedor == fazenda)
    if leilao_id is not None:
        query = query.filter(Lote.leilao_id == leilao_id)
    if estado:
        if not joined_leilao:
            query = query.join(Leilao, isouter=True)
            joined_leilao = True
        query = query.filter(Leilao.local_estado == estado)
    if cidade:
        if not joined_leilao:
            query = query.join(Leilao, isouter=True)
            joined_leilao = True
        query = query.filter(Leilao.local_cidade == cidade)
    if casa_leilao:
        if not joined_leilao:
            query = query.join(Leilao, isouter=True)
            joined_leilao = True
        query = query.filter(Leilao.titulo == casa_leilao)
    data_col = func.coalesce(Leilao.data_leilao, Leilao.processado_em)
    if data_inicio or data_fim:
        if not joined_leilao:
            query = query.join(Leilao, isouter=True)
            joined_leilao = True
        if data_inicio:
            query = query.filter(data_col >= datetime.fromisoformat(data_inicio))
        if data_fim:
            query = query.filter(data_col <= datetime.fromisoformat(data_fim + "T23:59:59"))
    elif dias:
        desde = datetime.utcnow() - timedelta(days=dias)
        if not joined_leilao:
            query = query.join(Leilao, isouter=True)
            joined_leilao = True
        query = query.filter(data_col >= desde)
    return query


@app.get("/api/lotes")
def get_lotes(
    raca: str | None = None,
    sexo: str | None = None,
    idade_min: int | None = None,
    idade_max: int | None = None,
    estado: str | None = None,
    cidade: str | None = None,
    fazenda: str | None = None,
    dias: int | None = None,
    data_inicio: str | None = None,
    data_fim: str | None = None,
    status: str | None = None,
    preco_min: float | None = None,
    preco_max: float | None = None,
    qtd_min: int | None = None,
    qtd_max: int | None = None,
    leilao_id: int | None = None,
    condicao: str | None = None,
    casa_leilao: str | None = None,
    ordenar: str | None = None,
    limite: int = Query(default=5000, le=10000),
):
    """Retorna lotes filtrados."""
    session = get_session()
    try:
        # Eager load leilão para evitar query N+1
        from sqlalchemy.orm import joinedload
        q = session.query(Lote).options(joinedload(Lote.leilao))

        q = _aplicar_filtros(
            q, raca=raca, sexo=sexo, idade_min=idade_min, idade_max=idade_max,
            estado=estado, cidade=cidade, fazenda=fazenda, dias=dias,
            data_inicio=data_inicio, data_fim=data_fim, status=status,
            preco_min=preco_min, preco_max=preco_max, qtd_min=qtd_min, qtd_max=qtd_max,
            leilao_id=leilao_id, condicao=condicao, casa_leilao=casa_leilao,
        )
        q = q.filter(Lote.preco_final > 0)

        # Ordenacao
        if ordenar == "preco_asc":
            q = q.order_by(Lote.preco_final.asc())
        elif ordenar == "preco_desc":
            q = q.order_by(Lote.preco_final.desc())
        elif ordenar == "qtd_desc":
            q = q.order_by(Lote.quantidade.desc())
        else:
            q = q.order_by(Lote.timestamp_inicio.desc())

        q = q.limit(limite)

        lotes = q.all()
        return [_lote_to_dict(l, session) for l in lotes]
    finally:
        session.close()


def _extrair_video_id(url: str) -> str | None:
    """Extrai video ID de uma URL do YouTube."""
    import re
    for pattern in [r"(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})", r"(?:/live/)([a-zA-Z0-9_-]{11})"]:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def _lote_to_dict(lote: Lote, session) -> dict:
    """Converte Lote pra dict serializavel."""
    # Usa o leilão já carregado via joinedload (evita query N+1)
    leilao = lote.leilao if hasattr(lote, 'leilao') and lote.leilao else session.query(Leilao).filter(Leilao.id == lote.leilao_id).first()

    # Montar URL do YouTube com timestamp
    youtube_url = None
    if leilao and leilao.url_video:
        video_id = _extrair_video_id(leilao.url_video)
        if video_id and lote.segundo_video:
            youtube_url = f"https://www.youtube.com/watch?v={video_id}&t={lote.segundo_video}s"
        elif video_id:
            youtube_url = f"https://www.youtube.com/watch?v={video_id}"

    return {
        "id": lote.id,
        "leilao_id": lote.leilao_id,
        "leilao_titulo": leilao.titulo if leilao else None,
        "leilao_data": (leilao.data_leilao or leilao.processado_em).isoformat() if leilao else None,
        "lote_numero": lote.lote_numero,
        "quantidade": lote.quantidade,
        "raca": lote.raca,
        "sexo": lote.sexo,
        "condicao": lote.condicao,
        "idade_meses": lote.idade_meses,
        "pelagem": lote.pelagem,
        "preco_inicial": float(lote.preco_inicial) if lote.preco_inicial else None,
        "preco_final": float(lote.preco_final) if lote.preco_final else None,
        "preco_por_cabeca": float(lote.preco_por_cabeca) if lote.preco_por_cabeca else None,
        "fazenda_vendedor": lote.fazenda_vendedor,
        "local_cidade": getattr(leilao, "local_cidade", None) if leilao else None,
        "local_estado": getattr(leilao, "local_estado", None) if leilao else None,
        "timestamp_video_inicio": lote.timestamp_video_inicio.isoformat() if lote.timestamp_video_inicio else None,
        "status": lote.status,
        "aparicoes": lote.aparicoes,
        "confianca_media": lote.confianca_media,
        "frame_paths": lote.frame_paths.split("|") if lote.frame_paths else [],
        "youtube_url": youtube_url,
        "revisar": bool(lote.revisar) if lote.revisar else False,
    }


# --- Metricas / Cards ---


@app.get("/api/metricas")
def get_metricas(
    raca: str | None = None,
    sexo: str | None = None,
    idade_min: int | None = None,
    idade_max: int | None = None,
    estado: str | None = None,
    fazenda: str | None = None,
    dias: int | None = None,
    leilao_id: int | None = None,
    condicao: str | None = None,
    casa_leilao: str | None = None,
):
    """Retorna metricas resumidas (media, min, max, total)."""
    session = get_session()
    try:
        q = session.query(
            func.avg(Lote.preco_final).label("media"),
            func.min(Lote.preco_final).label("minimo"),
            func.max(Lote.preco_final).label("maximo"),
            func.count(Lote.id).label("total_lotes"),
            func.sum(Lote.quantidade).label("total_cabecas"),
        )

        q = _aplicar_filtros(q, raca=raca, sexo=sexo, idade_min=idade_min, idade_max=idade_max, estado=estado, fazenda=fazenda, dias=dias, leilao_id=leilao_id, condicao=condicao, casa_leilao=casa_leilao)
        q = q.filter(Lote.preco_final > 0)

        result = q.one()

        # Tendencia: comparar media atual vs periodo anterior
        tendencia = None
        if dias:
            meio = datetime.utcnow() - timedelta(days=dias // 2)
            desde = datetime.utcnow() - timedelta(days=dias)

            data_col = func.coalesce(Leilao.data_leilao, Leilao.processado_em)

            q_recente = session.query(func.avg(Lote.preco_final))
            q_recente = q_recente.join(Leilao).filter(data_col >= meio)
            q_recente = _aplicar_filtros(q_recente, raca=raca, sexo=sexo, idade_min=idade_min, idade_max=idade_max, estado=estado, fazenda=fazenda, leilao_id=leilao_id, condicao=condicao, casa_leilao=casa_leilao, leilao_joined=True)
            q_recente = q_recente.filter(Lote.preco_final > 0)
            media_recente = q_recente.scalar()

            q_antigo = session.query(func.avg(Lote.preco_final))
            q_antigo = q_antigo.join(Leilao).filter(
                data_col >= desde,
                data_col < meio,
            )
            q_antigo = _aplicar_filtros(q_antigo, raca=raca, sexo=sexo, idade_min=idade_min, idade_max=idade_max, estado=estado, fazenda=fazenda, leilao_id=leilao_id, condicao=condicao, casa_leilao=casa_leilao, leilao_joined=True)
            q_antigo = q_antigo.filter(Lote.preco_final > 0)
            media_antiga = q_antigo.scalar()

            if media_recente and media_antiga and media_antiga > 0:
                tendencia = float((media_recente - media_antiga) / media_antiga * 100)

        return {
            "media": round(float(result.media), 2) if result.media else None,
            "minimo": round(float(result.minimo), 2) if result.minimo else None,
            "maximo": round(float(result.maximo), 2) if result.maximo else None,
            "total_lotes": result.total_lotes or 0,
            "total_cabecas": result.total_cabecas or 0,
            "tendencia_percentual": round(tendencia, 1) if tendencia else None,
        }
    finally:
        session.close()


# --- Tendencia (grafico) ---


@app.get("/api/tendencia")
def get_tendencia(
    raca: str | None = None,
    sexo: str | None = None,
    idade_min: int | None = None,
    idade_max: int | None = None,
    estado: str | None = None,
    cidade: str | None = None,
    fazenda: str | None = None,
    status: str | None = None,
    condicao: str | None = None,
    casa_leilao: str | None = None,
    dias: int = 90,
):
    """Retorna dados pra grafico de tendencia (media por leilao)."""
    session = get_session()
    try:
        desde = datetime.utcnow() - timedelta(days=dias)

        q = session.query(
            func.coalesce(Leilao.data_leilao, Leilao.processado_em).label("data"),
            Leilao.titulo.label("leilao"),
            func.avg(Lote.preco_final).label("media"),
            func.count(Lote.id).label("lotes"),
        ).join(Leilao)

        q = _aplicar_filtros(
            q, raca=raca, sexo=sexo, idade_min=idade_min, idade_max=idade_max,
            estado=estado, cidade=cidade, fazenda=fazenda, status=status, condicao=condicao,
            leilao_joined=True,
        )
        q = q.filter(Lote.preco_final > 0)
        q = q.filter(func.coalesce(Leilao.data_leilao, Leilao.processado_em) >= desde)
        if casa_leilao:
            q = q.filter(Leilao.titulo == casa_leilao)
        q = q.group_by(Leilao.id)
        q = q.order_by(func.coalesce(Leilao.data_leilao, Leilao.processado_em))

        pontos = []
        for row in q.all():
            pontos.append({
                "data": row.data.isoformat() if row.data else None,
                "leilao": row.leilao,
                "media": round(float(row.media), 2),
                "lotes": row.lotes,
            })

        return pontos
    finally:
        session.close()


# --- Fazendas ranking ---


@app.get("/api/fazendas")
def get_fazendas(
    raca: str | None = None,
    sexo: str | None = None,
    idade_min: int | None = None,
    idade_max: int | None = None,
    estado: str | None = None,
    dias: int | None = None,
    limite: int = 20,
):
    """Ranking de fazendas por preco medio."""
    session = get_session()
    try:
        q = session.query(
            Lote.fazenda_vendedor.label("fazenda"),
            func.avg(Lote.preco_final).label("media"),
            func.count(Lote.id).label("lotes"),
            func.sum(Lote.quantidade).label("cabecas"),
        )

        q = _aplicar_filtros(q, raca=raca, sexo=sexo, idade_min=idade_min, idade_max=idade_max, estado=estado, dias=dias)
        q = q.filter(Lote.preco_final > 0)
        q = q.filter(Lote.fazenda_vendedor.isnot(None))
        q = q.group_by(Lote.fazenda_vendedor)
        q = q.order_by(func.count(Lote.id).desc())
        q = q.limit(limite)

        return [
            {
                "fazenda": row.fazenda,
                "media": round(float(row.media), 2),
                "lotes": row.lotes,
                "cabecas": row.cabecas,
            }
            for row in q.all()
        ]
    finally:
        session.close()


# --- Regioes ---


@app.get("/api/regioes")
def get_regioes(
    raca: str | None = None,
    sexo: str | None = None,
    idade_min: int | None = None,
    idade_max: int | None = None,
    dias: int | None = None,
):
    """Media por estado."""
    session = get_session()
    try:
        q = session.query(
            Leilao.local_estado.label("estado"),
            func.avg(Lote.preco_final).label("media"),
            func.count(Lote.id).label("lotes"),
        ).join(Leilao)

        q = _aplicar_filtros(q, raca=raca, sexo=sexo, idade_min=idade_min, idade_max=idade_max, leilao_joined=True)
        q = q.filter(Lote.preco_final > 0)
        q = q.filter(Leilao.local_estado.isnot(None))
        if dias:
            desde = datetime.utcnow() - timedelta(days=dias)
            q = q.filter(func.coalesce(Leilao.data_leilao, Leilao.processado_em) >= desde)
        q = q.group_by(Leilao.local_estado)
        q = q.order_by(func.count(Lote.id).desc())

        return [
            {
                "estado": row.estado,
                "media": round(float(row.media), 2),
                "lotes": row.lotes,
            }
            for row in q.all()
        ]
    finally:
        session.close()


# --- Leiloes processados ---


@app.get("/api/leiloes")
def get_leiloes():
    """Lista todos os leiloes processados."""
    session = get_session()
    try:
        leiloes = (
            session.query(Leilao)
            .order_by(Leilao.processado_em.desc())
            .all()
        )
        return [
            {
                "id": l.id,
                "titulo": l.titulo,
                "canal": l.canal_youtube,
                "local_cidade": l.local_cidade,
                "local_estado": l.local_estado,
                "total_lotes": l.total_lotes,
                "processado_em": (l.data_leilao or l.processado_em).isoformat() if (l.data_leilao or l.processado_em) else None,
                "status": l.status,
            }
            for l in leiloes
        ]
    finally:
        session.close()


class LeilaoUpdate(BaseModel):
    titulo: str | None = None
    canal_youtube: str | None = None
    local_cidade: str | None = None
    local_estado: str | None = None
    data_leilao: str | None = None


@app.patch("/api/leiloes/{leilao_id}")
def patch_leilao_info(leilao_id: int, update: LeilaoUpdate):
    """Atualiza campos de um leilão processado."""
    session = get_session()
    try:
        leilao = session.query(Leilao).filter(Leilao.id == leilao_id).first()
        if not leilao:
            return JSONResponse({"error": "Leilão não encontrado"}, status_code=404)

        for campo, valor in update.model_dump(exclude_none=True).items():
            if campo == "data_leilao" and valor:
                setattr(leilao, campo, datetime.fromisoformat(valor))
            else:
                setattr(leilao, campo, valor)

        session.commit()
        return {"id": leilao.id, "ok": True}
    finally:
        session.close()


# --- Comparativo ---


def _query_medias(
    session, cidade=None, leilao_id=None, dias=None,
    raca=None, sexo=None, condicao=None,
    idade_min=None, idade_max=None, estado=None,
    preco_min=None, preco_max=None,
):
    """Consulta médias agrupadas por categoria (idade exata).

    Filtra por cidade OU por leilao_id especifico.
    """
    q = session.query(
        Lote.raca.label("raca"),
        Lote.sexo.label("sexo"),
        Lote.condicao.label("condicao"),
        Lote.idade_meses.label("idade_meses"),
        func.avg(Lote.preco_final).label("media"),
        func.min(Lote.preco_final).label("minimo"),
        func.max(Lote.preco_final).label("maximo"),
        func.count(Lote.id).label("lotes"),
    ).join(Leilao)

    if leilao_id is not None:
        q = q.filter(Lote.leilao_id == leilao_id)
    elif cidade:
        q = q.filter(Leilao.local_cidade == cidade)

    q = q.filter(Lote.preco_final > 0)
    q = q.filter(Lote.idade_meses.isnot(None))

    if raca:
        q = q.filter(Lote.raca == raca)
    if sexo:
        q = q.filter(Lote.sexo == sexo)
    if condicao:
        q = q.filter(Lote.condicao == condicao)
    if idade_min is not None:
        q = q.filter(Lote.idade_meses >= idade_min)
    if idade_max is not None:
        q = q.filter(Lote.idade_meses <= idade_max)
    if estado:
        q = q.filter(Leilao.local_estado == estado)
    if preco_min is not None:
        q = q.filter(Lote.preco_final >= preco_min)
    if preco_max is not None:
        q = q.filter(Lote.preco_final <= preco_max)
    if dias and leilao_id is None:
        desde = datetime.utcnow() - timedelta(days=dias)
        q = q.filter(func.coalesce(Leilao.data_leilao, Leilao.processado_em) >= desde)

    q = q.group_by(Lote.raca, Lote.sexo, Lote.condicao, Lote.idade_meses)
    return q.all()


@app.get("/api/comparativo/cidades")
def get_comparativo_cidades(
    cidade_a: str | None = None,
    cidade_b: str | None = None,
    leilao_id_a: int | None = None,
    leilao_id_b: int | None = None,
    raca: str | None = None,
    sexo: str | None = None,
    condicao: str | None = None,
    idade_min: int | None = None,
    idade_max: int | None = None,
    estado: str | None = None,
    preco_min: float | None = None,
    preco_max: float | None = None,
    dias: int = 90,
):
    """Compara preços médios entre duas cidades ou dois leilões por categoria."""
    session = get_session()
    try:
        filtros_extra = dict(idade_min=idade_min, idade_max=idade_max, estado=estado, preco_min=preco_min, preco_max=preco_max)
        dados_a = _query_medias(session, cidade=cidade_a, leilao_id=leilao_id_a, dias=dias, raca=raca, sexo=sexo, condicao=condicao, **filtros_extra)
        dados_b = _query_medias(session, cidade=cidade_b, leilao_id=leilao_id_b, dias=dias, raca=raca, sexo=sexo, condicao=condicao, **filtros_extra)

        # Indexar por chave de categoria (idade exata)
        def _key(row):
            return (row.raca, row.sexo, row.condicao or "", row.idade_meses)

        mapa_a = {_key(r): r for r in dados_a}
        mapa_b = {_key(r): r for r in dados_b}

        todas_chaves = set(mapa_a.keys()) | set(mapa_b.keys())

        categorias = []
        for chave in sorted(todas_chaves):
            a = mapa_a.get(chave)
            b = mapa_b.get(chave)
            media_a = round(float(a.media), 2) if a else None
            media_b = round(float(b.media), 2) if b else None

            diff = None
            diff_pct = None
            if media_a is not None and media_b is not None:
                diff = round(media_b - media_a, 2)
                if media_a > 0:
                    diff_pct = round((media_b - media_a) / media_a * 100, 1)

            categorias.append({
                "raca": chave[0],
                "sexo": chave[1],
                "condicao": chave[2] or None,
                "idade_meses": chave[3],
                "media_a": media_a,
                "media_b": media_b,
                "diff": diff,
                "diff_pct": diff_pct,
                "lotes_a": a.lotes if a else 0,
                "lotes_b": b.lotes if b else 0,
            })

        # Montar labels: se filtrou por leilao, usar titulo; senao, cidade
        label_a = cidade_a or ""
        label_b = cidade_b or ""
        if leilao_id_a is not None:
            leilao_a = session.query(Leilao).filter(Leilao.id == leilao_id_a).first()
            if leilao_a:
                label_a = leilao_a.titulo or f"Leilão #{leilao_id_a}"
        if leilao_id_b is not None:
            leilao_b = session.query(Leilao).filter(Leilao.id == leilao_id_b).first()
            if leilao_b:
                label_b = leilao_b.titulo or f"Leilão #{leilao_id_b}"

        return {
            "label_a": label_a,
            "label_b": label_b,
            "categorias": categorias,
        }
    finally:
        session.close()


@app.get("/api/ranking")
def get_ranking(
    raca: str | None = None,
    sexo: str | None = None,
    condicao: str | None = None,
    idade_min: int | None = None,
    idade_max: int | None = None,
    estado: str | None = None,
    cidade: str | None = None,
    data_inicio: str | None = None,
    data_fim: str | None = None,
):
    """Ranking de preços por categoria entre todos os leilões filtrados.

    Retorna para cada categoria (raça+sexo+condição+idade) o preço médio
    em cada leilão, ordenado do mais barato ao mais caro.
    """
    session = get_session()
    try:
        q = session.query(
            Lote.raca,
            Lote.sexo,
            Lote.condicao,
            Lote.idade_meses,
            Lote.leilao_id,
            func.avg(Lote.preco_final).label("media"),
            func.count(Lote.id).label("lotes"),
        ).join(Leilao)

        q = q.filter(Lote.preco_final > 0)
        q = q.filter(Lote.idade_meses.isnot(None))

        if raca:
            q = q.filter(Lote.raca == raca)
        if sexo:
            q = q.filter(Lote.sexo == sexo)
        if condicao:
            q = q.filter(Lote.condicao == condicao)
        if idade_min is not None:
            q = q.filter(Lote.idade_meses >= idade_min)
        if idade_max is not None:
            q = q.filter(Lote.idade_meses <= idade_max)
        if estado:
            q = q.filter(Leilao.local_estado == estado)
        if cidade:
            q = q.filter(Leilao.local_cidade == cidade)
        if data_inicio:
            q = q.filter(Leilao.data_leilao >= datetime.fromisoformat(data_inicio))
        if data_fim:
            q = q.filter(Leilao.data_leilao <= datetime.fromisoformat(data_fim + "T23:59:59"))

        q = q.group_by(Lote.raca, Lote.sexo, Lote.condicao, Lote.idade_meses, Lote.leilao_id)
        rows = q.all()

        # Montar mapa de leilões
        leilao_ids = {r.leilao_id for r in rows}
        leiloes_map: dict[int, dict] = {}
        for lid in leilao_ids:
            leilao = session.query(Leilao).filter(Leilao.id == lid).first()
            if leilao:
                leiloes_map[lid] = {
                    "id": leilao.id,
                    "titulo": leilao.titulo,
                    "cidade": leilao.local_cidade,
                    "estado": leilao.local_estado,
                    "data": (leilao.data_leilao or leilao.processado_em).isoformat() if (leilao.data_leilao or leilao.processado_em) else None,
                }

        # Agrupar por categoria
        categorias: dict[tuple, list] = {}
        for r in rows:
            key = (r.raca, r.sexo, r.condicao or "", r.idade_meses)
            if key not in categorias:
                categorias[key] = []
            categorias[key].append({
                "leilao_id": r.leilao_id,
                "media": round(float(r.media), 2),
                "lotes": r.lotes,
            })

        # Ordenar preços dentro de cada categoria (mais barato primeiro)
        resultado = []
        for key in sorted(categorias.keys()):
            precos = sorted(categorias[key], key=lambda x: x["media"])
            spread = precos[-1]["media"] - precos[0]["media"] if len(precos) > 1 else 0
            resultado.append({
                "raca": key[0],
                "sexo": key[1],
                "condicao": key[2] or None,
                "idade_meses": key[3],
                "precos": precos,
                "spread": round(spread, 2),
            })

        # Filtrar: só categorias com 2+ leilões (senão não tem comparação)
        resultado = [r for r in resultado if len(r["precos"]) >= 2]

        # Ordenar por maior spread (melhores oportunidades primeiro)
        resultado.sort(key=lambda x: x["spread"], reverse=True)

        return {
            "leiloes": leiloes_map,
            "categorias": resultado,
        }
    finally:
        session.close()


@app.get("/api/comparativo/lotes")
def get_comparativo_lotes(
    leilao_id_a: int = Query(...),
    leilao_id_b: int = Query(...),
    raca: str = Query(...),
    sexo: str = Query(...),
    idade_meses: int = Query(...),
    condicao: str | None = None,
):
    """Retorna lotes individuais de ambos os leiloes para uma categoria especifica."""
    session = get_session()
    try:
        def _buscar_lotes(leilao_id: int):
            q = session.query(Lote).filter(
                Lote.leilao_id == leilao_id,
                Lote.raca == raca,
                Lote.sexo == sexo,
                Lote.idade_meses == idade_meses,
                Lote.preco_final > 0,
            )
            if condicao:
                q = q.filter(Lote.condicao == condicao)
            else:
                q = q.filter(Lote.condicao.is_(None))
            return q.order_by(Lote.preco_final).all()

        lotes_a = _buscar_lotes(leilao_id_a)
        lotes_b = _buscar_lotes(leilao_id_b)

        def _video_id_for(leilao_id: int) -> str | None:
            leilao = session.query(Leilao).filter(Leilao.id == leilao_id).first()
            return _extrair_video_id(leilao.url_video) if leilao and leilao.url_video else None

        vid_a = _video_id_for(leilao_id_a)
        vid_b = _video_id_for(leilao_id_b)

        def _lote_resumo(lote: Lote, video_id: str | None) -> dict:
            return {
                "id": lote.id,
                "lote_numero": lote.lote_numero,
                "quantidade": lote.quantidade,
                "preco_final": float(lote.preco_final) if lote.preco_final else None,
                "fazenda_vendedor": lote.fazenda_vendedor,
                "status": lote.status,
                "youtube_url": f"https://www.youtube.com/watch?v={video_id}&t={lote.segundo_video}s" if video_id and lote.segundo_video else None,
            }

        return {
            "lotes_a": [_lote_resumo(l, vid_a) for l in lotes_a],
            "lotes_b": [_lote_resumo(l, vid_b) for l in lotes_b],
        }
    finally:
        session.close()


@app.get("/api/ranking/lotes")
def get_ranking_lotes(
    leilao_ids: str = Query(..., description="IDs separados por virgula"),
    raca: str = Query(...),
    sexo: str = Query(...),
    idade_meses: int = Query(...),
    condicao: str | None = None,
):
    """Retorna lotes individuais de N leiloes para uma categoria."""
    session = get_session()
    try:
        ids = [int(x.strip()) for x in leilao_ids.split(",") if x.strip()]
        resultado: dict[int, list[dict]] = {}

        for lid in ids:
            q = session.query(Lote).filter(
                Lote.leilao_id == lid,
                Lote.raca == raca,
                Lote.sexo == sexo,
                Lote.idade_meses == idade_meses,
                Lote.preco_final > 0,
            )
            if condicao:
                q = q.filter(Lote.condicao == condicao)
            else:
                q = q.filter(Lote.condicao.is_(None))

            lotes = q.order_by(Lote.preco_final).all()
            leilao = session.query(Leilao).filter(Leilao.id == lid).first()
            video_id = _extrair_video_id(leilao.url_video) if leilao and leilao.url_video else None

            resultado[lid] = [
                {
                    "id": l.id,
                    "lote_numero": l.lote_numero,
                    "quantidade": l.quantidade,
                    "preco_final": float(l.preco_final) if l.preco_final else None,
                    "fazenda_vendedor": l.fazenda_vendedor,
                    "status": l.status,
                    "youtube_url": f"https://www.youtube.com/watch?v={video_id}&t={l.segundo_video}s" if video_id and l.segundo_video else None,
                }
                for l in lotes
            ]

        return resultado
    finally:
        session.close()


@app.get("/api/comparativo/evolucao")
def get_comparativo_evolucao(
    cidade: str = Query(...),
    raca: str | None = None,
    sexo: str | None = None,
    condicao: str | None = None,
    idade_min: int | None = None,
    idade_max: int | None = None,
    dias: int = 180,
):
    """Evolução de preço de uma categoria ao longo dos leilões numa cidade."""
    session = get_session()
    try:
        q = session.query(
            Leilao.processado_em.label("data"),
            Leilao.titulo.label("leilao"),
            func.avg(Lote.preco_final).label("media"),
            func.min(Lote.preco_final).label("minimo"),
            func.max(Lote.preco_final).label("maximo"),
            func.count(Lote.id).label("lotes"),
        ).join(Leilao)

        q = q.filter(Leilao.local_cidade == cidade)
        q = q.filter(Lote.preco_final > 0)

        if raca:
            q = q.filter(Lote.raca == raca)
        if sexo:
            q = q.filter(Lote.sexo == sexo)
        if condicao:
            q = q.filter(Lote.condicao == condicao)
        if idade_min is not None:
            q = q.filter(Lote.idade_meses >= idade_min)
        if idade_max is not None:
            q = q.filter(Lote.idade_meses <= idade_max)
        if dias:
            desde = datetime.utcnow() - timedelta(days=dias)
            q = q.filter(func.coalesce(Leilao.data_leilao, Leilao.processado_em) >= desde)

        q = q.group_by(Leilao.id)
        q = q.order_by(Leilao.processado_em)

        return [
            {
                "data": row.data.isoformat() if row.data else None,
                "leilao": row.leilao,
                "media": round(float(row.media), 2),
                "minimo": round(float(row.minimo), 2),
                "maximo": round(float(row.maximo), 2),
                "lotes": row.lotes,
            }
            for row in q.all()
        ]
    finally:
        session.close()


# --- Processamento de videos ---


class ProcessarRequest(BaseModel):
    url: str
    batch: bool = False


_jobs_cancelados: set[str] = set()


def _job_cancelado(job_id: str) -> bool:
    """Verifica se um job foi cancelado."""
    return job_id in _jobs_cancelados


def _atualizar_job(job_id: str, **kwargs: object) -> None:
    """Atualiza campos de um job de processamento no banco."""
    session = get_session()
    try:
        from leilao_inteligente.models.database import Processamento
        job = session.query(Processamento).filter(Processamento.id == job_id).first()
        if job:
            for k, v in kwargs.items():
                setattr(job, k, v)
            session.commit()
    finally:
        session.close()


def _executar_processamento(job_id: str, url: str, batch: bool) -> None:
    """Executa o pipeline de processamento em background thread."""
    from leilao_inteligente.models.schemas import LeilaoInfo
    from leilao_inteligente.pipeline.downloader import obter_info_video, extrair_data_leilao, extrair_local_leilao
    from leilao_inteligente.pipeline.processor import processar_video
    from leilao_inteligente.storage.repository import salvar_leilao

    try:
        if _job_cancelado(job_id):
            return

        _atualizar_job(job_id, status="baixando")
        from leilao_inteligente.config import get_settings as _get_settings
        _settings = _get_settings()
        info = obter_info_video(url, cookies_file=_settings.cookies_path)

        if _job_cancelado(job_id):
            return

        canal = str(info.get("channel", ""))
        _atualizar_job(job_id, status="processando", titulo=str(info.get("title", "")))

        # Buscar prompt calibrado para o canal (se existir)
        prompt_cal = None
        try:
            from leilao_inteligente.pipeline.calibration import obter_calibracao, montar_prompt_gemini
            cal = obter_calibracao(canal)
            if cal:
                prompt_cal = montar_prompt_gemini(cal)
                logger.info("Usando prompt calibrado para canal '%s'", canal)
        except Exception:
            pass

        def _progress_cb(fase: str) -> None:
            _atualizar_job(job_id, status=fase)

        lotes = processar_video(url, batch=batch, on_progress=_progress_cb, canal_youtube=canal, prompt_calibrado=prompt_cal)

        if _job_cancelado(job_id):
            return

        if not lotes:
            _atualizar_job(job_id, status="concluido", lotes=0)
            return

        cidade, estado = extrair_local_leilao(info)
        leilao_info = LeilaoInfo(
            canal_youtube=str(info.get("channel", "Desconhecido")),
            url_video=url,
            titulo=str(info.get("title", "Sem titulo")),
            data_leilao=extrair_data_leilao(info),
            local_cidade=cidade,
            local_estado=estado,
        )
        leilao = salvar_leilao(leilao_info, lotes)

        _atualizar_job(job_id, status="concluido", lotes=len(lotes), leilao_id=leilao.id)

    except Exception as e:
        logger.exception("Erro no processamento %s", job_id)
        _atualizar_job(job_id, status="erro", erro=str(e)[:1000])


@app.post("/api/processar")
def post_processar(req: ProcessarRequest):
    """Inicia processamento de um video em background."""
    import uuid
    from leilao_inteligente.models.database import Processamento

    job_id = uuid.uuid4().hex[:12]

    session = get_session()
    try:
        job = Processamento(id=job_id, url=req.url, batch=int(req.batch), status="iniciando")
        session.add(job)
        session.commit()
    finally:
        session.close()

    thread = threading.Thread(
        target=_executar_processamento,
        args=(job_id, req.url, req.batch),
        daemon=True,
    )
    thread.start()

    modo = "batch (50% desconto)" if req.batch else "online"
    return {"job_id": job_id, "status": "iniciando", "modo": modo}


@app.get("/api/processar")
def get_processamentos_ativos():
    """Retorna todos os jobs de processamento (ativos e recentes)."""
    from leilao_inteligente.models.database import Processamento

    session = get_session()
    try:
        jobs = session.query(Processamento).order_by(Processamento.criado_em.desc()).limit(10).all()
        return {j.id: j.to_dict() for j in jobs}
    finally:
        session.close()


@app.get("/api/processar/{job_id}")
def get_processamento_status(job_id: str):
    """Retorna status de um processamento em andamento."""
    from leilao_inteligente.models.database import Processamento

    session = get_session()
    try:
        job = session.query(Processamento).filter(Processamento.id == job_id).first()
        if not job:
            return JSONResponse({"error": "Job nao encontrado"}, status_code=404)
        return job.to_dict()
    finally:
        session.close()


@app.delete("/api/processar/finalizados")
def delete_processamentos_finalizados():
    """Remove todos os jobs finalizados (concluido, erro, cancelado)."""
    from leilao_inteligente.models.database import Processamento

    session = get_session()
    try:
        removidos = (
            session.query(Processamento)
            .filter(Processamento.status.in_(["concluido", "erro", "cancelado"]))
            .delete(synchronize_session="fetch")
        )
        session.commit()
        return {"removidos": removidos}
    finally:
        session.close()


@app.delete("/api/processar/{job_id}")
def delete_processamento(job_id: str):
    """Cancela um processamento em andamento."""
    from leilao_inteligente.models.database import Processamento

    _jobs_cancelados.add(job_id)
    _atualizar_job(job_id, status="cancelado", erro="Cancelado pelo usuário")

    return {"id": job_id, "status": "cancelado"}


# --- Cookies YouTube ---


@app.post("/api/cookies")
async def upload_cookies(request: Request):
    """Atualiza cookies do YouTube — salva no banco (persiste entre restarts)."""
    import os
    from leilao_inteligente.models.database import Configuracao
    from datetime import datetime

    body = await request.body()
    if not body:
        return JSONResponse({"error": "Body vazio"}, status_code=400)

    body_text = body.decode("utf-8", errors="replace")

    # 1. Salvar no banco (persistente)
    session = get_session()
    try:
        existing = session.query(Configuracao).filter(Configuracao.chave == "youtube_cookies").first()
        if existing:
            existing.valor = body_text
            existing.atualizado_em = datetime.utcnow()
        else:
            session.add(Configuracao(chave="youtube_cookies", valor=body_text, atualizado_em=datetime.utcnow()))
        session.commit()
    finally:
        session.close()

    # 2. Salvar em arquivo local tambem (para uso imediato)
    cookies_path = "/app/cookies.txt" if os.path.exists("/app") else str(DATA_DIR / "cookies.txt")
    with open(cookies_path, "wb") as f:
        f.write(body)

    logger.info("Cookies YouTube atualizados e persistidos no banco (%d bytes)", len(body))
    return {"status": "ok", "bytes": len(body)}


@app.get("/api/cookies/status")
def get_cookies_status():
    """Verifica se cookies do YouTube estao configurados."""
    from leilao_inteligente.models.database import Configuracao

    session = get_session()
    try:
        config = session.query(Configuracao).filter(Configuracao.chave == "youtube_cookies").first()
        if config and config.valor:
            return {
                "configurado": True,
                "bytes": len(config.valor),
                "atualizado_em": config.atualizado_em.isoformat() if config.atualizado_em else None,
            }
    finally:
        session.close()
    return {"configurado": False}


# --- Frames visuais ---


class LoteUpdate(BaseModel):
    lote_numero: str | None = None
    quantidade: int | None = None
    raca: str | None = None
    sexo: str | None = None
    condicao: str | None = None
    idade_meses: int | None = None
    fazenda_vendedor: str | None = None
    preco_inicial: float | None = None
    preco_final: float | None = None
    status: str | None = None
    revisar: bool | None = None


@app.patch("/api/lotes/{lote_id}")
def patch_lote(lote_id: int, update: LoteUpdate):
    """Atualiza qualquer campo de um lote (edição manual)."""
    session = get_session()
    try:
        lote = session.query(Lote).filter(Lote.id == lote_id).first()
        if not lote:
            return JSONResponse({"error": "Lote não encontrado"}, status_code=404)

        for campo, valor in update.model_dump(exclude_none=True).items():
            if campo == "revisar":
                setattr(lote, campo, int(valor))
            else:
                setattr(lote, campo, valor)

        session.commit()
        return {"id": lote.id, "ok": True}
    finally:
        session.close()


@app.get("/api/frame/{path:path}")
def get_frame(path: str):
    """Serve um frame visual do gado."""
    file_path = (DATA_DIR / path).resolve()
    if not file_path.is_relative_to(DATA_DIR.resolve()):
        return JSONResponse({"error": "Acesso negado"}, status_code=403)
    if not file_path.exists():
        return JSONResponse({"error": "Frame nao encontrado"}, status_code=404)
    return FileResponse(file_path)


# --- Mercado (cotações de referência) ---


@app.get("/api/mercado/cotacoes")
def get_mercado_cotacoes(
    estado: str | None = None,
    categoria: str | None = None,
    fonte: str | None = None,
    raca: str | None = None,
    dias: int = 7,
):
    """Lista cotações de mercado com filtros."""
    session = get_session()
    try:
        desde = datetime.utcnow() - timedelta(days=dias)
        q = session.query(CotacaoMercado).filter(CotacaoMercado.data >= desde.date())

        if estado:
            q = q.filter(CotacaoMercado.estado == estado)
        if categoria:
            q = q.filter(CotacaoMercado.categoria == categoria)
        if fonte:
            q = q.filter(CotacaoMercado.fonte == fonte)
        if raca:
            q = q.filter(CotacaoMercado.raca == raca)

        q = q.order_by(CotacaoMercado.data.desc(), CotacaoMercado.estado)
        rows = q.limit(2000).all()

        return [
            {
                "id": r.id,
                "data": r.data.isoformat() if r.data else None,
                "estado": r.estado,
                "praca": r.praca,
                "categoria": r.categoria,
                "raca": r.raca,
                "sexo": r.sexo,
                "valor": float(r.valor),
                "unidade": r.unidade,
                "fonte": r.fonte,
            }
            for r in rows
        ]
    finally:
        session.close()


@app.get("/api/mercado/resumo")
def get_mercado_resumo(
    estado: str | None = None,
    categoria: str | None = None,
):
    """Resumo de cotações por estado e categoria (último dia disponível)."""
    session = get_session()
    try:
        # Última data disponível
        ultima_data = session.query(func.max(CotacaoMercado.data)).scalar()
        if not ultima_data:
            return {"data": None, "cotacoes": []}

        q = session.query(
            CotacaoMercado.estado,
            CotacaoMercado.categoria,
            CotacaoMercado.raca,
            CotacaoMercado.sexo,
            CotacaoMercado.unidade,
            CotacaoMercado.fonte,
            func.avg(CotacaoMercado.valor).label("media"),
            func.min(CotacaoMercado.valor).label("minimo"),
            func.max(CotacaoMercado.valor).label("maximo"),
            func.count(CotacaoMercado.id).label("pracas"),
        ).filter(CotacaoMercado.data == ultima_data)

        if estado:
            q = q.filter(CotacaoMercado.estado == estado)
        if categoria:
            q = q.filter(CotacaoMercado.categoria == categoria)

        q = q.group_by(
            CotacaoMercado.estado, CotacaoMercado.categoria,
            CotacaoMercado.raca, CotacaoMercado.sexo,
            CotacaoMercado.unidade, CotacaoMercado.fonte,
        )
        q = q.order_by(CotacaoMercado.estado, CotacaoMercado.categoria)

        cotacoes = []
        for r in q.all():
            cotacoes.append({
                "estado": r.estado,
                "categoria": r.categoria,
                "raca": r.raca,
                "sexo": r.sexo,
                "unidade": r.unidade,
                "fonte": r.fonte,
                "media": round(float(r.media), 2),
                "minimo": round(float(r.minimo), 2),
                "maximo": round(float(r.maximo), 2),
                "pracas": r.pracas,
            })

        return {"data": ultima_data.isoformat(), "cotacoes": cotacoes}
    finally:
        session.close()


@app.get("/api/mercado/filtros")
def get_mercado_filtros():
    """Retorna opções de filtro disponíveis para cotações de mercado."""
    session = get_session()
    try:
        estados = [r[0] for r in session.query(CotacaoMercado.estado).distinct().order_by(CotacaoMercado.estado).all()]
        categorias = [r[0] for r in session.query(CotacaoMercado.categoria).distinct().order_by(CotacaoMercado.categoria).all()]
        fontes = [r[0] for r in session.query(CotacaoMercado.fonte).distinct().order_by(CotacaoMercado.fonte).all()]
        racas = [r[0] for r in session.query(CotacaoMercado.raca).distinct().order_by(CotacaoMercado.raca).all()]

        return {
            "estados": estados,
            "categorias": categorias,
            "fontes": fontes,
            "racas": racas,
        }
    finally:
        session.close()


@app.get("/api/mercado/tendencia")
def get_mercado_tendencia(
    estado: str | None = None,
    categoria: str = "boi_gordo",
    fonte: str | None = None,
):
    """Análise de tendência de mercado com regressão linear em múltiplas janelas."""
    from leilao_inteligente.market.tendencia import analisar_tendencia_mercado
    return analisar_tendencia_mercado(estado=estado, categoria=categoria, fonte=fonte)


@app.get("/api/mercado/tendencia/resumo")
def get_mercado_tendencia_resumo(estado: str | None = None):
    """Resumo de tendência para as principais categorias."""
    from leilao_inteligente.market.tendencia import resumo_tendencias
    return resumo_tendencias(estado=estado)


@app.post("/api/mercado/atualizar")
def post_mercado_atualizar():
    """Dispara coleta de cotações de mercado (todas as fontes)."""
    from leilao_inteligente.market.collector import atualizar_mercado

    try:
        resultado = atualizar_mercado()
        return resultado
    except Exception as e:
        logger.exception("Erro atualizando mercado")
        return JSONResponse({"error": str(e)}, status_code=500)


# ============================================================
# AO VIVO
# ============================================================

_sessao_ao_vivo: object = None  # SessaoAoVivo | None


class ConectarAoVivoRequest(BaseModel):
    url: str


@app.post("/api/ao-vivo/conectar")
def post_ao_vivo_conectar(req: ConectarAoVivoRequest):
    """Valida URL e cria sessão ao vivo (estado CONECTADO)."""
    global _sessao_ao_vivo
    import uuid
    from leilao_inteligente.pipeline.ao_vivo import SessaoAoVivo, validar_live
    from leilao_inteligente.pipeline.calibration import obter_calibracao

    info = validar_live(req.url)
    if info["erro"]:
        return JSONResponse({"erro": info["erro"]}, status_code=400)

    canal = info["canal"]
    _sessao_ao_vivo = SessaoAoVivo(
        id=uuid.uuid4().hex[:12],
        url=req.url,
        canal=canal,
        titulo=info["titulo"],
    )

    return {
        "sessao_id": _sessao_ao_vivo.id,
        "canal": canal,
        "titulo": info["titulo"],
        "video_id": info["video_id"],
        "status": "conectado",
        "tem_calibracao": obter_calibracao(canal) is not None,
    }


@app.post("/api/ao-vivo/iniciar")
def post_ao_vivo_iniciar():
    """Inicia captura ao vivo (botão 'Iniciar Análise')."""
    global _sessao_ao_vivo
    if not _sessao_ao_vivo:
        return JSONResponse({"erro": "Nenhuma sessão conectada"}, status_code=400)
    if _sessao_ao_vivo.status == "analisando":
        return {"status": "analisando", "aviso": "Já está analisando"}

    from leilao_inteligente.pipeline.calibration import obter_calibracao, montar_prompt_gemini
    cal = obter_calibracao(_sessao_ao_vivo.canal)
    prompt = montar_prompt_gemini(cal) if cal else None

    _sessao_ao_vivo.iniciar(prompt_calibrado=prompt)
    return {"status": "analisando"}


@app.post("/api/ao-vivo/pausar")
def post_ao_vivo_pausar():
    """Pausa a captura (intervalo do leilão)."""
    if not _sessao_ao_vivo:
        return JSONResponse({"erro": "Nenhuma sessão"}, status_code=400)
    _sessao_ao_vivo.pausar()
    return {"status": "pausado"}


@app.post("/api/ao-vivo/retomar")
def post_ao_vivo_retomar():
    """Retoma a captura após pausa."""
    if not _sessao_ao_vivo:
        return JSONResponse({"erro": "Nenhuma sessão"}, status_code=400)
    _sessao_ao_vivo.retomar()
    return {"status": "analisando"}


@app.post("/api/ao-vivo/encerrar")
def post_ao_vivo_encerrar():
    """Encerra sessão e persiste como leilão no banco."""
    global _sessao_ao_vivo
    if not _sessao_ao_vivo:
        return JSONResponse({"erro": "Nenhuma sessão"}, status_code=400)

    _sessao_ao_vivo.encerrar()
    if _sessao_ao_vivo._thread:
        _sessao_ao_vivo._thread.join(timeout=10)

    from leilao_inteligente.storage.repository import salvar_leilao
    from leilao_inteligente.models.schemas import LeilaoInfo, LoteConsolidado

    lotes_consolidados = []
    for lote in _sessao_ao_vivo.lotes_finalizados:
        lc = LoteConsolidado(
            lote_numero=lote.lote_numero,
            quantidade=lote.quantidade,
            raca=lote.raca,
            sexo=lote.sexo,
            condicao=lote.condicao,
            idade_meses=lote.idade_meses,
            preco_inicial=lote.preco_inicial,
            preco_final=lote.preco_atual,
            preco_por_cabeca=lote.preco_atual / lote.quantidade if lote.quantidade else None,
            fazenda_vendedor=lote.fazenda_vendedor,
            local_cidade=None,
            local_estado=None,
            timestamp_inicio=lote.inicio,
            timestamp_fim=lote.fim,
            frames_analisados=lote.frames_analisados,
            confianca_media=lote.confianca_media,
            aparicoes=1,
            status=lote.status,
            frame_paths=[],
            segundo_video=None,
        )
        lotes_consolidados.append(lc)

    resultado = {"status": "encerrado", "leilao_id": None, "lotes": 0}
    if lotes_consolidados:
        leilao_info = LeilaoInfo(
            canal_youtube=_sessao_ao_vivo.canal,
            url_video=_sessao_ao_vivo.url,
            titulo=_sessao_ao_vivo.titulo,
            data_leilao=datetime.now(tz=timezone.utc),
        )
        leilao = salvar_leilao(leilao_info, lotes_consolidados)
        resultado = {"status": "encerrado", "leilao_id": leilao.id, "lotes": len(lotes_consolidados)}

    _sessao_ao_vivo = None
    return resultado


@app.get("/api/ao-vivo/status")
def get_ao_vivo_status():
    """Retorna estado atual da sessão ao vivo."""
    if not _sessao_ao_vivo:
        return {"ativo": False}
    return {"ativo": True, **_sessao_ao_vivo.to_dict()}


@app.get("/api/ao-vivo/eventos")
def get_ao_vivo_eventos():
    """Stream SSE de eventos ao vivo."""
    if not _sessao_ao_vivo:
        return JSONResponse({"erro": "Nenhuma sessão"}, status_code=400)

    import json as _json

    def event_stream():
        while _sessao_ao_vivo and _sessao_ao_vivo.status not in ("encerrado", "erro"):
            try:
                evento = _sessao_ao_vivo.eventos.get(timeout=5)
                yield f"data: {_json.dumps(evento, default=str)}\n\n"
            except Exception:
                yield f"data: {_json.dumps({'tipo': 'heartbeat'})}\n\n"
        yield f"data: {_json.dumps({'tipo': 'fim'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.get("/api/ao-vivo/comparacao")
def get_ao_vivo_comparacao(
    n_leiloes: int = 5,
    casas: str | None = None,
    cidades: str | None = None,
    estados: str | None = None,
):
    """Comparações históricas multicamada para o lote atual.

    Filtro fixo: raça exata, sexo exato, idade ±1 mês, status arrematado.
    Camadas configuráveis: mesma casa, casas específicas, cidades, estados, geral.
    """
    if not _sessao_ao_vivo or not _sessao_ao_vivo.lote_atual:
        return {"comparacoes": []}

    lote = _sessao_ao_vivo.lote_atual
    session = get_session()

    try:
        raca = lote.raca
        sexo = lote.sexo
        idade = lote.idade_meses
        preco_atual = float(lote.preco_atual)

        if not all([raca, sexo, idade]):
            return {"comparacoes": [], "motivo": "Dados insuficientes do lote atual"}

        def _query_camada(filtros_extra=None, label=""):
            """Monta comparação para uma camada geográfica."""
            import numpy as np

            # Lotes arrematados com mesmo perfil
            q = session.query(Lote).join(Leilao, isouter=True).filter(
                Lote.raca == raca,
                Lote.sexo == sexo,
                Lote.idade_meses.between(idade - 1, idade + 1),
                Lote.status == "arrematado",
                Lote.preco_final > 0,
            )
            if filtros_extra:
                for f in filtros_extra:
                    q = q.filter(f)

            # Limitar por N últimos leilões
            leilao_ids = [r[0] for r in session.query(Leilao.id).order_by(
                func.coalesce(Leilao.data_leilao, Leilao.processado_em).desc()
            ).limit(n_leiloes).all()]
            if leilao_ids:
                q = q.filter(Lote.leilao_id.in_(leilao_ids))

            lotes_hist = q.all()
            if not lotes_hist:
                return None

            precos = [float(l.preco_final) for l in lotes_hist]
            n = len(precos)
            media = sum(precos) / n

            # Posição percentual
            abaixo = sum(1 for p in precos if p < preco_atual)
            percentual = round(abaixo / n * 100)

            # Taxa de arrematação por faixa (quartis dinâmicos)
            quartis = np.percentile(precos, [25, 50, 75]).tolist()
            faixas = [
                (min(precos), quartis[0]),
                (quartis[0], quartis[1]),
                (quartis[1], quartis[2]),
                (quartis[2], max(precos)),
            ]

            # Todos os lotes (incluindo não arrematados) para taxa
            q_todos = session.query(Lote).join(Leilao, isouter=True).filter(
                Lote.raca == raca,
                Lote.sexo == sexo,
                Lote.idade_meses.between(idade - 1, idade + 1),
                Lote.preco_final > 0,
            )
            if filtros_extra:
                for f in filtros_extra:
                    q_todos = q_todos.filter(f)
            if leilao_ids:
                q_todos = q_todos.filter(Lote.leilao_id.in_(leilao_ids))
            todos = q_todos.all()

            taxa_faixas = []
            faixa_atual_idx = None
            for i, (fmin, fmax) in enumerate(faixas):
                na_faixa = [l for l in todos if fmin <= float(l.preco_final) <= fmax]
                arrematados = sum(1 for l in na_faixa if l.status == "arrematado")
                total_faixa = len(na_faixa)
                taxa = round(arrematados / total_faixa * 100) if total_faixa > 0 else 0
                taxa_faixas.append({
                    "min": round(fmin),
                    "max": round(fmax),
                    "total": total_faixa,
                    "arrematados": arrematados,
                    "taxa": taxa,
                })
                if fmin <= preco_atual <= fmax:
                    faixa_atual_idx = i

            # Tendência
            tendencia = None
            if n >= 4:
                precos_sorted = sorted(precos)
                meio = n // 2
                media_recente = sum(precos_sorted[meio:]) / len(precos_sorted[meio:])
                media_antiga = sum(precos_sorted[:meio]) / len(precos_sorted[:meio])
                if media_antiga > 0:
                    tendencia = round((media_recente - media_antiga) / media_antiga * 100, 1)

            return {
                "label": label,
                "media": round(media),
                "minimo": round(min(precos)),
                "maximo": round(max(precos)),
                "lotes": n,
                "percentual": percentual,
                "tendencia": tendencia,
                "taxa_faixas": taxa_faixas,
                "faixa_atual": faixa_atual_idx,
                "n_leiloes_real": len(set(l.leilao_id for l in lotes_hist)),
            }

        comparacoes = []

        # Camada 1: Mesma casa
        c = _query_camada([Leilao.titulo == _sessao_ao_vivo.titulo], f"Esta casa")
        if c:
            comparacoes.append(c)

        # Camada 2: Casas específicas
        if casas:
            for casa in casas.split(","):
                c = _query_camada([Leilao.titulo == casa.strip()], casa.strip()[:30])
                if c:
                    comparacoes.append(c)

        # Camada 3: Cidades
        if cidades:
            for cidade in cidades.split(","):
                c = _query_camada([Leilao.local_cidade == cidade.strip()], f"Cidade: {cidade.strip()}")
                if c:
                    comparacoes.append(c)

        # Camada 4: Estados
        if estados:
            for estado in estados.split(","):
                c = _query_camada([Leilao.local_estado == estado.strip().upper()], f"Estado: {estado.strip().upper()}")
                if c:
                    comparacoes.append(c)

        # Camada 5: Geral
        c = _query_camada(label="Todos os leilões")
        if c:
            comparacoes.append(c)

        return {
            "perfil": {"raca": raca, "sexo": sexo, "idade_meses": idade, "preco_atual": preco_atual},
            "n_leiloes_solicitados": n_leiloes,
            "comparacoes": comparacoes,
        }
    finally:
        session.close()
