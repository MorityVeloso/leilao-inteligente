"""Extracao de dados de frames via Gemini Flash Vision.

Suporta dois modos de execucao:
- Online: requests paralelos em tempo real (para ao vivo)
- Batch: upload pro GCS + Batch API com 50% desconto (para videos gravados)
"""

import hashlib
import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

import cv2
import numpy as np
from google import genai
from google.genai.types import CreateBatchJobConfig, GenerateContentConfig, JobState, Part

from leilao_inteligente.config import get_settings, DATA_DIR


logger = logging.getLogger(__name__)

FRAME_WIDTH = 640
TOPO_PERCENT = 15   # 15% superior (logos, cidade, hora)
BASE_PERCENT = 55   # 55% inferior (lote, descrição, preço, fazenda)
MAX_PARALELO = 7
CACHE_DIR = DATA_DIR / "gemini_cache"
BATCH_GCS_PREFIX = "leilao_batch"
BATCH_POLL_INTERVAL = 30  # segundos entre checks de status

PROMPT_EXTRACAO = """Analise este frame de um leilão de gado brasileiro transmitido ao vivo.

A imagem mostra o topo e a base do vídeo concatenados (o meio com o gado foi removido).
O overlay do leilão contém textos sobrepostos com dados do lote sendo leiloado.

Se NÃO houver overlay de lote (pista vazia, intervalo, propaganda, telefones, tela de espera):
{"erro": "nao_e_leilao"}

Se houver overlay com dados do lote, retorne APENAS este JSON sem markdown:
{
    "lote_numero": "12",
    "quantidade": 25,
    "raca": "Nelore",
    "sexo": "femea",
    "condicao": null,
    "idade_meses": 16,
    "pelagem": null,
    "preco_lance": 2680.00,
    "local_cidade": "Rianápolis",
    "local_estado": "GO",
    "fazenda_vendedor": "SITIO BOA SORTE",
    "timestamp_video": null,
    "confianca": 0.95
}

ATENÇÃO — lote_numero vs quantidade:
Em alguns layouts, "LOTE" aparece em uma linha e o NÚMERO DO LOTE aparece na linha de BAIXO (em fonte grande).
A QUANTIDADE de animais aparece ANTES de "MACHO(S)", "VACA(S)", "FEMEA(S)", "NOVILHA(S)".
Exemplo: se o overlay mostra "LOTE" acima, "145" grande abaixo, e "2 VACA(S) NELORE" ao lado,
então lote_numero="145" e quantidade=2 (NÃO o contrário).
O número que vem ANTES da raça/sexo é SEMPRE a quantidade.
O número grande isolado perto de "LOTE" é SEMPRE o número do lote.

Regras:
- lote_numero: número/código do lote. Geralmente em destaque, isolado, perto da palavra "LOTE"
- quantidade: número de animais. SEMPRE aparece ANTES de "MACHO(S)", "VACA(S)", "FEMEA(S)", "NOVILHA(S)"
- raca: Nelore, Anelorado, Mestiço, Guzera, Senepol, Tabapua, Angus (apenas raça, sem condição)
- sexo: "macho", "femea" ou "misto"
- condicao: só fêmeas — "parida", "prenhe", "solteira", "desmamada". null se macho
- idade_meses: converter "16 MS"=16, "2 ANOS"=24, "36 M"=36. null se não visível
- preco_lance: valor em R$ por animal. Leia o número perto de "R$" ou "VALOR POR ANIMAL". Se o campo mostra "R$ ,00" ou "R$ .00" sem valor, retorne 0. Retorne número sem R$, pontos ou vírgula (ex: 2680.00)
- local_cidade: cidade do leilão. Procure no topo do frame, em logos, banners, ou perto de "LIVE". Pode estar em texto pequeno dentro de logos amarelos/coloridos
- local_estado: sigla UF (2 letras). Geralmente junto com a cidade (ex: "Rianápolis-GO")
- fazenda_vendedor: nome do vendedor/fazenda. Aparece como "VENDEDOR:", "FAZ.", "FAZENDA"
- timestamp_video: hora do overlay (DD/MM/AAAA HH:MM:SS ou HH:MM:SS). Procure perto de "LIVE". null se não visível
- confianca: 0.0 a 1.0 (sua confiança na leitura)
- Campo não legível: null (não invente)
"""

MODEL_NAME = "gemini-2.5-flash"

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Inicializa e retorna o client Gemini (singleton).

    Suporta dois backends:
    - aistudio: usa API key (GEMINI_API_KEY). Limite de 10k RPD.
    - vertex: usa Google Cloud (GCP_PROJECT_ID). Pay-as-you-go, sem limite fixo.
    """
    global _client
    if _client is None:
        settings = get_settings()
        if settings.gemini_backend == "vertex":
            _client = genai.Client(
                vertexai=True,
                project=settings.gcp_project_id,
                location=settings.gcp_location,
            )
            logger.info("Gemini via Vertex AI (projeto=%s, regiao=%s)", settings.gcp_project_id, settings.gcp_location)
        else:
            _client = genai.Client(api_key=settings.gemini_api_key)
            logger.info("Gemini via AI Studio")
    return _client


# --- Cache ---


def _cache_key(overlay_bytes: bytes, prompt_hash: str = "") -> str:
    """Gera chave de cache a partir do hash SHA-256 do overlay + prompt."""
    h = hashlib.sha256(overlay_bytes)
    if prompt_hash:
        h.update(prompt_hash.encode())
    return h.hexdigest()


_skip_remote_cache = False  # Flag para pular fallback Supabase (reconsolidação)


def _prompt_hash(prompt: str | None) -> str:
    """Hash curto do prompt customizado (vazio se prompt padrão)."""
    if not prompt or prompt == PROMPT_EXTRACAO:
        return ""
    return hashlib.sha256(prompt.encode()).hexdigest()[:12]


def _cache_get(key: str) -> dict[str, object] | None:
    """Busca resultado no cache local. Se não encontrar, tenta Supabase."""
    cache_file = CACHE_DIR / f"{key}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    if _skip_remote_cache:
        return None

    # Fallback: buscar no Supabase Storage
    dados = _cache_get_remote(key)
    if dados is not None:
        # Salvar localmente para próximas consultas
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(dados, ensure_ascii=False))
    return dados


def _cache_set(key: str, dados: dict[str, object]) -> None:
    """Salva resultado no cache local e no Supabase."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{key}.json"
    cache_file.write_text(json.dumps(dados, ensure_ascii=False))
    _cache_set_remote(key, dados)


def _cache_get_remote(key: str) -> dict[str, object] | None:
    """Busca cache no Supabase Storage."""
    try:
        settings = _get_settings_cached()
        if not settings.supabase_url or not settings.supabase_service_role_key:
            return None
        resp = httpx.get(
            f"{settings.supabase_url}/storage/v1/object/gemini-cache/{key}.json",
            headers={"Authorization": f"Bearer {settings.supabase_service_role_key}"},
            timeout=5,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def _cache_set_remote(key: str, dados: dict[str, object]) -> None:
    """Salva cache no Supabase Storage (fire-and-forget)."""
    try:
        settings = _get_settings_cached()
        if not settings.supabase_url or not settings.supabase_service_role_key:
            return
        httpx.post(
            f"{settings.supabase_url}/storage/v1/object/gemini-cache/{key}.json",
            headers={
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "Content-Type": "application/json",
                "x-upsert": "true",
            },
            content=json.dumps(dados, ensure_ascii=False).encode(),
            timeout=5,
        )
    except Exception:
        pass


def _get_settings_cached():
    """Retorna settings cacheado (evita re-parsear .env a cada chamada)."""
    global _settings_cache
    if _settings_cache is None:
        from leilao_inteligente.config import get_settings
        _settings_cache = get_settings()
    return _settings_cache

_settings_cache = None


# --- Frame ---


def _preparar_frame(frame_path: Path) -> bytes:
    """Recorta topo (15%) + base (50%) do frame, descartando o meio (gado).

    O overlay de leilão fica sempre no topo e na base do frame.
    O meio mostra o gado (irrelevante pra extração de dados).
    Juntar topo+base reduz ~67% dos tokens sem perder informação.
    """
    frame = cv2.imread(str(frame_path))
    if frame is None:
        raise ValueError(f"Nao foi possivel ler frame: {frame_path}")

    h, w = frame.shape[:2]

    topo = frame[0:int(h * TOPO_PERCENT / 100), :]
    base = frame[int(h * (100 - BASE_PERCENT) / 100):, :]

    combinado = np.vstack([topo, base])

    ch, cw = combinado.shape[:2]
    new_h = int(ch * FRAME_WIDTH / cw)
    combinado = cv2.resize(combinado, (FRAME_WIDTH, new_h), interpolation=cv2.INTER_AREA)

    _, buf = cv2.imencode(".jpg", combinado, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return buf.tobytes()


def _preparar_frame_completo(frame_path: Path) -> bytes:
    """Redimensiona frame SEM crop (para detectar carimbo de arrematação no centro).

    Usa 640px — máximo dentro de 1 tile do Gemini (768px), mesmo custo que 320px.
    """
    frame = cv2.imread(str(frame_path))
    if frame is None:
        raise ValueError(f"Nao foi possivel ler frame: {frame_path}")
    h, w = frame.shape[:2]
    new_w = 640
    new_h = int(h * new_w / w)
    frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return buf.tobytes()


PROMPT_CARIMBO = """Olhe esta imagem de um leilão de gado ao vivo.
Há algum indicador visual de VENDA/ARREMATAÇÃO na tela?
Pode estar em qualquer posição (centro, canto, topo, base, lateral).
Exemplos: martelo, selo "VENDIDO", carimbo "ARREMATADO", animação de venda, banner de venda.
NÃO considere textos do overlay normal (preço, lote, fazenda).
Responda APENAS: SIM ou NAO"""


PROMPT_CALIBRACAO = """Olhe estas 2 imagens consecutivas de um leilão de gado ao vivo.
A PRIMEIRA é o frame ANTES. A SEGUNDA é o frame DEPOIS.
Entre os dois, apareceu algum indicador visual de venda/arrematação?

Se SIM, descreva em uma linha:
POSICAO|TEXTO|FORMATO|CORES
Exemplo: centro|VENDIDO|martelo 3D|marrom, branco

Se NÃO há indicador de venda, responda apenas: NAO"""


def detectar_carimbo_arrematacao(frame_path: Path) -> bool:
    """Detecta se frame contém carimbo visual de arrematação (martelo, VENDIDO, etc)."""
    try:
        frame_bytes = _preparar_frame_completo(frame_path)
    except ValueError:
        return False

    key = "stamp_" + _cache_key(frame_bytes)
    cached = _cache_get(key)
    if cached is not None:
        return cached.get("arrematado", False)

    try:
        settings = _get_settings_cached()
        client = genai.Client(api_key=settings.gemini_api_key)
        image_part = Part.from_bytes(data=frame_bytes, mime_type="image/jpeg")
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[PROMPT_CARIMBO, image_part],
            config=GenerateContentConfig(temperature=0.0, max_output_tokens=10),
        )
        resultado = "SIM" in response.text.upper()
        _cache_set(key, {"arrematado": resultado})
        return resultado
    except Exception as e:
        logger.warning("Erro detectando carimbo: %s", e)
        return False


def detectar_carimbo_calibracao(frame_antes_path: Path, frame_depois_path: Path) -> dict | None:
    """Envia par de frames (antes/depois) ao Gemini para identificar padrão do carimbo.

    Retorna dict com posicao, texto, formato, cores. Ou None se não é carimbo.
    """
    try:
        bytes_antes = _preparar_frame_completo(frame_antes_path)
        bytes_depois = _preparar_frame_completo(frame_depois_path)
    except ValueError:
        return None

    key = "calib_" + _cache_key(bytes_antes + bytes_depois)
    cached = _cache_get(key)
    if cached is not None:
        return cached if cached.get("posicao") else None

    try:
        settings = _get_settings_cached()
        client = genai.Client(api_key=settings.gemini_api_key)
        part_antes = Part.from_bytes(data=bytes_antes, mime_type="image/jpeg")
        part_depois = Part.from_bytes(data=bytes_depois, mime_type="image/jpeg")
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[PROMPT_CALIBRACAO, part_antes, part_depois],
            config=GenerateContentConfig(temperature=0.0, max_output_tokens=100),
        )
        texto = response.text.strip().upper()

        if "NAO" in texto and "|" not in texto:
            _cache_set(key, {"arrematado": False})
            return None

        # Parsear: POSICAO|TEXTO|FORMATO|CORES
        partes = texto.split("|")
        resultado = {
            "posicao": partes[0].strip().lower() if len(partes) > 0 else "",
            "texto": partes[1].strip() if len(partes) > 1 else "",
            "formato": partes[2].strip().lower() if len(partes) > 2 else "",
            "cores": partes[3].strip().lower() if len(partes) > 3 else "",
        }
        _cache_set(key, resultado)
        return resultado
    except Exception as e:
        logger.warning("Erro na calibração de carimbo: %s", e)
        return None


def detectar_carimbo_lote(frame_paths: list[Path]) -> bool:
    """Verifica se algum dos frames contém carimbo de arrematação."""
    for fp in frame_paths:
        if detectar_carimbo_arrematacao(fp):
            return True
    return False


# --- Gemini ---


def _chamar_gemini(client: genai.Client, image_part: Part, prompt: str = PROMPT_EXTRACAO) -> object:
    """Chama Gemini com retry em rate limit e timeout."""
    max_retries = 3
    for tentativa in range(max_retries):
        try:
            return client.models.generate_content(
                model=MODEL_NAME,
                contents=[prompt, image_part],
                config=GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=1024,
                ),
            )
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                espera = 15 * (tentativa + 1)
                logger.info("Rate limit, aguardando %ds (%d/%d)", espera, tentativa + 1, max_retries)
                time.sleep(espera)
            elif "timed out" in err.lower() or "ReadTimeout" in type(e).__name__:
                espera = 5 * (tentativa + 1)
                logger.info("Timeout, aguardando %ds (%d/%d)", espera, tentativa + 1, max_retries)
                time.sleep(espera)
            else:
                raise
    raise RuntimeError("Gemini falhou apos todas as tentativas")


def _parse_response(texto: str) -> dict[str, object] | None:
    """Parseia resposta JSON do Gemini."""
    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.split("\n", 1)[1] if "\n" in texto else texto
        if texto.endswith("```"):
            texto = texto[:-3]
        texto = texto.strip()

    try:
        dados = json.loads(texto)
    except json.JSONDecodeError:
        return None

    if "erro" in dados:
        return None

    return dados


# --- API publica ---


def extrair_dados_frame(frame_path: Path, prompt: str | None = None) -> dict[str, object] | None:
    """Recorta overlay 420p, envia ao Gemini e extrai dados estruturados."""
    if not frame_path.exists():
        raise FileNotFoundError(f"Frame nao encontrado: {frame_path}")

    try:
        overlay_bytes = _preparar_frame(frame_path)
    except Exception:
        logger.exception("Erro ao recortar overlay: %s", frame_path.name)
        return None

    # Verificar cache
    ph = _prompt_hash(prompt)
    key = _cache_key(overlay_bytes, ph)
    cached = _cache_get(key)
    if cached is not None:
        logger.debug("Cache hit: %s", frame_path.name)
        return cached

    client = _get_client()

    try:
        image_part = Part.from_bytes(data=overlay_bytes, mime_type="image/jpeg")
        response = _chamar_gemini(client, image_part, prompt=prompt or PROMPT_EXTRACAO)
    except Exception:
        logger.exception("Erro ao chamar Gemini para: %s", frame_path.name)
        return None

    if not response.text:
        return None

    dados = _parse_response(response.text)
    if dados:
        _cache_set(key, dados)
        logger.debug("Extraido de %s: lote %s", frame_path.name, dados.get("lote_numero"))
    return dados


def extrair_dados_lote(
    frames: list[Path],
    callback: object = None,
    prompt: str | None = None,
) -> list[tuple[Path, dict[str, object]]]:
    """Extrai dados de multiplos frames em paralelo.

    Usa cache por hash do overlay: se o frame ja foi processado antes,
    retorna o resultado salvo sem chamar o Gemini.

    Args:
        frames: Lista de caminhos de frames.
        callback: Funcao chamada apos cada frame (pra progress bar).

    Returns:
        Lista de tuplas (frame_path, dados_extraidos) para frames validos.
    """
    resultados: list[tuple[Path, dict[str, object]]] = []
    frames_sem_cache: list[Path] = []
    cache_hits = 0

    ph = _prompt_hash(prompt)

    # Primeiro: resolver o que ja tem cache (rapido, sem rede)
    for fp in frames:
        try:
            overlay_bytes = _preparar_frame(fp)
            key = _cache_key(overlay_bytes, ph)
            cached = _cache_get(key)
            if cached is not None:
                resultados.append((fp, cached))
                cache_hits += 1
                if callback:
                    callback()
            else:
                frames_sem_cache.append(fp)
        except Exception:
            frames_sem_cache.append(fp)

    if cache_hits:
        logger.info("Cache: %d hits, %d misses → %d requests ao Gemini", cache_hits, len(frames_sem_cache), len(frames_sem_cache))

    if not frames_sem_cache:
        return resultados

    # Depois: processar os que nao tem cache em paralelo
    client = _get_client()

    def _processar_frame(frame_path: Path) -> tuple[Path, dict[str, object] | None]:
        try:
            overlay_bytes = _preparar_frame(frame_path)
            key = _cache_key(overlay_bytes, ph)

            image_part = Part.from_bytes(data=overlay_bytes, mime_type="image/jpeg")
            response = _chamar_gemini(client, image_part, prompt=prompt or PROMPT_EXTRACAO)
            if response.text:
                dados = _parse_response(response.text)
                if dados:
                    _cache_set(key, dados)
                return (frame_path, dados)
            return (frame_path, None)
        except Exception:
            logger.debug("Erro em %s", frame_path.name)
            return (frame_path, None)

    with ThreadPoolExecutor(max_workers=MAX_PARALELO) as executor:
        futures = {
            executor.submit(_processar_frame, fp): fp
            for fp in frames_sem_cache
        }

        for future in as_completed(futures):
            frame_path, dados = future.result()
            if dados is not None:
                resultados.append((frame_path, dados))
            if callback:
                callback()

    return resultados


# --- Batch API (50% mais barato, para videos gravados) ---


def _upload_frames_gcs(
    frames_para_upload: list[tuple[Path, bytes, str]],
    bucket_name: str,
    batch_id: str,
) -> dict[str, tuple[Path, str]]:
    """Upload frames preparados para o GCS.

    Returns:
        Dict de gcs_uri → (frame_path, cache_key).
    """
    from google.cloud import storage as gcs

    settings = get_settings()
    gcs_client = gcs.Client(project=settings.gcp_project_id)
    bucket = gcs_client.bucket(bucket_name)

    frame_map: dict[str, tuple[Path, str]] = {}

    for fp, overlay_bytes, key in frames_para_upload:
        blob_name = f"{batch_id}/{key}.jpg"
        blob = bucket.blob(blob_name)
        # FIX 1: timeout para upload individual (evita travamento)
        blob.upload_from_string(overlay_bytes, content_type="image/jpeg", timeout=60)
        gcs_uri = f"gs://{bucket_name}/{blob_name}"
        frame_map[gcs_uri] = (fp, key)

    return frame_map


def _criar_jsonl_batch(
    frame_map: dict[str, tuple[Path, str]],
    bucket_name: str,
    batch_id: str,
    prompt: str | None = None,
) -> str:
    """Cria arquivo JSONL com requests e faz upload pro GCS.

    Returns:
        URI GCS do arquivo JSONL.
    """
    from google.cloud import storage as gcs

    settings = get_settings()
    lines: list[str] = []

    for gcs_uri in frame_map:
        request = {
            "request": {
                "contents": [{
                    "role": "user",
                    "parts": [
                        {"text": prompt or PROMPT_EXTRACAO},
                        {"fileData": {"fileUri": gcs_uri, "mimeType": "image/jpeg"}},
                    ],
                }],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 1024,
                },
            }
        }
        lines.append(json.dumps(request, ensure_ascii=False))

    # FIX 2: verificar que temos linhas antes de fazer upload
    if not lines:
        raise ValueError("Nenhuma linha JSONL gerada")

    gcs_client = gcs.Client(project=settings.gcp_project_id)
    bucket = gcs_client.bucket(bucket_name)
    blob_name = f"{batch_id}/input.jsonl"
    blob = bucket.blob(blob_name)
    blob.upload_from_string("\n".join(lines), content_type="application/jsonl", timeout=120)

    return f"gs://{bucket_name}/{blob_name}"


def _aguardar_batch(client: genai.Client, job: object, timeout_horas: int = 24) -> object:
    """Aguarda conclusao do batch job com polling.

    FIX 3: timeout maximo para evitar polling infinito.
    """
    completed_states = {
        JobState.JOB_STATE_SUCCEEDED,
        JobState.JOB_STATE_FAILED,
        JobState.JOB_STATE_CANCELLED,
    }

    max_polls = (timeout_horas * 3600) // BATCH_POLL_INTERVAL
    polls = 0

    while job.state not in completed_states:
        polls += 1
        if polls > max_polls:
            logger.error("Batch timeout apos %dh de polling", timeout_horas)
            return job

        time.sleep(BATCH_POLL_INTERVAL)
        try:
            job = client.batches.get(name=job.name)
        except Exception as e:
            # FIX 4: erro de rede no polling nao deve matar o job
            logger.warning("Erro ao consultar batch: %s (tentando novamente)", e)
            continue

        logger.info("Batch %s: %s (poll %d)", job.name, job.state, polls)

    return job


def _parsear_resultados_batch(
    bucket_name: str,
    batch_id: str,
    frame_map: dict[str, tuple[Path, str]],
) -> list[tuple[Path, dict[str, object]]]:
    """Baixa e parseia resultados do batch job do GCS."""
    from google.cloud import storage as gcs

    settings = get_settings()
    gcs_client = gcs.Client(project=settings.gcp_project_id)
    bucket = gcs_client.bucket(bucket_name)

    resultados: list[tuple[Path, dict[str, object]]] = []
    erros = 0

    output_blobs = list(bucket.list_blobs(prefix=f"{batch_id}/output/"))

    # FIX 5: log se nao encontrou output
    if not output_blobs:
        logger.warning("Batch: nenhum arquivo de output encontrado em %s/output/", batch_id)
        return resultados

    for output_blob in output_blobs:
        if not output_blob.name.endswith(".jsonl"):
            continue

        content = output_blob.download_as_text()
        for line in content.strip().split("\n"):
            if not line.strip():
                continue

            try:
                result = json.loads(line)
            except json.JSONDecodeError:
                erros += 1
                continue

            # Status vazio = sucesso
            if result.get("status"):
                erros += 1
                logger.debug("Batch request falhou: %s", result["status"])
                continue

            # FIX 6: extrair GCS URI com validacao robusta
            try:
                parts = result.get("request", {}).get("contents", [{}])[0].get("parts", [])
                gcs_uri = next(
                    (p["fileData"]["fileUri"]
                     for p in parts
                     if isinstance(p.get("fileData"), dict)
                     and isinstance(p["fileData"].get("fileUri"), str)),
                    None,
                )
                if gcs_uri is None:
                    erros += 1
                    continue
            except (KeyError, IndexError, TypeError):
                erros += 1
                continue

            if gcs_uri not in frame_map:
                continue

            fp, key = frame_map[gcs_uri]

            # FIX 7: parsear resposta com validacao robusta
            try:
                response = result.get("response", {})
                candidates = response.get("candidates", [])
                if not candidates:
                    erros += 1
                    continue
                content_parts = candidates[0].get("content", {}).get("parts", [])
                if not content_parts:
                    erros += 1
                    continue
                response_text = content_parts[0].get("text", "")
                if not response_text:
                    erros += 1
                    continue
            except (KeyError, IndexError, TypeError):
                erros += 1
                continue

            dados = _parse_response(response_text)
            if dados:
                _cache_set(key, dados)
                resultados.append((fp, dados))

    if erros:
        logger.info("Batch parsing: %d extraidos, %d erros", len(resultados), erros)

    return resultados


def _limpar_gcs_batch(bucket_name: str, batch_id: str) -> None:
    """Remove arquivos temporarios do GCS apos o batch."""
    from google.cloud import storage as gcs

    settings = get_settings()
    try:
        gcs_client = gcs.Client(project=settings.gcp_project_id)
        bucket = gcs_client.bucket(bucket_name)
        blobs = list(bucket.list_blobs(prefix=batch_id))
        if blobs:
            bucket.delete_blobs(blobs)
            logger.info("GCS cleanup: removidos %d arquivos de %s", len(blobs), batch_id)
    except Exception:
        logger.warning("Falha ao limpar GCS %s/%s", bucket_name, batch_id)


def extrair_dados_lote_batch(
    frames: list[Path],
    callback: object = None,
    prompt: str | None = None,
) -> list[tuple[Path, dict[str, object]]]:
    """Extrai dados via Batch API (50% mais barato, para videos gravados).

    Fluxo:
    1. Preparar frames (crop topo+base) e verificar cache local
    2. Upload frames sem cache pro GCS
    3. Criar JSONL e submeter batch job
    4. Aguardar resultado (polling a cada 30s)
    5. Parsear resultados e atualizar cache local
    6. Limpar GCS
    """
    settings = get_settings()

    if not settings.gcs_bucket:
        raise ValueError(
            "GCS_BUCKET nao configurado. Necessario para Batch API. "
            "Configure no .env: GCS_BUCKET=nome-do-bucket"
        )

    if settings.gemini_backend != "vertex":
        raise ValueError("Batch API so funciona com backend Vertex AI. Configure: GEMINI_BACKEND=vertex")

    resultados: list[tuple[Path, dict[str, object]]] = []
    frames_para_upload: list[tuple[Path, bytes, str]] = []
    cache_hits = 0
    ph = _prompt_hash(prompt)

    # 1. Verificar cache local
    for fp in frames:
        try:
            overlay_bytes = _preparar_frame(fp)
            key = _cache_key(overlay_bytes, ph)
            cached = _cache_get(key)
            if cached is not None:
                resultados.append((fp, cached))
                cache_hits += 1
                if callback:
                    callback()
            else:
                frames_para_upload.append((fp, overlay_bytes, key))
        except Exception:
            logger.debug("Erro ao preparar frame %s, pulando", fp.name)

    if cache_hits:
        logger.info(
            "Batch cache: %d hits, %d misses → %d para upload",
            cache_hits, len(frames_para_upload), len(frames_para_upload),
        )

    if not frames_para_upload:
        return resultados

    bucket_name = settings.gcs_bucket
    batch_id = f"{BATCH_GCS_PREFIX}/{uuid.uuid4().hex[:12]}"

    try:
        # 2. Upload frames pro GCS
        logger.info("Batch: uploading %d frames para gs://%s/%s", len(frames_para_upload), bucket_name, batch_id)
        frame_map = _upload_frames_gcs(frames_para_upload, bucket_name, batch_id)
        logger.info("Batch: upload concluido (%d frames)", len(frame_map))

        # 3. Criar JSONL e submeter batch
        jsonl_uri = _criar_jsonl_batch(frame_map, bucket_name, batch_id, prompt=prompt)
        output_uri = f"gs://{bucket_name}/{batch_id}/output/"

        client = _get_client()
        job = client.batches.create(
            model=MODEL_NAME,
            src=jsonl_uri,
            config=CreateBatchJobConfig(dest=output_uri),
        )
        logger.info("Batch job criado: %s (estado: %s)", job.name, job.state)

        # 4. Aguardar conclusao
        job = _aguardar_batch(client, job)

        if job.state != JobState.JOB_STATE_SUCCEEDED:
            logger.error("Batch job falhou: %s", job.state)
            return resultados

        # 5. Parsear resultados
        batch_resultados = _parsear_resultados_batch(bucket_name, batch_id, frame_map)
        resultados.extend(batch_resultados)

        logger.info(
            "Batch concluido: %d extraidos de %d enviados (%d do cache)",
            len(batch_resultados), len(frame_map), cache_hits,
        )

        # Notificar callback para os frames do batch
        if callback:
            for _ in batch_resultados:
                callback()

    finally:
        # FIX: sempre limpar GCS, mesmo em caso de erro
        _limpar_gcs_batch(bucket_name, batch_id)

    # 6. Limpar GCS
    _limpar_gcs_batch(bucket_name, batch_id)

    return resultados
