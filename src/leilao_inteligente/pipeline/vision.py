"""Extracao de dados de frames via Gemini Flash Vision."""

import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import cv2
import numpy as np
from google import genai
from google.genai.types import GenerateContentConfig, Part

from leilao_inteligente.config import get_settings, DATA_DIR


logger = logging.getLogger(__name__)

FRAME_WIDTH = 640
TOPO_PERCENT = 15   # 15% superior (logos, cidade, hora)
BASE_PERCENT = 55   # 55% inferior (lote, descrição, preço, fazenda)
MAX_PARALELO = 20
CACHE_DIR = DATA_DIR / "gemini_cache"

PROMPT_EXTRACAO = """Extraia os dados do overlay deste frame de leilão de gado brasileiro.

O layout do overlay varia entre casas de leilão. Os dados podem estar em qualquer posição
do frame (topo, centro, inferior, esquerda, direita). Leia todo o frame.

Retorne APENAS um JSON válido neste formato, sem markdown:
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

Regras:
- lote_numero: string exata do número do lote no overlay ("12", "0005", "001A")
- quantidade: número de animais no lote
- raca: Nelore, Angus, Cruzado, Anelorado, Guzera, Senepol, etc (apenas a raça, sem condição reprodutiva)
- sexo: "macho", "femea" ou "misto" (sem acento). Pode aparecer como MACHO(S), FEMEA(S), FÊMEA(S)
- condicao: condição reprodutiva da fêmea: "parida" (com bezerro/cria ao pé), "prenhe" (gestante), "solteira", "desmamada". null se macho ou não informado
- idade_meses: converter para meses. "16 MS" = 16, "2 ANOS" = 24, "36 M" = 36. null se não visível
- pelagem: null se não visível
- preco_lance: valor em R$ por animal (não por lote). Número sem R$, pontos de milhar ou vírgula. 0 se não visível
- local_cidade e local_estado (sigla UF 2 letras). Pode estar em qualquer parte do frame
- fazenda_vendedor: nome do vendedor/fazenda. Pode aparecer como "VENDEDOR:", "FAZ.", ou na faixa acima da descrição
- timestamp_video: data/hora do overlay (DD/MM/AAAA HH:MM:SS). null se não visível
- confianca: 0.0 a 1.0
- Se não for frame de leilão: {"erro": "nao_e_leilao"}
- Se não conseguir ler um campo: null
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


def _cache_key(overlay_bytes: bytes) -> str:
    """Gera chave de cache a partir do hash SHA-256 do overlay."""
    return hashlib.sha256(overlay_bytes).hexdigest()


def _cache_get(key: str) -> dict[str, object] | None:
    """Busca resultado no cache. Retorna None se nao existe."""
    cache_file = CACHE_DIR / f"{key}.json"
    if not cache_file.exists():
        return None
    try:
        return json.loads(cache_file.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _cache_set(key: str, dados: dict[str, object]) -> None:
    """Salva resultado no cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{key}.json"
    cache_file.write_text(json.dumps(dados, ensure_ascii=False))


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


# --- Gemini ---


def _chamar_gemini(client: genai.Client, image_part: Part) -> object:
    """Chama Gemini com retry em rate limit e timeout."""
    max_retries = 3
    for tentativa in range(max_retries):
        try:
            return client.models.generate_content(
                model=MODEL_NAME,
                contents=[PROMPT_EXTRACAO, image_part],
                config=GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=1024,
                    thinking_config={"thinking_budget": 0},
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


def extrair_dados_frame(frame_path: Path) -> dict[str, object] | None:
    """Recorta overlay 420p, envia ao Gemini e extrai dados estruturados."""
    if not frame_path.exists():
        raise FileNotFoundError(f"Frame nao encontrado: {frame_path}")

    try:
        overlay_bytes = _preparar_frame(frame_path)
    except Exception:
        logger.exception("Erro ao recortar overlay: %s", frame_path.name)
        return None

    # Verificar cache
    key = _cache_key(overlay_bytes)
    cached = _cache_get(key)
    if cached is not None:
        logger.debug("Cache hit: %s", frame_path.name)
        return cached

    client = _get_client()

    try:
        image_part = Part.from_bytes(data=overlay_bytes, mime_type="image/jpeg")
        response = _chamar_gemini(client, image_part)
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

    # Primeiro: resolver o que ja tem cache (rapido, sem rede)
    for fp in frames:
        try:
            overlay_bytes = _preparar_frame(fp)
            key = _cache_key(overlay_bytes)
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
            key = _cache_key(overlay_bytes)

            image_part = Part.from_bytes(data=overlay_bytes, mime_type="image/jpeg")
            response = _chamar_gemini(client, image_part)
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
