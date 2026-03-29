"""Testes para funcoes puras do pipeline/processor.py."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from leilao_inteligente.models.schemas import LoteConsolidado, LoteExtraido
from leilao_inteligente.pipeline.processor import (
    JANELA_ARREMATACAO_SEGUNDOS,
    LoteComFrame,
    _contar_aparicoes,
    _dedup_lotes_espelhados,
    _dedup_lotes_por_similaridade,
    _filtrar_frames_outliers,
    _identificar_janelas_arrematacao,
    _pegar_ultima_aparicao_lcf,
    _valor_mais_frequente,
    consolidar_lotes,
    selecionar_frames_visuais,
)

BASE_TS = datetime(2026, 3, 26, 20, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers / Factories
# ---------------------------------------------------------------------------


def _lote(
    numero: str = "0001",
    preco: float = 3000.0,
    offset_min: float = 0.0,
    qtd: int = 10,
    raca: str = "Nelore",
    sexo: str = "macho",
    confianca: float = 0.95,
) -> LoteExtraido:
    return LoteExtraido(
        lote_numero=numero,
        quantidade=qtd,
        raca=raca,
        sexo=sexo,
        preco_lance=Decimal(str(preco)),
        local_cidade="Crixas",
        local_estado="GO",
        timestamp_frame=BASE_TS + timedelta(minutes=offset_min),
        confianca=confianca,
    )


def _lcf(
    numero: str = "0001",
    preco: float = 3000.0,
    offset_min: float = 0.0,
    frame_name: str = "frame_000001.jpg",
    **kw,
) -> LoteComFrame:
    return LoteComFrame(
        _lote(numero=numero, preco=preco, offset_min=offset_min, **kw),
        Path(f"/tmp/{frame_name}"),
    )


def _consolidado(
    numero: str,
    raca: str = "Nelore",
    sexo: str = "macho",
    qtd: int = 10,
    frames: int = 5,
    offset_min: float = 0.0,
) -> LoteConsolidado:
    return LoteConsolidado(
        lote_numero=numero,
        quantidade=qtd,
        raca=raca,
        sexo=sexo,
        preco_inicial=Decimal("1000"),
        preco_final=Decimal("2000"),
        local_cidade="Crixas",
        local_estado="GO",
        timestamp_inicio=BASE_TS + timedelta(minutes=offset_min),
        frames_analisados=frames,
        confianca_media=0.9,
    )


# ===========================================================================
# _valor_mais_frequente
# ===========================================================================


class TestValorMaisFrequente:
    def test_todos_none(self):
        assert _valor_mais_frequente([None, None]) is None

    def test_lista_vazia(self):
        assert _valor_mais_frequente([]) is None

    def test_um_valor(self):
        assert _valor_mais_frequente(["JULIANA"]) == "JULIANA"

    def test_ignora_none_retorna_unico(self):
        assert _valor_mais_frequente([None, "JULIANA", None]) == "JULIANA"

    def test_retorna_mais_frequente(self):
        assert _valor_mais_frequente([None, "JULIANA", "VITORIA", "JULIANA"]) == "JULIANA"

    def test_empate_retorna_qualquer(self):
        resultado = _valor_mais_frequente(["A", "B"])
        assert resultado in ("A", "B")


# ===========================================================================
# _contar_aparicoes
# ===========================================================================


class TestContarAparicoes:
    def test_single_frame(self):
        assert _contar_aparicoes([_lote()]) == 1

    def test_frames_within_10_min(self):
        frames = [_lote(offset_min=0), _lote(offset_min=5), _lote(offset_min=9)]
        assert _contar_aparicoes(frames) == 1

    def test_gap_greater_than_10_min(self):
        frames = [_lote(offset_min=0), _lote(offset_min=11)]
        assert _contar_aparicoes(frames) == 2

    def test_two_gaps_three_appearances(self):
        frames = [
            _lote(offset_min=0),
            _lote(offset_min=5),
            _lote(offset_min=20),
            _lote(offset_min=25),
            _lote(offset_min=40),
        ]
        assert _contar_aparicoes(frames) == 3

    def test_exactly_10_min_gap_counts_as_one(self):
        """Gap de exatamente 10 min nao conta como nova aparicao (> 10, nao >=)."""
        frames = [_lote(offset_min=0), _lote(offset_min=10)]
        assert _contar_aparicoes(frames) == 1

    def test_empty_frames(self):
        """Lista vazia ainda retorna 1 (edge case protegido por len <= 1)."""
        assert _contar_aparicoes([]) == 1


# ===========================================================================
# _pegar_ultima_aparicao_lcf
# ===========================================================================


class TestPegarUltimaAparicaoLcf:
    def test_single_frame(self):
        frames = [_lcf(offset_min=0)]
        result = _pegar_ultima_aparicao_lcf(frames)
        assert len(result) == 1

    def test_no_gap_returns_all(self):
        frames = [_lcf(offset_min=0), _lcf(offset_min=5), _lcf(offset_min=9)]
        result = _pegar_ultima_aparicao_lcf(frames)
        assert len(result) == 3

    def test_one_gap_returns_last_group(self):
        frames = [
            _lcf(offset_min=0, frame_name="frame_000001.jpg"),
            _lcf(offset_min=5, frame_name="frame_000002.jpg"),
            _lcf(offset_min=20, frame_name="frame_000003.jpg"),
            _lcf(offset_min=25, frame_name="frame_000004.jpg"),
        ]
        result = _pegar_ultima_aparicao_lcf(frames)
        assert len(result) == 2
        assert result[0].frame_path.name == "frame_000003.jpg"
        assert result[1].frame_path.name == "frame_000004.jpg"

    def test_two_gaps_returns_last_group(self):
        frames = [
            _lcf(offset_min=0, frame_name="frame_000001.jpg"),
            _lcf(offset_min=20, frame_name="frame_000002.jpg"),
            _lcf(offset_min=40, frame_name="frame_000003.jpg"),
        ]
        result = _pegar_ultima_aparicao_lcf(frames)
        assert len(result) == 1
        assert result[0].frame_path.name == "frame_000003.jpg"


# ===========================================================================
# selecionar_frames_visuais
# ===========================================================================


class TestSelecionarFramesVisuais:
    def test_fewer_frames_than_n_returns_all(self):
        frames = [_lcf(frame_name=f"frame_{i:06d}.jpg") for i in range(1, 3)]
        result = selecionar_frames_visuais(frames, n=4)
        assert len(result) == 2

    def test_exact_n_frames_returns_all(self):
        frames = [_lcf(frame_name=f"frame_{i:06d}.jpg") for i in range(1, 5)]
        result = selecionar_frames_visuais(frames, n=4)
        assert len(result) == 4

    def test_selects_equidistant_frames(self):
        frames = [_lcf(frame_name=f"frame_{i:06d}.jpg") for i in range(1, 13)]
        result = selecionar_frames_visuais(frames, n=4)
        assert len(result) == 4
        # With 12 frames and n=4, step=3, indices=[0,3,6,9]
        assert result[0] == Path("/tmp/frame_000001.jpg")
        assert result[1] == Path("/tmp/frame_000004.jpg")
        assert result[2] == Path("/tmp/frame_000007.jpg")
        assert result[3] == Path("/tmp/frame_000010.jpg")

    def test_n_equals_1(self):
        frames = [_lcf(frame_name=f"frame_{i:06d}.jpg") for i in range(1, 6)]
        result = selecionar_frames_visuais(frames, n=1)
        assert len(result) == 1
        assert result[0] == Path("/tmp/frame_000001.jpg")

    def test_empty_list(self):
        result = selecionar_frames_visuais([], n=4)
        assert result == []


# ===========================================================================
# _dedup_lotes_espelhados
# ===========================================================================


class TestDedupLotesEspelhados:
    def test_no_mirrors_keeps_all(self):
        lotes = [_consolidado("0001"), _consolidado("0002"), _consolidado("0003")]
        result = _dedup_lotes_espelhados(lotes)
        assert len(result) == 3

    def test_mirror_pair_keeps_more_frames(self):
        """'1000' reversed = '0001'. Same attributes -> keep one with more frames."""
        lotes = [
            _consolidado("1000", frames=3),
            _consolidado("0001", frames=8),
        ]
        result = _dedup_lotes_espelhados(lotes)
        assert len(result) == 1
        assert result[0].lote_numero == "0001"

    def test_mirror_different_raca_and_sexo_keeps_both(self):
        """Different raca AND sexo -> score < 3, not a dup."""
        lotes = [
            _consolidado("1000", raca="Nelore", sexo="macho"),
            _consolidado("0001", raca="Angus", sexo="femea"),
        ]
        result = _dedup_lotes_espelhados(lotes)
        assert len(result) == 2

    def test_mirror_timestamps_far_apart_and_different_qtd_keeps_both(self):
        """Timestamps > 30min AND different qtd -> score < 3, not a dup."""
        lotes = [
            _consolidado("1000", offset_min=0, qtd=10),
            _consolidado("0001", offset_min=60, qtd=20),
        ]
        result = _dedup_lotes_espelhados(lotes)
        assert len(result) == 2

    def test_mirror_different_sexo_keeps_both(self):
        """Different sexo reduces score below threshold."""
        lotes = [
            _consolidado("1000", sexo="macho", raca="Angus"),
            _consolidado("0001", sexo="femea", raca="Nelore"),
        ]
        result = _dedup_lotes_espelhados(lotes)
        assert len(result) == 2

    def test_mirror_same_attributes_close_timestamps(self):
        """All 4 criteria match: definitely a mirror."""
        lotes = [
            _consolidado("1000", frames=10, offset_min=0),
            _consolidado("0001", frames=2, offset_min=5),
        ]
        result = _dedup_lotes_espelhados(lotes)
        assert len(result) == 1
        assert result[0].lote_numero == "1000"  # more frames

    def test_palindrome_not_removed(self):
        """A palindrome like '1001' reversed is itself, should not be removed."""
        lotes = [_consolidado("1001")]
        result = _dedup_lotes_espelhados(lotes)
        assert len(result) == 1


# ===========================================================================
# consolidar_lotes
# ===========================================================================


class TestConsolidarLotes:
    """Tests for consolidar_lotes.

    We patch salvar_frames_visuais (file I/O) and frame_timestamp
    to avoid filesystem dependencies.
    """

    @pytest.fixture(autouse=True)
    def _patch_io(self):
        with (
            patch(
                "leilao_inteligente.pipeline.processor.salvar_frames_visuais",
                return_value=[],
            ),
            patch(
                "leilao_inteligente.pipeline.processor.frame_timestamp",
                return_value=0,
            ),
        ):
            yield

    def test_price_increases_arrematado(self):
        frames = [
            _lcf(preco=1000, offset_min=0, frame_name="frame_000001.jpg"),
            _lcf(preco=2000, offset_min=1, frame_name="frame_000002.jpg"),
            _lcf(preco=3000, offset_min=2, frame_name="frame_000003.jpg"),
        ]
        result = consolidar_lotes(frames)
        assert len(result) == 1
        lote = result[0]
        assert lote.status == "arrematado"
        assert lote.preco_inicial == Decimal("1000")
        assert lote.preco_final == Decimal("3000")

    def test_price_zero_excluded_from_price_calc(self):
        """Frames with preco=0 should not affect preco_inicial/preco_final
        but the lot should still be consolidated."""
        frames = [
            _lcf(preco=0, offset_min=0, frame_name="frame_000001.jpg"),
            _lcf(preco=1000, offset_min=1, frame_name="frame_000002.jpg"),
            _lcf(preco=2000, offset_min=2, frame_name="frame_000003.jpg"),
        ]
        result = consolidar_lotes(frames)
        assert len(result) == 1
        lote = result[0]
        assert lote.preco_inicial == Decimal("1000")
        assert lote.preco_final == Decimal("2000")

    def test_repescagem_detected(self):
        """Gap > 10 min between frames -> repescagem."""
        frames = [
            _lcf(preco=1000, offset_min=0, frame_name="frame_000001.jpg"),
            _lcf(preco=2000, offset_min=5, frame_name="frame_000002.jpg"),
            _lcf(preco=1500, offset_min=20, frame_name="frame_000003.jpg"),
            _lcf(preco=2500, offset_min=25, frame_name="frame_000004.jpg"),
        ]
        result = consolidar_lotes(frames)
        assert len(result) == 1
        lote = result[0]
        assert lote.status == "repescagem"
        assert lote.aparicoes == 2
        # Should use last appearance prices
        assert lote.preco_inicial == Decimal("1500")
        assert lote.preco_final == Decimal("2500")

    def test_single_frame_low_confidence_discarded(self):
        frames = [
            _lcf(preco=1000, offset_min=0, confianca=0.7, frame_name="frame_000001.jpg"),
        ]
        result = consolidar_lotes(frames)
        assert len(result) == 0

    def test_single_frame_high_confidence_kept(self):
        frames = [
            _lcf(preco=1000, offset_min=0, confianca=0.95, frame_name="frame_000001.jpg"),
        ]
        result = consolidar_lotes(frames)
        assert len(result) == 1
        assert result[0].confianca_media == 0.95

    def test_multiple_lot_numbers_separate(self):
        frames = [
            _lcf(numero="0001", preco=1000, offset_min=0, frame_name="frame_000001.jpg"),
            _lcf(numero="0001", preco=2000, offset_min=1, frame_name="frame_000002.jpg"),
            _lcf(numero="0002", preco=5000, offset_min=2, frame_name="frame_000003.jpg"),
            _lcf(numero="0002", preco=6000, offset_min=3, frame_name="frame_000004.jpg"),
        ]
        result = consolidar_lotes(frames)
        assert len(result) == 2
        numeros = {l.lote_numero for l in result}
        assert numeros == {"0001", "0002"}

    def test_all_price_zero_discarded(self):
        """If all frames have preco=0, the lot is discarded."""
        frames = [
            _lcf(preco=0, offset_min=0, frame_name="frame_000001.jpg"),
            _lcf(preco=0, offset_min=1, frame_name="frame_000002.jpg"),
        ]
        result = consolidar_lotes(frames)
        assert len(result) == 0

    def test_preco_por_cabeca_calculated(self):
        frames = [
            _lcf(preco=1000, offset_min=0, qtd=10, frame_name="frame_000001.jpg"),
            _lcf(preco=2000, offset_min=1, qtd=10, frame_name="frame_000002.jpg"),
        ]
        result = consolidar_lotes(frames)
        assert len(result) == 1
        assert result[0].preco_por_cabeca == Decimal("2000") / 10

    def test_frames_analisados_counts_nonzero_price_only(self):
        frames = [
            _lcf(preco=0, offset_min=0, frame_name="frame_000001.jpg"),
            _lcf(preco=1000, offset_min=1, frame_name="frame_000002.jpg"),
            _lcf(preco=2000, offset_min=2, frame_name="frame_000003.jpg"),
        ]
        result = consolidar_lotes(frames)
        assert len(result) == 1
        assert result[0].frames_analisados == 2


# ---------------------------------------------------------------------------
# _identificar_janelas_arrematacao
# ---------------------------------------------------------------------------


class TestIdentificarJanelasArrematacao:
    def test_retorna_janela_apos_ultimo_frame(self):
        """Deve retornar janela de 15s apos o ultimo frame de cada lote."""
        # frame_000100 → (100-1)*5 = 495s
        frames = [
            _lcf("01", preco=3000, frame_name="frame_000100.jpg"),
        ]
        janelas = _identificar_janelas_arrematacao(frames)
        assert "01" in janelas
        inicio, fim = janelas["01"]
        assert inicio == 496  # ultimo_ts + 1
        assert fim == 495 + JANELA_ARREMATACAO_SEGUNDOS

    def test_usa_ultimo_frame_do_lote(self):
        """Com multiplos frames, usa o de maior timestamp."""
        # frame_000100 → 495s, frame_000200 → 995s
        frames = [
            _lcf("01", preco=1000, frame_name="frame_000100.jpg"),
            _lcf("01", preco=2000, frame_name="frame_000200.jpg"),
        ]
        janelas = _identificar_janelas_arrematacao(frames)
        inicio, fim = janelas["01"]
        assert inicio == 996  # (200-1)*5 + 1
        assert fim == 995 + JANELA_ARREMATACAO_SEGUNDOS

    def test_multiplos_lotes_janelas_separadas(self):
        """Cada lote tem sua propria janela."""
        frames = [
            _lcf("01", preco=1000, frame_name="frame_000100.jpg"),
            _lcf("02", preco=2000, frame_name="frame_000200.jpg"),
        ]
        janelas = _identificar_janelas_arrematacao(frames)
        assert len(janelas) == 2
        assert "01" in janelas
        assert "02" in janelas

    def test_ignora_lote_sem_preco(self):
        """Lotes com todos os frames preco=0 nao precisam de arrematacao."""
        frames = [
            _lcf("01", preco=0, frame_name="frame_000100.jpg"),
        ]
        janelas = _identificar_janelas_arrematacao(frames)
        assert len(janelas) == 0

    def test_inclui_frames_preco_zero_no_calculo_de_tempo(self):
        """Frames sem preco ainda contam pro calculo do ultimo timestamp."""
        frames = [
            _lcf("01", preco=3000, frame_name="frame_000100.jpg"),
            _lcf("01", preco=0, frame_name="frame_000200.jpg"),  # ultimo mas sem preco
        ]
        janelas = _identificar_janelas_arrematacao(frames)
        assert "01" in janelas
        inicio, _ = janelas["01"]
        # Deve usar frame_000200 (995s) como ultimo, nao frame_000100 (495s)
        assert inicio == 996


# ===========================================================================
# _filtrar_frames_outliers
# ===========================================================================


class TestFiltrarFramesOutliers:
    def test_sem_outliers(self):
        """Frames proximos nao sao removidos."""
        frames = [
            _lcf("01", offset_min=0),
            _lcf("01", offset_min=1),
            _lcf("01", offset_min=2),
        ]
        resultado = _filtrar_frames_outliers(frames)
        assert len(resultado) == 3

    def test_remove_frame_isolado(self):
        """Frame com gap > 5min do cluster e removido."""
        frames = [
            _lcf("01", offset_min=0),
            _lcf("01", offset_min=1),
            _lcf("01", offset_min=2),
            _lcf("01", offset_min=15),  # 15min depois = outlier
        ]
        resultado = _filtrar_frames_outliers(frames)
        assert len(resultado) == 3

    def test_mantem_maior_cluster(self):
        """Se ha 2 clusters, mantem o maior."""
        frames = [
            _lcf("01", offset_min=0),  # cluster 1 (1 frame)
            _lcf("01", offset_min=10),  # cluster 2 (3 frames)
            _lcf("01", offset_min=11),
            _lcf("01", offset_min=12),
        ]
        resultado = _filtrar_frames_outliers(frames)
        assert len(resultado) == 3

    def test_lote_com_2_frames_nao_filtra(self):
        """Lotes com <= 2 frames nao sao filtrados (pouco dado)."""
        frames = [
            _lcf("01", offset_min=0),
            _lcf("01", offset_min=20),  # longe mas so tem 2
        ]
        resultado = _filtrar_frames_outliers(frames)
        assert len(resultado) == 2

    def test_lotes_diferentes_filtrados_separadamente(self):
        """Cada lote e filtrado independentemente."""
        frames = [
            _lcf("01", offset_min=0),
            _lcf("01", offset_min=1),
            _lcf("01", offset_min=2),
            _lcf("01", offset_min=15),  # outlier do lote 01
            _lcf("02", offset_min=0),
            _lcf("02", offset_min=1),
        ]
        resultado = _filtrar_frames_outliers(frames)
        lote01 = [f for f in resultado if f.lote.lote_numero == "01"]
        lote02 = [f for f in resultado if f.lote.lote_numero == "02"]
        assert len(lote01) == 3
        assert len(lote02) == 2


# ===========================================================================
# _dedup_lotes_por_similaridade
# ===========================================================================


class TestDedupLotesPorSimilaridade:
    def test_lotes_diferentes_mantidos(self):
        """Lotes com dados diferentes nao sao dedup."""
        lotes = [
            _consolidado("01", raca="Nelore", qtd=35),
            _consolidado("02", raca="Angus", qtd=10),
        ]
        resultado = _dedup_lotes_por_similaridade(lotes)
        assert len(resultado) == 2

    def test_detecta_duplicata_por_dados(self):
        """Lotes com numeros diferentes mas mesmos dados = duplicata."""
        lotes = [
            LoteConsolidado(
                lote_numero="0005", quantidade=35, raca="Nelore", sexo="macho",
                preco_inicial=Decimal("3000"), preco_final=Decimal("3290"),
                local_cidade="Crixas", local_estado="GO",
                timestamp_inicio=BASE_TS, frames_analisados=20, confianca_media=0.9,
            ),
            LoteConsolidado(
                lote_numero="2000", quantidade=35, raca="Nelore", sexo="macho",
                preco_inicial=Decimal("3000"), preco_final=Decimal("3290"),
                local_cidade="Crixas", local_estado="GO",
                timestamp_inicio=BASE_TS + timedelta(minutes=5), frames_analisados=3, confianca_media=0.9,
            ),
        ]
        resultado = _dedup_lotes_por_similaridade(lotes)
        assert len(resultado) == 1
        assert resultado[0].lote_numero == "0005"  # mais frames

    def test_nao_dedup_preco_diferente(self):
        """Mesmo perfil mas preco diferente = lotes distintos."""
        lotes = [
            LoteConsolidado(
                lote_numero="01", quantidade=35, raca="Nelore", sexo="macho",
                preco_inicial=Decimal("3000"), preco_final=Decimal("3290"),
                local_cidade="Crixas", local_estado="GO",
                timestamp_inicio=BASE_TS, frames_analisados=10, confianca_media=0.9,
            ),
            LoteConsolidado(
                lote_numero="02", quantidade=35, raca="Nelore", sexo="macho",
                preco_inicial=Decimal("3000"), preco_final=Decimal("4500"),
                local_cidade="Crixas", local_estado="GO",
                timestamp_inicio=BASE_TS + timedelta(minutes=5), frames_analisados=10, confianca_media=0.9,
            ),
        ]
        resultado = _dedup_lotes_por_similaridade(lotes)
        assert len(resultado) == 2

    def test_nao_dedup_tempo_distante(self):
        """Mesmo perfil mas timestamps > 30min = lotes distintos."""
        lotes = [
            LoteConsolidado(
                lote_numero="01", quantidade=35, raca="Nelore", sexo="macho",
                preco_inicial=Decimal("3000"), preco_final=Decimal("3290"),
                local_cidade="Crixas", local_estado="GO",
                timestamp_inicio=BASE_TS, frames_analisados=10, confianca_media=0.9,
            ),
            LoteConsolidado(
                lote_numero="02", quantidade=35, raca="Nelore", sexo="macho",
                preco_inicial=Decimal("3000"), preco_final=Decimal("3290"),
                local_cidade="Crixas", local_estado="GO",
                timestamp_inicio=BASE_TS + timedelta(hours=2), frames_analisados=10, confianca_media=0.9,
            ),
        ]
        resultado = _dedup_lotes_por_similaridade(lotes)
        assert len(resultado) == 2
