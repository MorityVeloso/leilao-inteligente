"""Análise de tendência de mercado bovino via regressão linear."""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

import numpy as np
from sqlalchemy import func

from leilao_inteligente.models.database import CotacaoMercado
from leilao_inteligente.storage.db import get_session

logger = logging.getLogger(__name__)

MIN_PONTOS = 3  # mínimo de dias distintos para calcular tendência


class Tendencia(str, Enum):
    ALTA_FORTE = "alta_forte"
    ALTA = "alta"
    ESTAVEL = "estavel"
    BAIXA = "baixa"
    BAIXA_FORTE = "baixa_forte"


# Limiares de variação % por janela (calibrados para mercado bovino)
LIMIARES = {
    7:  {"forte": 2.0, "leve": 1.0},
    21: {"forte": 5.0, "leve": 2.0},
    30: {"forte": 5.0, "leve": 3.0},
    90: {"forte": 8.0, "leve": 5.0},
}


@dataclass
class ResultadoTendencia:
    tendencia: Tendencia
    variacao_pct: float
    r_squared: float
    n_pontos: int
    preco_inicial: float
    preco_final: float
    janela_dias: int

    def to_dict(self) -> dict:
        return {
            "tendencia": self.tendencia.value,
            "variacao_pct": round(self.variacao_pct, 2),
            "r_squared": round(self.r_squared, 3),
            "n_pontos": self.n_pontos,
            "preco_inicial": round(self.preco_inicial, 2),
            "preco_final": round(self.preco_final, 2),
            "janela_dias": self.janela_dias,
        }


def _classificar(variacao_pct: float, r_squared: float, janela: int) -> Tendencia:
    """Classifica tendência com base na variação e confiança (R²)."""
    lim = LIMIARES.get(janela, LIMIARES[30])

    # R² muito baixo = dados dispersos, sem tendência confiável
    if r_squared < 0.15:
        return Tendencia.ESTAVEL

    if variacao_pct >= lim["forte"]:
        return Tendencia.ALTA_FORTE
    if variacao_pct >= lim["leve"]:
        return Tendencia.ALTA
    if variacao_pct <= -lim["forte"]:
        return Tendencia.BAIXA_FORTE
    if variacao_pct <= -lim["leve"]:
        return Tendencia.BAIXA

    return Tendencia.ESTAVEL


def calcular_tendencia_serie(
    datas: list[date],
    valores: list[float],
    janela_dias: int,
) -> ResultadoTendencia | None:
    """Calcula tendência via regressão linear numa série de (data, valor)."""
    if len(datas) < MIN_PONTOS:
        return None

    # Converter datas para dias numéricos (0, 1, 2, ...)
    base = min(datas)
    x = np.array([(d - base).days for d in datas], dtype=float)
    y = np.array(valores, dtype=float)

    # Regressão linear: y = slope * x + intercept
    coef = np.polyfit(x, y, 1)
    slope, intercept = coef[0], coef[1]

    # Valores estimados pela reta
    y_pred = np.polyval(coef, x)

    # R²
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_squared = float(1 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0
    r_squared = max(0.0, r_squared)

    # Variação % da reta (início → fim do período)
    preco_inicial = float(intercept)
    preco_final = float(slope * x[-1] + intercept)

    if preco_inicial > 0:
        variacao_pct = ((preco_final - preco_inicial) / preco_inicial) * 100
    else:
        variacao_pct = 0.0

    tendencia = _classificar(variacao_pct, r_squared, janela_dias)

    return ResultadoTendencia(
        tendencia=tendencia,
        variacao_pct=variacao_pct,
        r_squared=r_squared,
        n_pontos=len(datas),
        preco_inicial=preco_inicial,
        preco_final=preco_final,
        janela_dias=janela_dias,
    )


def analisar_tendencia_mercado(
    estado: str | None = None,
    categoria: str = "boi_gordo",
    fonte: str | None = None,
) -> dict:
    """Analisa tendência de mercado em múltiplas janelas temporais.

    Retorna dict com tendência para cada janela (7d, 21d, 90d)
    e o valor mais recente como referência.
    """
    session = get_session()
    try:
        janelas = [7, 21, 90]
        maior_janela = max(janelas)
        desde = date.today() - timedelta(days=maior_janela)

        # Buscar médias diárias (agrupadas por data)
        q = session.query(
            CotacaoMercado.data,
            func.avg(CotacaoMercado.valor).label("media"),
        ).filter(
            CotacaoMercado.data >= desde,
            CotacaoMercado.categoria == categoria,
        )

        if estado:
            q = q.filter(CotacaoMercado.estado == estado)
        if fonte:
            q = q.filter(CotacaoMercado.fonte == fonte)

        q = q.group_by(CotacaoMercado.data).order_by(CotacaoMercado.data)
        rows = q.all()

        if len(rows) < MIN_PONTOS:
            return {
                "categoria": categoria,
                "estado": estado,
                "fonte": fonte,
                "janelas": {},
                "ultimo_valor": None,
                "ultima_data": None,
                "insuficiente": True,
                "n_pontos": len(rows),
            }

        todas_datas = [r.data for r in rows]
        todos_valores = [float(r.media) for r in rows]

        # Calcular para cada janela
        resultado_janelas = {}
        for janela in janelas:
            corte = date.today() - timedelta(days=janela)
            datas_j = [d for d, v in zip(todas_datas, todos_valores) if d >= corte]
            valores_j = [v for d, v in zip(todas_datas, todos_valores) if d >= corte]

            tend = calcular_tendencia_serie(datas_j, valores_j, janela)
            if tend:
                resultado_janelas[str(janela)] = tend.to_dict()

        return {
            "categoria": categoria,
            "estado": estado,
            "fonte": fonte,
            "janelas": resultado_janelas,
            "ultimo_valor": round(todos_valores[-1], 2) if todos_valores else None,
            "ultima_data": str(todas_datas[-1]) if todas_datas else None,
            "insuficiente": False,
            "n_pontos": len(rows),
        }
    finally:
        session.close()


def resumo_tendencias(estado: str | None = None) -> list[dict]:
    """Retorna tendência resumida para as principais categorias."""
    categorias = ["boi_gordo", "bezerro_12m", "garrote", "vaca_gorda"]
    resultados = []

    for cat in categorias:
        analise = analisar_tendencia_mercado(estado=estado, categoria=cat)
        # Pegar a janela mais longa disponível como referência
        janela_ref = None
        for j in ["21", "7", "90"]:
            if j in analise.get("janelas", {}):
                janela_ref = analise["janelas"][j]
                break

        resultados.append({
            "categoria": cat,
            "ultimo_valor": analise.get("ultimo_valor"),
            "ultima_data": analise.get("ultima_data"),
            "tendencia": janela_ref,
            "insuficiente": analise.get("insuficiente", True),
        })

    return resultados
