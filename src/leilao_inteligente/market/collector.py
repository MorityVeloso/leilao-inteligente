"""Orquestrador de coleta de cotações de mercado — todas as fontes."""

import logging
from datetime import date

from sqlalchemy.dialects.postgresql import insert as pg_insert

from leilao_inteligente.models.database import CotacaoMercado
from leilao_inteligente.storage.db import get_session

logger = logging.getLogger(__name__)


def coletar_todas_fontes() -> list[dict]:
    """Coleta cotações de todas as fontes disponíveis."""
    resultados = []

    # 1. Notícias Agrícolas (Scot + Datagro) — síncrono
    try:
        from leilao_inteligente.market.scraper import scrape_tudo
        na = scrape_tudo()
        resultados.extend(na)
        logger.info("NA: %d cotações", len(na))
    except Exception as e:
        logger.error("Falha Notícias Agrícolas: %s", e)

    # 2. CEPEA + IMEA via agrobr — async wrapper
    try:
        from leilao_inteligente.market.cepea_collector import coletar_cepea_imea
        agro = coletar_cepea_imea()
        resultados.extend(agro)
        logger.info("agrobr: %d cotações", len(agro))
    except Exception as e:
        logger.error("Falha agrobr (CEPEA/IMEA): %s", e)

    logger.info("Total coletado: %d cotações", len(resultados))
    return resultados


def _deduplicar(cotacoes: list[dict]) -> list[dict]:
    """Remove duplicatas por chave única, mantendo o maior valor."""
    mapa: dict[tuple, dict] = {}
    for c in cotacoes:
        key = (
            str(c["data"]), c["estado"], c.get("praca") or "",
            c["categoria"], c["raca"], c["sexo"], c["fonte"],
        )
        if key not in mapa or c["valor"] > mapa[key]["valor"]:
            mapa[key] = c
    return list(mapa.values())


def persistir_cotacoes(cotacoes: list[dict]) -> int:
    """Persiste cotações no banco via upsert (ON CONFLICT UPDATE)."""
    if not cotacoes:
        return 0

    cotacoes = _deduplicar(cotacoes)
    session = get_session()
    inseridos = 0

    try:
        # Batch de 100 para não sobrecarregar
        for i in range(0, len(cotacoes), 100):
            batch = cotacoes[i:i + 100]
            valores = []
            for c in batch:
                valores.append({
                    "data": c["data"],
                    "estado": c["estado"],
                    "praca": c.get("praca"),
                    "categoria": c["categoria"],
                    "raca": c["raca"],
                    "sexo": c["sexo"],
                    "valor": c["valor"],
                    "unidade": c["unidade"],
                    "fonte": c["fonte"],
                })

            stmt = pg_insert(CotacaoMercado).values(valores)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_cotacao",
                set_={
                    "valor": stmt.excluded.valor,
                    "unidade": stmt.excluded.unidade,
                },
            )
            session.execute(stmt)
            inseridos += len(batch)

        session.commit()
        logger.info("Persistidos %d cotações", inseridos)
    except Exception as e:
        session.rollback()
        logger.error("Erro persistindo cotações: %s", e)
        raise
    finally:
        session.close()

    return inseridos


def atualizar_mercado() -> dict:
    """Coleta e persiste tudo. Retorna resumo."""
    cotacoes = coletar_todas_fontes()
    inseridos = persistir_cotacoes(cotacoes)
    return {
        "coletados": len(cotacoes),
        "persistidos": inseridos,
        "fontes": list({c["fonte"] for c in cotacoes}),
        "data": date.today().isoformat(),
    }
