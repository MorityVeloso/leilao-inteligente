"""Fixtures compartilhadas para testes."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest


@pytest.fixture
def dados_lote_valido() -> dict:
    """Dados validos de um lote como retornados pelo Gemini."""
    return {
        "lote_numero": 5,
        "quantidade": 35,
        "raca": "Nelore",
        "sexo": "macho",
        "idade_meses": 12,
        "pelagem": "branco",
        "preco_lance": 3290.00,
        "local_cidade": "Crixás",
        "local_estado": "GO",
        "confianca": 0.95,
    }


@pytest.fixture
def dados_lote_sujo() -> dict:
    """Dados com inconsistencias comuns do Gemini (precisam normalizacao)."""
    return {
        "lote_numero": 10,
        "quantidade": 20,
        "raca": "  nelore  ",
        "sexo": "Machos",
        "idade_meses": 18,
        "pelagem": "  Branco  ",
        "preco_lance": "R$ 3.500,00",
        "local_cidade": "  araçatuba  ",
        "local_estado": "sp",
        "confianca": 0.88,
    }


@pytest.fixture
def dados_lote_invalido() -> dict:
    """Dados invalidos que devem ser rejeitados."""
    return {
        "lote_numero": -1,
        "quantidade": 0,
        "raca": "",
        "sexo": "indefinido",
        "preco_lance": 50,  # abaixo do minimo
        "local_cidade": "X",
        "local_estado": "ZZ",
        "confianca": 2.0,  # acima do maximo
    }


@pytest.fixture
def timestamp_fixture() -> datetime:
    """Timestamp de referencia para testes."""
    return datetime(2026, 3, 26, 22, 0, 0, tzinfo=timezone.utc)
