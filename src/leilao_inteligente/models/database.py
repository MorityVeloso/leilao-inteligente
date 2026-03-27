"""SQLAlchemy models para persistencia."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    pass


class Leilao(Base):
    """Tabela de leiloes processados."""

    __tablename__ = "leiloes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    canal_youtube: Mapped[str] = mapped_column(String(200))
    url_video: Mapped[str] = mapped_column(String(500), unique=True)
    titulo: Mapped[str] = mapped_column(String(500))
    data_leilao: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    local_cidade: Mapped[str | None] = mapped_column(String(100), nullable=True)
    local_estado: Mapped[str | None] = mapped_column(String(2), nullable=True)
    total_lotes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    status: Mapped[str] = mapped_column(String(20), default="processando")

    lotes: Mapped[list["Lote"]] = relationship(back_populates="leilao", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Leilao(id={self.id}, titulo='{self.titulo}', status='{self.status}')>"


class Lote(Base):
    """Tabela de lotes extraidos."""

    __tablename__ = "lotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    leilao_id: Mapped[int] = mapped_column(ForeignKey("leiloes.id"))
    lote_numero: Mapped[str] = mapped_column(String(10))
    quantidade: Mapped[int] = mapped_column(Integer)
    raca: Mapped[str] = mapped_column(String(50))
    sexo: Mapped[str] = mapped_column(String(10))
    idade_meses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pelagem: Mapped[str | None] = mapped_column(String(50), nullable=True)
    preco_inicial: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    preco_final: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    preco_por_cabeca: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    fazenda_vendedor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    timestamp_inicio: Mapped[datetime] = mapped_column(DateTime)
    timestamp_fim: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    timestamp_video_inicio: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    timestamp_video_fim: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    frames_analisados: Mapped[int] = mapped_column(Integer, default=1)
    confianca_media: Mapped[float] = mapped_column(Float, default=0.0)
    aparicoes: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="incerto")
    frame_paths: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    leilao: Mapped["Leilao"] = relationship(back_populates="lotes")

    def __repr__(self) -> str:
        return (
            f"<Lote(id={self.id}, lote={self.lote_numero}, "
            f"{self.quantidade}x {self.raca} {self.sexo}, status={self.status})>"
        )
