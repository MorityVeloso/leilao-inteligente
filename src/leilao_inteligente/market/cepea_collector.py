"""Coletor de cotações via agrobr (CEPEA + IMEA)."""

import asyncio
import logging
from datetime import date, datetime

logger = logging.getLogger(__name__)


async def _coletar_cepea_boi_gordo() -> list[dict]:
    """Coleta indicador CEPEA/ESALQ boi gordo — referência nacional (SP)."""
    from agrobr.cepea import indicador

    try:
        df = await indicador("boi_gordo")
    except Exception as e:
        logger.error("Erro coletando CEPEA boi gordo: %s", e)
        return []

    resultados = []
    for _, row in df.iterrows():
        dt = row["data"]
        if hasattr(dt, "date"):
            dt = dt.date()

        resultados.append({
            "data": dt,
            "estado": "SP",
            "praca": "São Paulo",
            "categoria": "boi_gordo",
            "raca": "nelore",
            "sexo": "macho",
            "valor": float(row["valor"]),
            "unidade": "BRL/@",
            "fonte": "cepea",
        })

    logger.info("CEPEA boi gordo: %d cotações", len(resultados))
    return resultados


async def _coletar_imea_boi() -> list[dict]:
    """Coleta cotações IMEA bovinocultura — MT por município, R$/@."""
    from agrobr.imea import cotacoes

    try:
        df = await cotacoes(cadeia="boi_gordo")
    except Exception as e:
        logger.error("Erro coletando IMEA: %s", e)
        return []

    # Filtrar apenas R$/@ (ignorar R$/kg, %, cab, dia)
    df_arroba = df[df["unidade"] == "R$/@"].copy()
    df_arroba = df_arroba.dropna(subset=["valor"])

    resultados = []
    for _, row in df_arroba.iterrows():
        dt = row["data_publicacao"]
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt).date()
        elif hasattr(dt, "date"):
            dt = dt.date()

        resultados.append({
            "data": dt,
            "estado": "MT",
            "praca": row["localidade"],
            "categoria": "boi_gordo",
            "raca": "nelore",
            "sexo": "macho",
            "valor": float(row["valor"]),
            "unidade": "BRL/@",
            "fonte": "imea",
        })

    logger.info("IMEA boi gordo: %d cotações (R$/@)", len(resultados))
    return resultados


async def _coletar_tudo_async() -> list[dict]:
    """Coleta CEPEA + IMEA em paralelo."""
    cepea, imea = await asyncio.gather(
        _coletar_cepea_boi_gordo(),
        _coletar_imea_boi(),
        return_exceptions=True,
    )

    resultados = []
    if isinstance(cepea, list):
        resultados.extend(cepea)
    else:
        logger.error("CEPEA falhou: %s", cepea)

    if isinstance(imea, list):
        resultados.extend(imea)
    else:
        logger.error("IMEA falhou: %s", imea)

    return resultados


def coletar_cepea_imea() -> list[dict]:
    """Coleta síncrona de CEPEA + IMEA. Retorna lista de dicts prontos para CotacaoMercado."""
    return asyncio.run(_coletar_tudo_async())
