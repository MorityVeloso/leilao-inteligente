"""Orquestrador do pipeline de processamento de videos."""

import logging
import shutil
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from leilao_inteligente.config import get_settings, DATA_DIR
from leilao_inteligente.models.schemas import LoteConsolidado, LoteExtraido
from leilao_inteligente.pipeline.change_detector import filtrar_frames_relevantes
from leilao_inteligente.pipeline.downloader import baixar_video, extrair_video_id
from leilao_inteligente.pipeline.frame_extractor import extrair_frames, frame_timestamp
from leilao_inteligente.pipeline.validator import validar_lote
from leilao_inteligente.pipeline.vision import extrair_dados_lote


logger = logging.getLogger(__name__)

REPESCAGEM_MIN_MINUTOS = 10
FRAMES_VISUAIS_POR_LOTE = 4
LOTE_FRAMES_DIR = DATA_DIR / "lote_frames"


# Registro que associa um LoteExtraido ao seu frame_path original
class LoteComFrame:
    def __init__(self, lote: LoteExtraido, frame_path: Path):
        self.lote = lote
        self.frame_path = frame_path


def selecionar_frames_visuais(
    frames_do_lote: list[LoteComFrame],
    n: int = FRAMES_VISUAIS_POR_LOTE,
) -> list[Path]:
    """Seleciona N frames equidistantes no tempo pra visualizacao do gado.

    Escolhe frames espacados pra ter angulos diferentes do gado.
    Prioriza frames com maior confianca em caso de empate.
    """
    if len(frames_do_lote) <= n:
        return [f.frame_path for f in frames_do_lote]

    # Selecionar indices equidistantes
    total = len(frames_do_lote)
    step = total / n
    indices = [int(i * step) for i in range(n)]

    # Garantir que nao repete e esta dentro dos limites
    selecionados: list[Path] = []
    for idx in indices:
        idx = min(idx, total - 1)
        path = frames_do_lote[idx].frame_path
        if path not in selecionados:
            selecionados.append(path)

    return selecionados


def salvar_frames_visuais(
    video_id: str,
    lote_numero: str,
    frame_paths: list[Path],
) -> list[str]:
    """Copia frames visuais do lote pra diretorio permanente.

    Returns:
        Lista de paths relativos salvos.
    """
    lote_dir = LOTE_FRAMES_DIR / video_id / lote_numero
    lote_dir.mkdir(parents=True, exist_ok=True)

    salvos: list[str] = []
    for i, src in enumerate(frame_paths):
        dst = lote_dir / f"visual_{i + 1}.jpg"
        shutil.copy2(src, dst)
        salvos.append(str(dst.relative_to(DATA_DIR)))

    return salvos


def consolidar_lotes(
    lotes_com_frame: list[LoteComFrame],
    video_id: str = "",
) -> list[LoteConsolidado]:
    """Agrupa frames por lote e consolida em registros unicos."""
    por_lote: dict[str, list[LoteComFrame]] = defaultdict(list)
    for lcf in lotes_com_frame:
        por_lote[lcf.lote.lote_numero].append(lcf)

    consolidados: list[LoteConsolidado] = []

    for numero, frames_lote in sorted(por_lote.items()):
        # Filtrar frames com preco > 0
        frames_com_preco = [f for f in frames_lote if f.lote.preco_lance > 0]

        if not frames_com_preco:
            logger.debug("Lote %s: todos os frames com preco 0, descartando", numero)
            continue

        if len(frames_com_preco) < 2:
            if frames_com_preco[0].lote.confianca < 0.9:
                logger.debug(
                    "Lote %s: apenas 1 frame com confianca %.0f%%, descartando",
                    numero, frames_com_preco[0].lote.confianca * 100,
                )
                continue

        frames_com_preco.sort(key=lambda x: x.lote.timestamp_frame)

        # Detectar repescagem
        lotes_only = [f.lote for f in frames_com_preco]
        aparicoes = _contar_aparicoes(lotes_only)

        if aparicoes > 1:
            frames_com_preco = _pegar_ultima_aparicao_lcf(frames_com_preco)

        primeiro = frames_com_preco[0].lote
        ultimo = frames_com_preco[-1].lote

        preco_inicial = primeiro.preco_lance
        preco_final = ultimo.preco_lance

        if aparicoes > 1:
            status = "repescagem"
        elif preco_final > preco_inicial:
            status = "arrematado"
        else:
            status = "incerto"

        preco_por_cabeca: Decimal | None = None
        if primeiro.quantidade > 0 and preco_final > 0:
            preco_por_cabeca = preco_final / primeiro.quantidade

        # Selecionar e salvar frames visuais (4 melhores, corpo inteiro do gado)
        # Usa TODOS os frames do lote (incluindo preco 0) pra ter mais opcoes visuais
        todos_frames_lote = [f for f in frames_lote]
        todos_frames_lote.sort(key=lambda x: x.lote.timestamp_frame)
        frames_visuais = selecionar_frames_visuais(todos_frames_lote)
        frame_paths_salvos: list[str] = []
        if video_id and frames_visuais:
            frame_paths_salvos = salvar_frames_visuais(video_id, numero, frames_visuais)

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
            confianca_media=sum(f.lote.confianca for f in frames_com_preco) / len(frames_com_preco),
            aparicoes=aparicoes,
            status=status,
        )
        consolidados.append(consolidado)

    # Deduplicar lotes espelhados (1000 = 0001, etc)
    consolidados = _dedup_lotes_espelhados(consolidados)

    logger.info("Consolidados %d lotes", len(consolidados))
    return consolidados


def _dedup_lotes_espelhados(lotes: list[LoteConsolidado]) -> list[LoteConsolidado]:
    """Remove lotes duplicados por espelhamento de numero.

    O Gemini as vezes le "0001" como "1000" (inverte os digitos).
    Detecta pares espelhados comparando:
    - Numero invertido existe?
    - Mesma raca, sexo, quantidade?
    - Timestamps proximos (< 30 min)?

    Quando encontra par, mantem o lote com mais frames analisados.
    """
    removidos: set[int] = set()
    lotes_por_numero: dict[str, int] = {l.lote_numero: i for i, l in enumerate(lotes)}

    for i, lote in enumerate(lotes):
        if i in removidos:
            continue

        num = lote.lote_numero
        # Tentar inversao: "1000" -> "0001"
        invertido = num[::-1]

        # Tambem tentar com padding: "430" -> "034" -> "0034"? Nao, manter simples
        candidatos = [invertido]

        # Se o numero e so digitos, tentar com zero-padding
        if num.isdigit() and invertido.isdigit():
            invertido_padded = invertido.lstrip("0").zfill(len(num))
            if invertido_padded != invertido:
                candidatos.append(invertido_padded)
            # Tambem tentar com zeros a esquerda no invertido
            invertido_zeros = invertido.zfill(4)
            if invertido_zeros not in candidatos:
                candidatos.append(invertido_zeros)

        for cand in candidatos:
            if cand == num or cand not in lotes_por_numero:
                continue

            j = lotes_por_numero[cand]
            if j in removidos:
                continue

            outro = lotes[j]

            # Verificar similaridade
            mesma_raca = lote.raca.lower() == outro.raca.lower()
            mesmo_sexo = lote.sexo == outro.sexo
            mesma_qtd = lote.quantidade == outro.quantidade

            # Timestamps proximos (< 30 min)
            diff_tempo = abs(
                (lote.timestamp_inicio - outro.timestamp_inicio).total_seconds()
            )
            tempo_proximo = diff_tempo < 30 * 60

            # Precisa de pelo menos 2 criterios alem do numero invertido
            score = sum([mesma_raca, mesmo_sexo, mesma_qtd, tempo_proximo])

            if score >= 3:
                # Manter o que tem mais frames ou maior confianca
                if outro.frames_analisados > lote.frames_analisados:
                    removidos.add(i)
                    logger.info(
                        "Lote espelhado: %s = %s (mantendo %s, %d frames vs %d)",
                        num, cand, cand, outro.frames_analisados, lote.frames_analisados,
                    )
                else:
                    removidos.add(j)
                    logger.info(
                        "Lote espelhado: %s = %s (mantendo %s, %d frames vs %d)",
                        cand, num, num, lote.frames_analisados, outro.frames_analisados,
                    )
                break

    resultado = [l for i, l in enumerate(lotes) if i not in removidos]
    if removidos:
        logger.info("Removidos %d lotes espelhados", len(removidos))
    return resultado


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


def _pegar_ultima_aparicao_lcf(frames: list[LoteComFrame]) -> list[LoteComFrame]:
    """Retorna frames da ultima aparicao (apos ultimo gap grande)."""
    if len(frames) <= 1:
        return frames

    ultimo_gap_idx = 0
    for i in range(1, len(frames)):
        diff = (frames[i].lote.timestamp_frame - frames[i - 1].lote.timestamp_frame).total_seconds()
        if diff > REPESCAGEM_MIN_MINUTOS * 60:
            ultimo_gap_idx = i

    return frames[ultimo_gap_idx:]


def processar_video(url: str) -> list[LoteConsolidado]:
    """Pipeline completo: download → frames → deteccao → extracao → consolidacao."""
    settings = get_settings()
    video_id = extrair_video_id(url)

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

        # 4. Extrair dados via Gemini (overlay 420p, 20 requests paralelos)
        task = progress.add_task(
            "Extraindo dados via Gemini...", total=len(frames_relevantes)
        )

        def _on_frame_done() -> None:
            progress.advance(task)

        resultados_gemini = extrair_dados_lote(
            frames_relevantes, callback=_on_frame_done
        )

        lotes_com_frame: list[LoteComFrame] = []
        for frame_path, dados in resultados_gemini:
            ts_segundos = frame_timestamp(
                frame_path, settings.frame_interval_seconds
            )
            ts = datetime.now(tz=timezone.utc) + timedelta(seconds=ts_segundos)
            lote = validar_lote(dados, timestamp_frame=ts)
            if lote is not None:
                lotes_com_frame.append(LoteComFrame(lote, frame_path))

        progress.update(
            task, description=f"Extraidos {len(lotes_com_frame)} registros validos"
        )

    # 5. Consolidar lotes + salvar frames visuais
    consolidados = consolidar_lotes(lotes_com_frame, video_id=video_id)

    logger.info(
        "Pipeline completo: %d frames → %d relevantes → %d registros → %d lotes",
        len(frames),
        len(frames_relevantes),
        len(lotes_com_frame),
        len(consolidados),
    )

    return consolidados
