"""Orquestrador do pipeline de processamento de videos."""

import logging
from collections import defaultdict
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

# Minimo de minutos entre aparicoes do mesmo lote para considerar repescagem
REPESCAGEM_MIN_MINUTOS = 10


def consolidar_lotes(lotes_extraidos: list[LoteExtraido]) -> list[LoteConsolidado]:
    """Agrupa frames por lote e consolida em registros unicos.

    Logica:
    - Agrupa frames pelo lote_numero
    - Descarta frames com preco = 0 (transicao de overlay)
    - Exige 2+ frames concordantes para confirmar lote
    - Detecta repescagem (mesmo lote aparece com gap > 10min)
    - Determina status: arrematado | repescagem | incerto
    """
    # Agrupar por lote
    por_lote: dict[str, list[LoteExtraido]] = defaultdict(list)
    for lote in lotes_extraidos:
        por_lote[lote.lote_numero].append(lote)

    consolidados: list[LoteConsolidado] = []

    for numero, frames_lote in sorted(por_lote.items()):
        # Filtrar frames com preco > 0 (descartar transicoes)
        frames_com_preco = [f for f in frames_lote if f.preco_lance > 0]

        if not frames_com_preco:
            logger.debug("Lote %s: todos os frames com preco 0, descartando", numero)
            continue

        # Exigir 2+ frames para confirmar (evitar frames de transicao sujos)
        # Excecao: se so tem 1 frame mas confianca >= 0.9, aceitar
        if len(frames_com_preco) < 2:
            if frames_com_preco[0].confianca < 0.9:
                logger.debug(
                    "Lote %s: apenas 1 frame com confianca %.0f%%, descartando",
                    numero, frames_com_preco[0].confianca * 100,
                )
                continue

        frames_com_preco.sort(key=lambda x: x.timestamp_frame)

        # Detectar aparicoes (repescagem)
        aparicoes = _contar_aparicoes(frames_com_preco)

        # Usar ultima aparicao como definitiva (repescagem sobrescreve)
        if aparicoes > 1:
            frames_com_preco = _pegar_ultima_aparicao(frames_com_preco)

        primeiro = frames_com_preco[0]
        ultimo = frames_com_preco[-1]

        preco_inicial = primeiro.preco_lance
        preco_final = ultimo.preco_lance

        # Status
        if aparicoes > 1:
            status = "repescagem"
        elif preco_final > preco_inicial:
            status = "arrematado"
        else:
            status = "incerto"

        preco_por_cabeca: Decimal | None = None
        if primeiro.quantidade > 0 and preco_final > 0:
            preco_por_cabeca = preco_final / primeiro.quantidade

        consolidado = LoteConsolidado(
            lote_numero=primeiro.lote_numero,
            quantidade=primeiro.quantidade,
            raca=primeiro.raca,
            sexo=primeiro.sexo,
            idade_meses=primeiro.idade_meses,
            pelagem=primeiro.pelagem,
            preco_inicial=preco_inicial,
            preco_final=preco_final,
            preco_por_cabeca=preco_por_cabeca,
            local_cidade=primeiro.local_cidade,
            local_estado=primeiro.local_estado,
            fazenda_vendedor=primeiro.fazenda_vendedor,
            timestamp_inicio=primeiro.timestamp_frame,
            timestamp_fim=ultimo.timestamp_frame,
            timestamp_video_inicio=primeiro.timestamp_video,
            timestamp_video_fim=ultimo.timestamp_video,
            frames_analisados=len(frames_com_preco),
            confianca_media=sum(f.confianca for f in frames_com_preco) / len(frames_com_preco),
            aparicoes=aparicoes,
            status=status,
        )
        consolidados.append(consolidado)

    logger.info("Consolidados %d lotes", len(consolidados))
    return consolidados


def _contar_aparicoes(frames: list[LoteExtraido]) -> int:
    """Conta quantas vezes um lote apareceu (separado por gaps > REPESCAGEM_MIN_MINUTOS)."""
    if len(frames) <= 1:
        return 1

    aparicoes = 1
    for i in range(1, len(frames)):
        diff = (frames[i].timestamp_frame - frames[i - 1].timestamp_frame).total_seconds()
        if diff > REPESCAGEM_MIN_MINUTOS * 60:
            aparicoes += 1

    return aparicoes


def _pegar_ultima_aparicao(frames: list[LoteExtraido]) -> list[LoteExtraido]:
    """Retorna frames da ultima aparicao (apos ultimo gap grande)."""
    if len(frames) <= 1:
        return frames

    ultimo_gap_idx = 0
    for i in range(1, len(frames)):
        diff = (frames[i].timestamp_frame - frames[i - 1].timestamp_frame).total_seconds()
        if diff > REPESCAGEM_MIN_MINUTOS * 60:
            ultimo_gap_idx = i

    return frames[ultimo_gap_idx:]


def processar_video(url: str) -> list[LoteConsolidado]:
    """Pipeline completo: download → frames → deteccao → extracao → consolidacao."""
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
