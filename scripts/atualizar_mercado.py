#!/usr/bin/env python3
"""Script para atualização diária de cotações de mercado.

Uso manual:
    python scripts/atualizar_mercado.py

Cron (diário às 8h):
    0 8 * * * cd /path/to/leilao-inteligente && .venv/bin/python scripts/atualizar_mercado.py
"""

import logging
import sys
from pathlib import Path

# Adicionar src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


def main() -> None:
    from leilao_inteligente.storage.db import init_db
    from leilao_inteligente.market.collector import atualizar_mercado

    init_db()

    logger.info("Iniciando atualização de cotações de mercado...")
    resultado = atualizar_mercado()

    logger.info(
        "Concluído: %d coletados, %d persistidos, fontes: %s",
        resultado["coletados"],
        resultado["persistidos"],
        resultado["fontes"],
    )


if __name__ == "__main__":
    main()
