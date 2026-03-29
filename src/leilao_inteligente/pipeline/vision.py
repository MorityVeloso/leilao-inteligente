"""Extracao de dados de frames via Gemini Flash Vision."""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import cv2
from google import genai
from google.genai.types import GenerateContentConfig, Part

from leilao_inteligente.config import get_settings


logger = logging.getLogger(__name__)

OVERLAY_WIDTH = 420
MAX_PARALELO = 20

PROMPT_EXTRACAO = """Extraia os dados do overlay deste leilão de gado brasileiro.

Retorne APENAS um JSON válido neste formato, sem markdown:
{
    "lote_numero": "0005",
    "quantidade": 35,
    "raca": "Nelore",
    "sexo": "macho",
    "condicao": "parida",
    "idade_meses": 12,
    "pelagem": null,
    "preco_lance": 3290.00,
    "local_cidade": "Crixás",
    "local_estado": "GO",
    "fazenda_vendedor": "FAZ. JULIANA",
    "timestamp_video": "26/03/2026 20:54:21",
    "confianca": 0.95
}

Regras:
- lote_numero: string exata do overlay ("00", "0005", "001A", "55A")
- quantidade: número de animais
- raca: Nelore, Angus, Cruzado, Anelorado, Guzera, Senepol, etc (apenas a raça, sem condição reprodutiva)
- sexo: "macho", "femea" ou "misto" (sem acento)
- condicao: condição reprodutiva da fêmea. Valores: "parida" (com bezerro/cria ao pé), "prenhe" (gestante), "solteira" (sem cria nem gestação), "desmamada". null se macho ou não informado. Extrair da descrição do lote (ex: "2 NELORE PARIDA - 36 M" → condicao: "parida")
- idade_meses: idade em meses, null se não visível
- pelagem: null (não visível no recorte)
- preco_lance: número sem R$ ou pontos de milhar. 0 se não visível
- local_cidade e local_estado (sigla UF 2 letras)
- fazenda_vendedor: nome da fazenda acima da descrição do gado
- timestamp_video: data/hora exata do overlay (DD/MM/AAAA HH:MM:SS)
- confianca: 0.0 a 1.0
- Se não for overlay de leilão: {"erro": "nao_e_leilao"}
- Se não conseguir ler um campo: null
"""

MODEL_NAME = "gemini-2.5-flash"

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Inicializa e retorna o client Gemini (singleton)."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _recortar_overlay(frame_path: Path, top_percent: int = 70) -> bytes:
    """Recorta a regiao do overlay (inferior) e redimensiona pra 420p."""
    frame = cv2.imread(str(frame_path))
    if frame is None:
        raise ValueError(f"Nao foi possivel ler frame: {frame_path}")

    h, w = frame.shape[:2]
    top_cut = int(h * top_percent / 100)
    overlay = frame[top_cut:, :]

    oh, ow = overlay.shape[:2]
    new_w = OVERLAY_WIDTH
    new_h = int(oh * new_w / ow)
    overlay_resized = cv2.resize(overlay, (new_w, new_h), interpolation=cv2.INTER_AREA)

    _, buf = cv2.imencode(".jpg", overlay_resized, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return buf.tobytes()


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


def extrair_dados_frame(frame_path: Path) -> dict[str, object] | None:
    """Recorta overlay 420p, envia ao Gemini e extrai dados estruturados."""
    if not frame_path.exists():
        raise FileNotFoundError(f"Frame nao encontrado: {frame_path}")

    client = _get_client()

    try:
        overlay_bytes = _recortar_overlay(frame_path)
        image_part = Part.from_bytes(data=overlay_bytes, mime_type="image/jpeg")
        response = _chamar_gemini(client, image_part)
    except Exception:
        logger.exception("Erro ao chamar Gemini para: %s", frame_path.name)
        return None

    if not response.text:
        return None

    dados = _parse_response(response.text)
    if dados:
        logger.debug("Extraido de %s: lote %s", frame_path.name, dados.get("lote_numero"))
    return dados


def extrair_dados_lote(
    frames: list[Path],
    callback: object = None,
) -> list[tuple[Path, dict[str, object]]]:
    """Extrai dados de multiplos frames em paralelo.

    Args:
        frames: Lista de caminhos de frames.
        callback: Funcao chamada apos cada frame (pra progress bar).

    Returns:
        Lista de tuplas (frame_path, dados_extraidos) para frames validos.
    """
    client = _get_client()
    resultados: list[tuple[Path, dict[str, object]]] = []

    def _processar_frame(frame_path: Path) -> tuple[Path, dict[str, object] | None]:
        try:
            overlay_bytes = _recortar_overlay(frame_path)
            image_part = Part.from_bytes(data=overlay_bytes, mime_type="image/jpeg")
            response = _chamar_gemini(client, image_part)
            if response.text:
                dados = _parse_response(response.text)
                return (frame_path, dados)
            return (frame_path, None)
        except Exception:
            logger.debug("Erro em %s", frame_path.name)
            return (frame_path, None)

    with ThreadPoolExecutor(max_workers=MAX_PARALELO) as executor:
        futures = {
            executor.submit(_processar_frame, fp): fp
            for fp in frames
        }

        for future in as_completed(futures):
            frame_path, dados = future.result()
            if dados is not None:
                resultados.append((frame_path, dados))
            if callback:
                callback()

    return resultados
