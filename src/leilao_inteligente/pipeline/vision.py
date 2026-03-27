"""Extracao de dados de frames via Gemini Flash Vision."""

import json
import logging
from pathlib import Path

import cv2
from google import genai
from google.genai.types import GenerateContentConfig, Part

from leilao_inteligente.config import get_settings


logger = logging.getLogger(__name__)

# Largura do overlay recortado enviado ao Gemini (420p)
OVERLAY_WIDTH = 420

PROMPT_EXTRACAO = """Extraia os dados do overlay deste leilão de gado brasileiro.

Retorne APENAS um JSON válido neste formato, sem markdown:
{
    "lote_numero": "0005",
    "quantidade": 35,
    "raca": "Nelore",
    "sexo": "macho",
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
- raca: Nelore, Angus, Cruzado, Anelorado, Guzera, Senepol, etc
- sexo: "macho", "femea" ou "misto" (sem acento)
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
    """Recorta a regiao do overlay (inferior) e redimensiona pra 420p.

    Args:
        frame_path: Caminho do frame JPEG.
        top_percent: Porcentagem do topo a remover (70 = manter 30% inferior).

    Returns:
        Bytes JPEG do overlay recortado e redimensionado.
    """
    frame = cv2.imread(str(frame_path))
    if frame is None:
        raise ValueError(f"Nao foi possivel ler frame: {frame_path}")

    h, w = frame.shape[:2]
    top_cut = int(h * top_percent / 100)
    overlay = frame[top_cut:, :]

    # Redimensionar pra 420p de largura mantendo proporcao
    oh, ow = overlay.shape[:2]
    new_w = OVERLAY_WIDTH
    new_h = int(oh * new_w / ow)
    overlay_resized = cv2.resize(overlay, (new_w, new_h), interpolation=cv2.INTER_AREA)

    _, buf = cv2.imencode(".jpg", overlay_resized, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return buf.tobytes()


def _chamar_gemini_com_retry(
    client: genai.Client,
    image_part: Part,
    max_retries: int = 3,
) -> object:
    """Chama Gemini com retry automatico em caso de rate limit."""
    import time

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
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                espera = 15 * (tentativa + 1)
                logger.info(
                    "Rate limit atingido, aguardando %ds (tentativa %d/%d)",
                    espera, tentativa + 1, max_retries,
                )
                time.sleep(espera)
            elif "ReadTimeout" in str(type(e).__name__) or "timed out" in str(e):
                espera = 10 * (tentativa + 1)
                logger.info(
                    "Timeout, aguardando %ds (tentativa %d/%d)",
                    espera, tentativa + 1, max_retries,
                )
                time.sleep(espera)
            else:
                raise
    raise RuntimeError("Gemini falhou apos todas as tentativas")


def extrair_dados_frame(frame_path: Path) -> dict[str, object] | None:
    """Recorta overlay do frame, envia ao Gemini e extrai dados estruturados.

    Envia apenas o overlay recortado em 420p (3x mais barato que frame completo).
    O frame completo e mantido no disco pra visualizacao no dashboard.

    Args:
        frame_path: Caminho do frame JPEG.

    Returns:
        Dict com dados extraidos ou None se falhar.
    """
    if not frame_path.exists():
        raise FileNotFoundError(f"Frame nao encontrado: {frame_path}")

    client = _get_client()

    try:
        overlay_bytes = _recortar_overlay(frame_path)
        image_part = Part.from_bytes(data=overlay_bytes, mime_type="image/jpeg")
        response = _chamar_gemini_com_retry(client, image_part)
    except Exception:
        logger.exception("Erro ao chamar Gemini para: %s", frame_path.name)
        return None

    if not response.text:
        logger.warning("Resposta vazia do Gemini para: %s", frame_path.name)
        return None

    texto = response.text.strip()
    # Remove markdown code blocks se Gemini retornar com ```json
    if texto.startswith("```"):
        texto = texto.split("\n", 1)[1] if "\n" in texto else texto
        if texto.endswith("```"):
            texto = texto[:-3]
        texto = texto.strip()

    try:
        dados = json.loads(texto)
    except json.JSONDecodeError:
        logger.warning(
            "Resposta invalida do Gemini para %s: %s", frame_path.name, texto[:200]
        )
        return None

    if "erro" in dados:
        logger.info("Frame nao e leilao: %s (%s)", frame_path.name, dados["erro"])
        return None

    logger.debug("Dados extraidos de %s: lote %s", frame_path.name, dados.get("lote_numero"))
    return dados
