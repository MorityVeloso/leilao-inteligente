"""API REST para o dashboard consumir."""

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy import func, case

from leilao_inteligente.config import DATA_DIR
from leilao_inteligente.models.database import Leilao, Lote
from leilao_inteligente.storage.db import get_session, init_db


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

        return {
            "racas": racas,
            "sexos": sexos,
            "estados": estados,
            "fazendas": fazendas,
            "faixas_idade": [
                {"label": "1-8m", "min": 1, "max": 8},
                {"label": "10-14m", "min": 10, "max": 14},
                {"label": "15-20m", "min": 15, "max": 20},
                {"label": "21-36m", "min": 21, "max": 36},
                {"label": "36m+", "min": 36, "max": 120},
            ],
        }
    finally:
        session.close()


# --- Lotes com filtros ---


def _aplicar_filtros(query, raca, sexo, idade_min, idade_max, estado, fazenda, dias):
    """Aplica filtros ao query de lotes."""
    if raca:
        query = query.filter(Lote.raca == raca)
    if sexo:
        query = query.filter(Lote.sexo == sexo)
    if idade_min is not None:
        query = query.filter(Lote.idade_meses >= idade_min)
    if idade_max is not None:
        query = query.filter(Lote.idade_meses <= idade_max)
    if estado:
        query = query.join(Leilao, isouter=True).filter(Leilao.local_estado == estado)
    if fazenda:
        query = query.filter(Lote.fazenda_vendedor == fazenda)
    if dias:
        desde = datetime.utcnow() - timedelta(days=dias)
        if estado:
            query = query.filter(Leilao.processado_em >= desde)
        else:
            query = query.join(Leilao, isouter=True).filter(Leilao.processado_em >= desde)
    return query


@app.get("/api/lotes")
def get_lotes(
    raca: str | None = None,
    sexo: str | None = None,
    idade_min: int | None = None,
    idade_max: int | None = None,
    estado: str | None = None,
    fazenda: str | None = None,
    dias: int | None = None,
    leilao_id: int | None = None,
    limite: int = Query(default=200, le=1000),
):
    """Retorna lotes filtrados."""
    session = get_session()
    try:
        q = session.query(Lote)

        if leilao_id:
            q = q.filter(Lote.leilao_id == leilao_id)

        q = _aplicar_filtros(q, raca, sexo, idade_min, idade_max, estado, fazenda, dias)
        q = q.filter(Lote.preco_final > 0)
        q = q.order_by(Lote.timestamp_inicio.desc())
        q = q.limit(limite)

        lotes = q.all()
        return [_lote_to_dict(l, session) for l in lotes]
    finally:
        session.close()


def _lote_to_dict(lote: Lote, session) -> dict:
    """Converte Lote pra dict serializavel."""
    leilao = session.query(Leilao).filter(Leilao.id == lote.leilao_id).first()
    return {
        "id": lote.id,
        "leilao_id": lote.leilao_id,
        "leilao_titulo": leilao.titulo if leilao else None,
        "leilao_data": leilao.processado_em.isoformat() if leilao and leilao.processado_em else None,
        "lote_numero": lote.lote_numero,
        "quantidade": lote.quantidade,
        "raca": lote.raca,
        "sexo": lote.sexo,
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

        q = _aplicar_filtros(q, raca, sexo, idade_min, idade_max, estado, fazenda, dias)
        q = q.filter(Lote.preco_final > 0)

        result = q.one()

        # Tendencia: comparar media atual vs periodo anterior
        tendencia = None
        if dias:
            meio = datetime.utcnow() - timedelta(days=dias // 2)
            desde = datetime.utcnow() - timedelta(days=dias)

            q_recente = session.query(func.avg(Lote.preco_final))
            q_recente = q_recente.join(Leilao).filter(Leilao.processado_em >= meio)
            q_recente = _aplicar_filtros(q_recente, raca, sexo, idade_min, idade_max, estado, fazenda, None)
            q_recente = q_recente.filter(Lote.preco_final > 0)
            media_recente = q_recente.scalar()

            q_antigo = session.query(func.avg(Lote.preco_final))
            q_antigo = q_antigo.join(Leilao).filter(
                Leilao.processado_em >= desde,
                Leilao.processado_em < meio,
            )
            q_antigo = _aplicar_filtros(q_antigo, raca, sexo, idade_min, idade_max, estado, fazenda, None)
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
    dias: int = 90,
):
    """Retorna dados pra grafico de tendencia (media por leilao)."""
    session = get_session()
    try:
        desde = datetime.utcnow() - timedelta(days=dias)

        q = session.query(
            Leilao.processado_em.label("data"),
            Leilao.titulo.label("leilao"),
            func.avg(Lote.preco_final).label("media"),
            func.count(Lote.id).label("lotes"),
        ).join(Leilao)

        q = _aplicar_filtros(q, raca, sexo, idade_min, idade_max, estado, None, None)
        q = q.filter(Lote.preco_final > 0)
        q = q.filter(Leilao.processado_em >= desde)
        q = q.group_by(Leilao.id)
        q = q.order_by(Leilao.processado_em)

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

        q = _aplicar_filtros(q, raca, sexo, idade_min, idade_max, estado, None, dias)
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

        q = _aplicar_filtros(q, raca, sexo, idade_min, idade_max, None, None, dias)
        q = q.filter(Lote.preco_final > 0)
        q = q.filter(Leilao.local_estado.isnot(None))
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
                "processado_em": l.processado_em.isoformat() if l.processado_em else None,
                "status": l.status,
            }
            for l in leiloes
        ]
    finally:
        session.close()


# --- Frames visuais ---


@app.get("/api/frame/{path:path}")
def get_frame(path: str):
    """Serve um frame visual do gado."""
    file_path = DATA_DIR / path
    if not file_path.exists():
        return {"error": "Frame nao encontrado"}
    return FileResponse(file_path)
