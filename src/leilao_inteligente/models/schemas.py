"""Pydantic schemas para validacao de dados extraidos."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class LoteExtraido(BaseModel):
    """Dados brutos extraidos pelo Gemini de um frame de leilao."""

    lote_numero: str = Field(min_length=1, max_length=10, description="Numero do lote (pode ser alfanumerico: 5, 001A, 55A)")
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
        ge=Decimal("0"), le=Decimal("500000"), description="Valor do lance em R$"
    )
    local_cidade: str = Field(min_length=2, max_length=100, description="Cidade")
    local_estado: str = Field(
        min_length=2, max_length=2, description="Sigla do estado (UF)"
    )
    fazenda_vendedor: str | None = Field(
        default=None, max_length=200, description="Nome da fazenda vendedora"
    )
    timestamp_video: datetime | None = Field(
        default=None, description="Data/hora exata mostrada no overlay"
    )
    timestamp_frame: datetime = Field(description="Timestamp do frame no video")
    confianca: float = Field(
        ge=0.0, le=1.0, description="Nivel de confianca da extracao"
    )


class LoteConsolidado(BaseModel):
    """Lote consolidado a partir de multiplos frames."""

    lote_numero: str
    quantidade: int
    raca: str
    sexo: Literal["macho", "femea", "misto"]
    idade_meses: int | None = None
    pelagem: str | None = None
    preco_inicial: Decimal
    preco_final: Decimal
    preco_por_cabeca: Decimal | None = None
    local_cidade: str
    local_estado: str
    fazenda_vendedor: str | None = None
    timestamp_inicio: datetime
    timestamp_fim: datetime | None = None
    timestamp_video_inicio: datetime | None = None
    timestamp_video_fim: datetime | None = None
    frames_analisados: int = Field(ge=1)
    confianca_media: float = Field(ge=0.0, le=1.0)
    aparicoes: int = Field(default=1, ge=1, description="Vezes que o lote apareceu (2+ = repescagem)")
    status: str = Field(default="incerto", description="arrematado | repescagem | incerto")
    frame_paths: list[str] = Field(default_factory=list, description="Paths dos frames visuais")


class LeilaoInfo(BaseModel):
    """Metadados de um leilao."""

    canal_youtube: str
    url_video: str
    titulo: str
    data_leilao: datetime | None = None
    local_cidade: str | None = None
    local_estado: str | None = None
