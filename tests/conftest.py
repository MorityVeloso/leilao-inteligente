"""Fixtures compartilhadas para testes."""

from datetime import datetime, timezone

import pytest


@pytest.fixture
def dados_lote_valido() -> dict:
    """Dados validos de um lote como retornados pelo Gemini."""
    return {
        "lote_numero": "0005",
        "quantidade": 35,
        "raca": "Nelore",
        "sexo": "macho",
        "idade_meses": 12,
        "pelagem": "branco",
        "preco_lance": 3290.00,
        "local_cidade": "Crixás",
        "local_estado": "GO",
        "fazenda_vendedor": "FAZ. JULIANA",
        "timestamp_video": "26/03/2026 20:54:21",
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
        "fazenda_vendedor": "Recinto FAZ. SANTO ANTONIO",
        "timestamp_video": "26/03/2026 21:30:00",
        "confianca": 0.88,
    }


@pytest.fixture
def dados_lote_invalido() -> dict:
    """Dados invalidos que devem ser rejeitados."""
    return {
        "lote_numero": "",
        "quantidade": 0,
        "raca": "",
        "sexo": "indefinido",
        "preco_lance": -50,
        "local_cidade": "X",
        "local_estado": "ZZ",
        "confianca": 2.0,
    }


@pytest.fixture
def dados_lote_alfanumerico() -> dict:
    """Lote com numero alfanumerico (ex: 001A, 55A)."""
    return {
        "lote_numero": "001A",
        "quantidade": 33,
        "raca": "Nelore",
        "sexo": "femea",
        "idade_meses": 9,
        "pelagem": "branco",
        "preco_lance": 2800.00,
        "local_cidade": "Crixás",
        "local_estado": "GO",
        "fazenda_vendedor": "FAZ. JULIANA",
        "confianca": 0.92,
    }


@pytest.fixture
def dados_lote_preco_zero() -> dict:
    """Lote com preco 0 (transicao de overlay)."""
    return {
        "lote_numero": "0005",
        "quantidade": 35,
        "raca": "Nelore",
        "sexo": "macho",
        "idade_meses": 12,
        "pelagem": "branco",
        "preco_lance": 0,
        "local_cidade": "Crixás",
        "local_estado": "GO",
        "confianca": 0.90,
    }


@pytest.fixture
def timestamp_fixture() -> datetime:
    """Timestamp de referencia para testes."""
    return datetime(2026, 3, 26, 22, 0, 0, tzinfo=timezone.utc)
