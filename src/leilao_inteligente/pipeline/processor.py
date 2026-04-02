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
from leilao_inteligente.pipeline.downloader import baixar_video, extrair_video_id
from leilao_inteligente.pipeline.frame_extractor import extrair_frames, extrair_frames_janela, frame_timestamp
from leilao_inteligente.pipeline.validator import validar_lote
from leilao_inteligente.pipeline.vision import extrair_dados_lote, extrair_dados_lote_batch


logger = logging.getLogger(__name__)

REPESCAGEM_MIN_MINUTOS = 10
FRAMES_VISUAIS_POR_LOTE = 4
JANELA_ARREMATACAO_SEGUNDOS = 5
OUTLIER_GAP_SEGUNDOS = 300  # 5 min — frame isolado do cluster principal


def _valor_mais_frequente_decimal(valores: list) -> Decimal | None:
    """Retorna o valor decimal mais frequente, ou None se vazio."""
    if not valores:
        return None
    contagem: dict[Decimal, int] = {}
    for v in valores:
        if v is not None:
            key = Decimal(str(v))
            contagem[key] = contagem.get(key, 0) + 1
    if not contagem:
        return None
    return max(contagem, key=contagem.get)  # type: ignore[arg-type]


def _valor_mais_frequente(valores: list[str | None]) -> str | None:
    """Retorna o valor nao-None mais frequente de uma lista, ou None."""
    contagem: dict[str, int] = {}
    for v in valores:
        if v is not None:
            contagem[v] = contagem.get(v, 0) + 1
    if not contagem:
        return None
    return max(contagem, key=contagem.get)  # type: ignore[arg-type]


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
    """Upload frames visuais do lote para Supabase Storage.

    Returns:
        Lista de storage paths salvos (ex: video_id/lote/visual_1.jpg).
    """
    from leilao_inteligente.storage.supabase_storage import upload_frame_file

    salvos: list[str] = []
    for i, src in enumerate(frame_paths):
        storage_path = f"{video_id}/{lote_numero}/visual_{i + 1}.jpg"
        url = upload_frame_file(storage_path, src)
        if url:
            salvos.append(storage_path)

    return salvos


def _filtrar_frames_outliers(
    lotes_com_frame: list[LoteComFrame],
) -> list[LoteComFrame]:
    """Remove frames temporalmente isolados do cluster principal de cada lote.

    O Gemini as vezes le o numero do lote errado em frames de transicao,
    associando um frame de outro lote ao lote errado. Esses frames ficam
    isolados temporalmente (>5min do cluster principal).

    Usa DBSCAN simplificado: encontra o maior cluster de frames proximos
    e descarta os outliers.
    """
    por_lote: dict[str, list[LoteComFrame]] = defaultdict(list)
    for lcf in lotes_com_frame:
        por_lote[lcf.lote.lote_numero].append(lcf)

    resultado: list[LoteComFrame] = []
    total_removidos = 0

    for numero, frames in por_lote.items():
        if len(frames) <= 2:
            resultado.extend(frames)
            continue

        # Ordenar por timestamp
        frames.sort(key=lambda x: x.lote.timestamp_frame)

        # Agrupar em clusters por proximidade temporal
        clusters: list[list[LoteComFrame]] = [[frames[0]]]
        for f in frames[1:]:
            diff = (f.lote.timestamp_frame - clusters[-1][-1].lote.timestamp_frame).total_seconds()
            if diff <= OUTLIER_GAP_SEGUNDOS:
                clusters[-1].append(f)
            else:
                clusters.append([f])

        # Manter apenas os clusters maiores (se empate, pode ser repescagem legítima)
        maior_tamanho = max(len(c) for c in clusters)
        clusters_maiores = [c for c in clusters if len(c) == maior_tamanho]
        frames_mantidos = [f for c in clusters_maiores for f in c]

        removidos = len(frames) - len(frames_mantidos)
        if removidos > 0:
            total_removidos += removidos
            logger.info(
                "Lote %s: removidos %d frames outliers (%d clusters, mantendo %d de %d clusters maiores)",
                numero, removidos, len(clusters), len(frames_mantidos), len(clusters_maiores),
            )

        resultado.extend(frames_mantidos)

    if total_removidos:
        logger.info("Total frames outliers removidos: %d", total_removidos)
    return resultado


def _dedup_lotes_por_similaridade(lotes: list[LoteConsolidado]) -> list[LoteConsolidado]:
    """Remove lotes duplicados por similaridade de dados (nao so por numero invertido).

    O Gemini le o mesmo overlay como numeros diferentes (ex: 0005 e 2000).
    Detecta pares comparando raca, sexo, quantidade, preco e timestamps,
    independente do numero do lote.
    """
    removidos: set[int] = set()

    for i in range(len(lotes)):
        if i in removidos:
            continue

        for j in range(i + 1, len(lotes)):
            if j in removidos:
                continue

            a, b = lotes[i], lotes[j]

            mesma_raca = a.raca.lower() == b.raca.lower()
            mesmo_sexo = a.sexo == b.sexo
            mesma_qtd = a.quantidade == b.quantidade
            mesmo_preco = a.preco_final == b.preco_final

            diff_tempo = abs(
                (a.timestamp_inicio - b.timestamp_inicio).total_seconds()
            )
            tempo_proximo = diff_tempo < 30 * 60

            # Precisa de: mesmo preco + mesma qtd + tempo proximo + pelo menos 1 de (raca, sexo)
            if mesmo_preco and mesma_qtd and tempo_proximo and (mesma_raca or mesmo_sexo):
                # Manter o com mais frames
                if b.frames_analisados > a.frames_analisados:
                    removidos.add(i)
                    logger.info(
                        "Lote duplicado: %s = %s (mantendo %s, %d frames vs %d)",
                        a.lote_numero, b.lote_numero, b.lote_numero,
                        b.frames_analisados, a.frames_analisados,
                    )
                    break  # i foi removido, sair do loop j
                else:
                    removidos.add(j)
                    logger.info(
                        "Lote duplicado: %s = %s (mantendo %s, %d frames vs %d)",
                        b.lote_numero, a.lote_numero, a.lote_numero,
                        a.frames_analisados, b.frames_analisados,
                    )

    resultado = [l for i, l in enumerate(lotes) if i not in removidos]
    if removidos:
        logger.info("Removidos %d lotes duplicados por similaridade", len(removidos))
    return resultado


def consolidar_lotes(
    lotes_com_frame: list[LoteComFrame],
    video_id: str = "",
) -> list[LoteConsolidado]:
    """Agrupa frames por lote e consolida em registros unicos."""
    # Filtrar frames outliers antes de agrupar
    lotes_com_frame = _filtrar_frames_outliers(lotes_com_frame)

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

        # Preço inicial: moda dos primeiros frames (evita outlier de transição)
        # Se todos forem diferentes, usa mediana dos primeiros
        primeiros_precos = [f.lote.preco_lance for f in frames_com_preco[:5] if f.lote.preco_lance > 0]
        moda_inicial = _valor_mais_frequente_decimal(primeiros_precos)
        if moda_inicial and primeiros_precos.count(moda_inicial) > 1:
            preco_inicial = moda_inicial
        else:
            preco_inicial = primeiro.preco_lance

        # Preço final: moda dos últimos frames
        ultimos_precos = [f.lote.preco_lance for f in frames_com_preco[-5:] if f.lote.preco_lance > 0]
        moda_final = _valor_mais_frequente_decimal(ultimos_precos)
        if moda_final and ultimos_precos.count(moda_final) > 1:
            preco_final = moda_final
        else:
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

        # Pegar fazenda e condicao mais frequente entre todos os frames (nao so o primeiro)
        # O primeiro frame muitas vezes nao tem fazenda porque o overlay ainda esta carregando
        fazenda_final = _valor_mais_frequente(
            [f.lote.fazenda_vendedor for f in frames_com_preco]
        )
        condicao_final = _valor_mais_frequente(
            [f.lote.condicao for f in frames_com_preco]
        )

        # Selecionar e salvar frames visuais (4 melhores, corpo inteiro do gado)
        # Usa TODOS os frames do lote (incluindo preco 0) pra ter mais opcoes visuais
        todos_frames_lote = [f for f in frames_lote]
        todos_frames_lote.sort(key=lambda x: x.lote.timestamp_frame)
        frames_visuais = selecionar_frames_visuais(todos_frames_lote)
        frame_paths_salvos: list[str] = []
        if video_id and frames_visuais:
            frame_paths_salvos = salvar_frames_visuais(video_id, numero, frames_visuais)

        # Calcular segundo_video a partir do primeiro frame
        segundo_video_val: int | None = None
        try:
            segundo_video_val = int(frame_timestamp(frames_com_preco[0].frame_path, 5))
        except (ValueError, IndexError):
            pass

        consolidado = LoteConsolidado(
            lote_numero=primeiro.lote_numero,
            quantidade=primeiro.quantidade,
            raca=primeiro.raca,
            sexo=primeiro.sexo,
            condicao=condicao_final,
            idade_meses=primeiro.idade_meses,
            pelagem=primeiro.pelagem,
            preco_inicial=preco_inicial,
            preco_final=preco_final,
            preco_por_cabeca=preco_por_cabeca,
            local_cidade=primeiro.local_cidade,
            local_estado=primeiro.local_estado,
            fazenda_vendedor=fazenda_final,
            timestamp_inicio=primeiro.timestamp_frame,
            timestamp_fim=ultimo.timestamp_frame,
            timestamp_video_inicio=primeiro.timestamp_video,
            timestamp_video_fim=ultimo.timestamp_video,
            frames_analisados=len(frames_com_preco),
            confianca_media=sum(f.lote.confianca for f in frames_com_preco) / len(frames_com_preco),
            aparicoes=aparicoes,
            status=status,
            frame_paths=frame_paths_salvos,
            segundo_video=segundo_video_val,
        )
        consolidados.append(consolidado)

    # Deduplicar lotes espelhados (1000 = 0001, etc)
    consolidados = _dedup_lotes_espelhados(consolidados)

    # Deduplicar por similaridade de dados (Gemini le mesmo lote como numeros diferentes)
    consolidados = _dedup_lotes_por_similaridade(consolidados)

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

            # Quantidade diferente = lotes diferentes com certeza
            if not mesma_qtd:
                continue

            # Precisa de pelo menos 3 criterios (qtd obrigatoria + 2 de raca/sexo/tempo)
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


def processar_video(
    url: str,
    batch: bool = False,
    on_progress: object = None,
) -> list[LoteConsolidado]:
    """Pipeline completo: download → frames → deteccao → extracao → consolidacao.

    Args:
        url: URL do video no YouTube.
        batch: Se True, usa Batch API (50% mais barato, ate 24h).
               Usar apenas para videos gravados, nunca para ao vivo.
        on_progress: Callback(fase: str) chamado a cada mudanca de fase.
    """
    settings = get_settings()
    extrair_fn = extrair_dados_lote_batch if batch else extrair_dados_lote
    _notify = on_progress if callable(on_progress) else lambda _: None

    if batch:
        logger.info("Modo BATCH ativado (50%% desconto, processamento assincrono)")
    video_id = extrair_video_id(url)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ) as progress:

        # 1. Download
        _notify("baixando_video")
        task = progress.add_task("Baixando video...", total=None)
        video_path = baixar_video(url, cookies_file=settings.cookies_path)
        progress.update(task, completed=True, description="Video baixado")

        # 2. Extrair frames
        _notify("extraindo_frames")
        task = progress.add_task("Extraindo frames...", total=None)
        frames = extrair_frames(video_path, intervalo_segundos=settings.frame_interval_seconds)
        progress.update(task, completed=True, description=f"Extraidos {len(frames)} frames")

        # 3. Filtrar frames relevantes
        _notify("detectando_mudancas")
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
        _notify("analisando_ia")
        task = progress.add_task(
            "Extraindo dados via Gemini...", total=len(frames_relevantes)
        )

        def _on_frame_done() -> None:
            progress.advance(task)

        resultados_gemini = extrair_fn(
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

    # 5. Consolidar lotes (passada 1)
    _notify("consolidando")
    consolidados = consolidar_lotes(lotes_com_frame, video_id=video_id)

    logger.info(
        "Passada 1: %d frames → %d relevantes → %d registros → %d lotes",
        len(frames),
        len(frames_relevantes),
        len(lotes_com_frame),
        len(consolidados),
    )

    # 6. Passada 2: refinar lotes com poucos frames (< 4 com preco)
    lotes_refinar = _identificar_lotes_pra_refinar(lotes_com_frame, min_frames=4)

    if lotes_refinar:
        _notify("refinando")
        logger.info("Passada 2: refinando %d lotes com poucos frames", len(lotes_refinar))

        novos_lcfs = _refinar_lotes(
            video_path, lotes_refinar, lotes_com_frame, settings.frame_interval_seconds,
            extrair_fn=extrair_fn,
        )

        if novos_lcfs:
            # Juntar com os originais e reconsolidar
            lotes_com_frame.extend(novos_lcfs)
            consolidados = consolidar_lotes(lotes_com_frame, video_id=video_id)

            logger.info(
                "Passada 2: +%d frames → %d lotes finais",
                len(novos_lcfs), len(consolidados),
            )

    # 7. Passada 3: capturar lance de arrematacao (ultimos segundos de cada lote)
    janelas_arrematacao = _identificar_janelas_arrematacao(lotes_com_frame)

    if janelas_arrematacao:
        _notify("capturando_arrematacao")
        logger.info("Passada 3: capturando arrematacao de %d lotes", len(janelas_arrematacao))

        novos_lcfs_arremate = _refinar_lotes(
            video_path, janelas_arrematacao, lotes_com_frame, settings.frame_interval_seconds,
            extrair_fn=extrair_fn,
        )

        if novos_lcfs_arremate:
            lotes_com_frame.extend(novos_lcfs_arremate)
            consolidados = consolidar_lotes(lotes_com_frame, video_id=video_id)

            logger.info(
                "Passada 3: +%d frames → %d lotes finais",
                len(novos_lcfs_arremate), len(consolidados),
            )

    return consolidados


# Minimo de frames com preco pra considerar lote bem coberto
MIN_FRAMES_BEM_COBERTO = 4


def _identificar_lotes_pra_refinar(
    lotes_com_frame: list[LoteComFrame],
    min_frames: int = MIN_FRAMES_BEM_COBERTO,
) -> dict[str, tuple[float, float]]:
    """Identifica lotes com poucos frames e suas janelas de tempo no video.

    Returns:
        Dict de lote_numero → (inicio_segundos, fim_segundos) no video.
    """
    from leilao_inteligente.pipeline.frame_extractor import frame_timestamp

    por_lote: dict[str, list[LoteComFrame]] = defaultdict(list)
    for lcf in lotes_com_frame:
        por_lote[lcf.lote.lote_numero].append(lcf)

    refinar: dict[str, tuple[float, float]] = {}

    for numero, frames in por_lote.items():
        frames_com_preco = [f for f in frames if f.lote.preco_lance > 0]

        if len(frames_com_preco) >= min_frames:
            continue  # Ja tem frames suficientes

        if not frames:
            continue

        # Calcular janela de tempo no video (com margem de 15s antes e depois)
        timestamps = []
        for f in frames:
            # Extrair timestamp do nome do frame
            nome = f.frame_path.stem
            try:
                num = int(nome.split("_")[1])
                ts = (num - 1) * 5  # intervalo de 5s da passada 1
                timestamps.append(ts)
            except (ValueError, IndexError):
                continue

        if not timestamps:
            continue

        # Janela centrada no ultimo timestamp (onde o lote ainda estava na tela)
        # Margem de 5s antes e 10s depois (capturar arrematacao)
        ultimo_ts = max(timestamps)
        inicio = max(0, ultimo_ts - 5)
        fim = ultimo_ts + 10

        refinar[numero] = (inicio, fim)

    return refinar


def _identificar_janelas_arrematacao(
    lotes_com_frame: list[LoteComFrame],
) -> dict[str, tuple[float, float]]:
    """Identifica janela final de cada lote para capturar o lance de arrematacao.

    O change detector pode perder o ultimo lance porque a mudanca de 1 digito
    no preco (ex: 4600 → 4700) fica abaixo do threshold. Esta funcao retorna
    uma janela de JANELA_ARREMATACAO_SEGUNDOS apos o ultimo frame de cada lote,
    para extrair frames de 1s e capturar o preco final real.

    Returns:
        Dict de lote_numero → (inicio_segundos, fim_segundos) no video.
    """
    por_lote: dict[str, list[LoteComFrame]] = defaultdict(list)
    for lcf in lotes_com_frame:
        por_lote[lcf.lote.lote_numero].append(lcf)

    janelas: dict[str, tuple[float, float]] = {}

    for numero, frames in por_lote.items():
        frames_com_preco = [f for f in frames if f.lote.preco_lance > 0]
        if not frames_com_preco:
            continue

        # Extrair timestamps dos frames
        timestamps: list[float] = []
        for f in frames:
            nome = f.frame_path.stem
            parts = nome.split("_")
            try:
                num = int(parts[1])
                # Detectar se e frame de refine (refine_INICIO_NUM) ou normal (frame_NUM)
                if parts[0] == "refine":
                    inicio_seg = int(parts[1])
                    frame_num = int(parts[2])
                    ts = inicio_seg + (frame_num - 1)
                else:
                    ts = (num - 1) * 5
                timestamps.append(ts)
            except (ValueError, IndexError):
                continue

        if not timestamps:
            continue

        ultimo_ts = max(timestamps)
        # Janela: do ultimo frame ate JANELA_ARREMATACAO_SEGUNDOS depois
        inicio = ultimo_ts + 1  # nao repetir o ultimo frame ja capturado
        fim = ultimo_ts + JANELA_ARREMATACAO_SEGUNDOS

        janelas[numero] = (inicio, fim)

    return janelas


def _refinar_lotes(
    video_path: Path,
    lotes_refinar: dict[str, tuple[float, float]],
    lotes_existentes: list[LoteComFrame],
    intervalo_original: int,
    extrair_fn: object = None,
) -> list[LoteComFrame]:
    """Passada 2/3: extrai frames de 1s nas janelas dos lotes com poucos frames.

    Envia ao Gemini (online ou batch) e retorna novos LoteComFrame pra integrar.
    """
    if extrair_fn is None:
        extrair_fn = extrair_dados_lote
    from leilao_inteligente.config import FRAMES_DIR

    video_name = video_path.stem
    refine_dir = FRAMES_DIR / video_name / "refine"
    refine_dir.mkdir(parents=True, exist_ok=True)

    # Extrair frames de 1s pra cada janela
    todos_frames: list[tuple[str, Path]] = []  # (lote_numero, frame_path)
    frame_lote_esperado: dict[str, str] = {}  # frame_path.name → lote_numero esperado

    for numero, (inicio, fim) in lotes_refinar.items():
        frames = extrair_frames_janela(
            video_path, inicio, fim, refine_dir, intervalo_segundos=1,
        )
        for fp in frames:
            todos_frames.append((numero, fp))
            frame_lote_esperado[fp.name] = numero

    if not todos_frames:
        return []

    logger.info("Passada 2: extraidos %d frames de %d lotes", len(todos_frames), len(lotes_refinar))

    # Enviar ao Gemini (online ou batch)
    frame_paths = [fp for _, fp in todos_frames]
    resultados = extrair_fn(frame_paths)

    # Validar e criar LoteComFrame
    novos: list[LoteComFrame] = []
    descartados = 0
    for frame_path, dados in resultados:
        # Calcular timestamp aproximado
        nome = frame_path.stem  # "refine_1200_0003"
        parts = nome.split("_")
        try:
            inicio_seg = int(parts[1])
            frame_num = int(parts[2])
            ts_seg = inicio_seg + (frame_num - 1)
        except (ValueError, IndexError):
            ts_seg = 0

        ts = datetime.now(tz=timezone.utc) + timedelta(seconds=ts_seg)
        lote = validar_lote(dados, timestamp_frame=ts)
        if lote is None:
            continue

        # Verificar se o lote extraido corresponde ao esperado
        # (passada 3 pode capturar frames do lote seguinte apos a arrematacao)
        esperado = frame_lote_esperado.get(frame_path.name)
        if esperado is not None and lote.lote_numero != esperado:
            descartados += 1
            logger.debug(
                "Frame %s: lote extraido %s != esperado %s, descartando",
                frame_path.name, lote.lote_numero, esperado,
            )
            continue

        novos.append(LoteComFrame(lote, frame_path))

    if descartados:
        logger.info("Passada 2: descartados %d frames de lotes diferentes", descartados)
    logger.info("Passada 2: %d registros validos de %d frames", len(novos), len(frame_paths))
    return novos
