"""Extracao de dados de frames via Gemini Flash Vision."""

import json
import logging
from pathlib import Path

from google import genai
from google.genai.types import GenerateContentConfig

from leilao_inteligente.config import get_settings


logger = logging.getLogger(__name__)

PROMPT_EXTRACAO = """Analise esta imagem de um leilão de gado brasileiro.

Extraia do overlay/legenda na tela:
- Número do lote (pode ser alfanumérico: 5, 001A, 55A, 00)
- Quantidade de animais
- Raça (ex: Nelore, Angus, Cruzado, Anelorado, Guzera, Senepol)
- Sexo (macho, femea ou misto)
- Idade em meses (se disponível)
- Valor do lance atual em reais (apenas o número, 0 se não visível)
- Cidade
- Estado (sigla UF, 2 letras)
- Nome da fazenda vendedora (texto que aparece acima da descrição do gado, ex: "3 BRAÇOS", "FAZ. JULIANA")
- Data e hora exata mostrada no overlay (formato: DD/MM/AAAA HH:MM:SS)

Observe também o gado na imagem:
- Cor predominante da pelagem (branco, vermelho, malhado, preto, etc)

Retorne APENAS um JSON válido neste formato exato, sem markdown:
{
    "lote_numero": "0005",
    "quantidade": 35,
    "raca": "Nelore",
    "sexo": "macho",
    "idade_meses": 12,
    "pelagem": "branco",
    "preco_lance": 3290.00,
    "local_cidade": "Crixás",
    "local_estado": "GO",
    "fazenda_vendedor": "FAZ. JULIANA",
    "timestamp_video": "26/03/2026 20:54:21",
    "confianca": 0.95
}

Regras:
- lote_numero deve ser string exatamente como aparece no overlay (ex: "00", "0005", "001A", "55A")
- Se não conseguir ler um campo, use null
- confianca: 0.0 a 1.0 indicando sua certeza geral sobre os dados
- sexo deve ser "macho", "femea" ou "misto" (sem acento)
- preco_lance deve ser apenas o número, sem R$ ou pontos de milhar. Se não visível, use 0
- local_estado deve ser a sigla de 2 letras (SP, GO, MT, MS, etc)
- fazenda_vendedor: nome da fazenda/recinto que aparece no overlay, sem "Recinto" na frente
- timestamp_video: data e hora exata como aparece no overlay
- Se a imagem não for de um leilão de gado, retorne {"erro": "nao_e_leilao"}
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


def _chamar_gemini_com_retry(
    client: genai.Client,
    image_part: object,
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
            else:
                raise
    raise RuntimeError("Rate limit excedido apos todas as tentativas")


def extrair_dados_frame(frame_path: Path) -> dict[str, object] | None:
    """Envia um frame ao Gemini e extrai dados estruturados.

    Args:
        frame_path: Caminho do frame JPEG.

    Returns:
        Dict com dados extraidos ou None se falhar.
    """
    if not frame_path.exists():
        raise FileNotFoundError(f"Frame nao encontrado: {frame_path}")

    client = _get_client()

    try:
        from google.genai.types import Part

        image_bytes = frame_path.read_bytes()
        image_part = Part.from_bytes(data=image_bytes, mime_type="image/jpeg")

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
