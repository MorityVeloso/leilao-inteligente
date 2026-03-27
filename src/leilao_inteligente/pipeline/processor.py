"""Orquestrador do pipeline de processamento de videos."""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from leilao_inteligente.config import get_settings
from leilao_inteligente.models.schemas import LoteConsolidado, LoteExtraido
from leilao_inteligente.pipeline.change_detector import filtrar_frames_relevantes
from leilao_inteligente.pipeline.downloader import baixar_video, obter_info_video
from leilao_inteligente.pipeline.frame_extractor import extrair_frames, frame_timestamp
from leilao_inteligente.pipeline.validator import validar_lote
from leilao_inteligente.pipeline.vision import extrair_dados_frame


logger = logging.getLogger(__name__)


def consolidar_lotes(lotes_extraidos: list[LoteExtraido]) -> list[LoteConsolidado]:
    """Agrupa frames por lote e consolida em registros unicos.

    Para cada lote:
    - Primeiro frame → preco_lance_inicial
    - Ultimo frame → preco_arrematacao
    - Calcula preco_por_cabeca
    - Calcula confianca media
    """
    por_lote: dict[int, list[LoteExtraido]] = {}
    for lote in lotes_extraidos:
        por_lote.setdefault(lote.lote_numero, []).append(lote)

    consolidados: list[LoteConsolidado] = []

    for _numero, frames_lote in sorted(por_lote.items()):
        frames_lote.sort(key=lambda x: x.timestamp_frame)
        primeiro = frames_lote[0]
        ultimo = frames_lote[-1]

        preco_arrematacao = ultimo.preco_lance
        preco_por_cabeca: Decimal | None = None
        if primeiro.quantidade > 0:
            preco_por_cabeca = preco_arrematacao / primeiro.quantidade

        consolidado = LoteConsolidado(
            lote_numero=primeiro.lote_numero,
            quantidade=primeiro.quantidade,
            raca=primeiro.raca,
            sexo=primeiro.sexo,
            idade_meses=primeiro.idade_meses,
            pelagem=primeiro.pelagem,
            preco_lance_inicial=primeiro.preco_lance,
            preco_arrematacao=preco_arrematacao,
            preco_por_cabeca=preco_por_cabeca,
            local_cidade=primeiro.local_cidade,
            local_estado=primeiro.local_estado,
            timestamp_inicio=primeiro.timestamp_frame,
            timestamp_fim=ultimo.timestamp_frame,
            frames_analisados=len(frames_lote),
            confianca_media=sum(f.confianca for f in frames_lote) / len(frames_lote),
        )
        consolidados.append(consolidado)

    logger.info("Consolidados %d lotes", len(consolidados))
    return consolidados


def processar_video(url: str) -> list[LoteConsolidado]:
    """Pipeline completo: download → frames → deteccao → extracao → consolidacao.

    Args:
        url: URL do video no YouTube.

    Returns:
        Lista de lotes consolidados extraidos do video.
    """
    settings = get_settings()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ) as progress:

        # 1. Download
        task = progress.add_task("Baixando video...", total=None)
        video_path = baixar_video(url, cookies_file=settings.yt_dlp_cookies_file)
        progress.update(task, completed=True, description="Video baixado")

        # 2. Extrair frames
        task = progress.add_task("Extraindo frames...", total=None)
        frames = extrair_frames(video_path, intervalo_segundos=settings.frame_interval_seconds)
        progress.update(task, completed=True, description=f"Extraidos {len(frames)} frames")

        # 3. Filtrar frames relevantes
        task = progress.add_task("Detectando mudancas...", total=None)
        frames_relevantes = filtrar_frames_relevantes(
            frames,
            top_percent=settings.overlay_region_top_percent,
            threshold=settings.change_threshold,
        )
        progress.update(
            task, completed=True,
            description=f"Relevantes: {len(frames_relevantes)} de {len(frames)}"
        )

        # 4. Extrair dados via Gemini
        task = progress.add_task(
            "Extraindo dados via Gemini...", total=len(frames_relevantes)
        )
        lotes_extraidos: list[LoteExtraido] = []

        for frame_path in frames_relevantes:
            dados = extrair_dados_frame(frame_path)
            if dados is not None:
                ts_segundos = frame_timestamp(
                    frame_path, settings.frame_interval_seconds
                )
                ts = datetime.now(tz=timezone.utc) + timedelta(seconds=ts_segundos)

                lote = validar_lote(dados, timestamp_frame=ts)
                if lote is not None:
                    lotes_extraidos.append(lote)

            progress.advance(task)

        progress.update(
            task, description=f"Extraidos {len(lotes_extraidos)} registros validos"
        )

    # 5. Consolidar lotes
    consolidados = consolidar_lotes(lotes_extraidos)

    logger.info(
        "Pipeline completo: %d frames → %d relevantes → %d registros → %d lotes",
        len(frames),
        len(frames_relevantes),
        len(lotes_extraidos),
        len(consolidados),
    )

    return consolidados
