"""Pydantic schemas para validacao de dados extraidos."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class LoteExtraido(BaseModel):
    """Dados brutos extraidos pelo Gemini de um frame de leilao."""

    lote_numero: int = Field(ge=1, le=9999, description="Numero do lote")
    quantidade: int = Field(ge=1, le=500, description="Quantidade de animais")
    raca: str = Field(min_length=2, max_length=50, description="Raca do gado")
    sexo: Literal["macho", "femea", "misto"] = Field(description="Sexo do lote")
    idade_meses: int | None = Field(
        default=None, ge=1, le=120, description="Idade em meses"
    )
    pelagem: str | None = Field(
        default=None, max_length=50, description="Cor da pelagem"
    )
    preco_lance: Decimal = Field(
        ge=Decimal("100"), le=Decimal("100000"), description="Valor do lance em R$"
    )
    local_cidade: str = Field(min_length=2, max_length=100, description="Cidade")
    local_estado: str = Field(
        min_length=2, max_length=2, description="Sigla do estado (UF)"
    )
    timestamp_frame: datetime = Field(description="Timestamp do frame no video")
    confianca: float = Field(
        ge=0.0, le=1.0, description="Nivel de confianca da extracao"
    )


class LoteConsolidado(BaseModel):
    """Lote consolidado a partir de multiplos frames."""

    lote_numero: int
    quantidade: int
    raca: str
    sexo: Literal["macho", "femea", "misto"]
    idade_meses: int | None = None
    pelagem: str | None = None
    preco_lance_inicial: Decimal
    preco_arrematacao: Decimal | None = None
    preco_por_cabeca: Decimal | None = None
    local_cidade: str
    local_estado: str
    timestamp_inicio: datetime
    timestamp_fim: datetime | None = None
    frames_analisados: int = Field(ge=1)
    confianca_media: float = Field(ge=0.0, le=1.0)


class LeilaoInfo(BaseModel):
    """Metadados de um leilao."""

    canal_youtube: str
    url_video: str
    titulo: str
    data_leilao: datetime | None = None
    local_cidade: str | None = None
    local_estado: str | None = None
