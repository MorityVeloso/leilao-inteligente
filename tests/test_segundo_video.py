"""Testes para o campo segundo_video no pipeline."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from leilao_inteligente.models.schemas import LoteConsolidado, LoteExtraido
from leilao_inteligente.pipeline.processor import LoteComFrame, consolidar_lotes


def _make_lote_extraido(
    lote_numero: str = "0001",
    preco_lance: Decimal = Decimal("3000"),
    timestamp_frame: datetime | None = None,
    confianca: float = 0.95,
) -> LoteExtraido:
    """Helper para criar LoteExtraido de teste."""
    if timestamp_frame is None:
        timestamp_frame = datetime(2026, 3, 26, 22, 0, 0, tzinfo=timezone.utc)
    return LoteExtraido(
        lote_numero=lote_numero,
        quantidade=10,
        raca="Nelore",
        sexo="macho",
        preco_lance=preco_lance,
        local_cidade="Goiania",
        local_estado="GO",
        timestamp_frame=timestamp_frame,
        confianca=confianca,
    )


class TestLoteConsolidadoSegundoVideo:
    """Testes do campo segundo_video no schema LoteConsolidado."""

    def test_aceita_segundo_video(self) -> None:
        """LoteConsolidado aceita segundo_video como int."""
        lote = LoteConsolidado(
            lote_numero="001",
            quantidade=10,
            raca="Nelore",
            sexo="macho",
            preco_inicial=Decimal("1000"),
            preco_final=Decimal("3000"),
            local_cidade="Goiania",
            local_estado="GO",
            timestamp_inicio=datetime(2026, 3, 26, 22, 0, 0, tzinfo=timezone.utc),
            frames_analisados=3,
            confianca_media=0.9,
            segundo_video=1610,
        )
        assert lote.segundo_video == 1610

    def test_default_segundo_video_none(self) -> None:
        """LoteConsolidado default segundo_video e None."""
        lote = LoteConsolidado(
            lote_numero="001",
            quantidade=10,
            raca="Nelore",
            sexo="macho",
            preco_inicial=Decimal("1000"),
            preco_final=Decimal("3000"),
            local_cidade="Goiania",
            local_estado="GO",
            timestamp_inicio=datetime(2026, 3, 26, 22, 0, 0, tzinfo=timezone.utc),
            frames_analisados=3,
            confianca_media=0.9,
        )
        assert lote.segundo_video is None


class TestConsolidarLotesSegundoVideo:
    """Testes de calculo de segundo_video em consolidar_lotes."""

    def test_calcula_segundo_video_do_frame_name(self, tmp_path: Path) -> None:
        """segundo_video = (frame_number - 1) * 5 a partir do nome do frame."""
        # frame_000323.jpg → (323-1)*5 = 1610
        frame_path = tmp_path / "frame_000323.jpg"
        frame_path.touch()

        ts_base = datetime(2026, 3, 26, 22, 0, 0, tzinfo=timezone.utc)

        lote1 = _make_lote_extraido(
            preco_lance=Decimal("3000"),
            timestamp_frame=ts_base,
        )
        lote2 = _make_lote_extraido(
            preco_lance=Decimal("3500"),
            timestamp_frame=ts_base + timedelta(seconds=5),
        )

        frame_path2 = tmp_path / "frame_000324.jpg"
        frame_path2.touch()

        lcfs = [
            LoteComFrame(lote1, frame_path),
            LoteComFrame(lote2, frame_path2),
        ]

        result = consolidar_lotes(lcfs)
        assert len(result) == 1
        assert result[0].segundo_video == 1610

    def test_segundo_video_frame_001(self, tmp_path: Path) -> None:
        """Primeiro frame (frame_000001) resulta em segundo_video=0."""
        frame_path = tmp_path / "frame_000001.jpg"
        frame_path.touch()

        ts_base = datetime(2026, 3, 26, 22, 0, 0, tzinfo=timezone.utc)

        lote1 = _make_lote_extraido(
            preco_lance=Decimal("2000"),
            timestamp_frame=ts_base,
        )
        lote2 = _make_lote_extraido(
            preco_lance=Decimal("2500"),
            timestamp_frame=ts_base + timedelta(seconds=5),
        )

        frame_path2 = tmp_path / "frame_000002.jpg"
        frame_path2.touch()

        lcfs = [
            LoteComFrame(lote1, frame_path),
            LoteComFrame(lote2, frame_path2),
        ]

        result = consolidar_lotes(lcfs)
        assert len(result) == 1
        assert result[0].segundo_video == 0

    def test_segundo_video_ignora_frames_preco_zero(self, tmp_path: Path) -> None:
        """segundo_video vem do primeiro frame com preco > 0, nao do preco 0."""
        frame_zero = tmp_path / "frame_000010.jpg"
        frame_zero.touch()
        frame_com_preco = tmp_path / "frame_000050.jpg"
        frame_com_preco.touch()
        frame_com_preco2 = tmp_path / "frame_000051.jpg"
        frame_com_preco2.touch()

        ts_base = datetime(2026, 3, 26, 22, 0, 0, tzinfo=timezone.utc)

        lote_zero = _make_lote_extraido(
            preco_lance=Decimal("0"),
            timestamp_frame=ts_base,
        )
        lote_com = _make_lote_extraido(
            preco_lance=Decimal("5000"),
            timestamp_frame=ts_base + timedelta(seconds=200),
        )
        lote_com2 = _make_lote_extraido(
            preco_lance=Decimal("5500"),
            timestamp_frame=ts_base + timedelta(seconds=205),
        )

        lcfs = [
            LoteComFrame(lote_zero, frame_zero),
            LoteComFrame(lote_com, frame_com_preco),
            LoteComFrame(lote_com2, frame_com_preco2),
        ]

        result = consolidar_lotes(lcfs)
        assert len(result) == 1
        # (50-1)*5 = 245
        assert result[0].segundo_video == 245
