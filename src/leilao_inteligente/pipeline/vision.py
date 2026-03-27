"""Extracao de dados de frames via Gemini Flash Vision."""

import json
import logging
from pathlib import Path

import google.generativeai as genai
from PIL import Image

from leilao_inteligente.config import get_settings


logger = logging.getLogger(__name__)

PROMPT_EXTRACAO = """Analise esta imagem de um leilão de gado brasileiro.

Extraia do overlay/legenda na tela:
- Número do lote
- Quantidade de animais
- Raça (ex: Nelore, Angus, Brahman)
- Sexo (macho, femea ou misto)
- Idade em meses (se disponível)
- Valor do lance atual em reais (apenas o número)
- Cidade
- Estado (sigla UF, 2 letras)

Observe também o gado na imagem:
- Cor predominante da pelagem (branco, vermelho, malhado, preto, etc)

Retorne APENAS um JSON válido neste formato exato, sem markdown:
{
    "lote_numero": 5,
    "quantidade": 35,
    "raca": "Nelore",
    "sexo": "macho",
    "idade_meses": 12,
    "pelagem": "branco",
    "preco_lance": 3290.00,
    "local_cidade": "Crixás",
    "local_estado": "GO",
    "confianca": 0.95
}

Regras:
- Se não conseguir ler um campo, use null
- confianca: 0.0 a 1.0 indicando sua certeza geral sobre os dados
- sexo deve ser "macho", "femea" ou "misto" (sem acento)
- preco_lance deve ser apenas o número, sem R$ ou pontos de milhar
- local_estado deve ser a sigla de 2 letras (SP, GO, MT, MS, etc)
- Se a imagem não for de um leilão de gado, retorne {"erro": "nao_e_leilao"}
"""


_model: genai.GenerativeModel | None = None


def _get_model() -> genai.GenerativeModel:
    """Inicializa e retorna o modelo Gemini (singleton)."""
    global _model
    if _model is None:
        settings = get_settings()
        genai.configure(api_key=settings.gemini_api_key)
        _model = genai.GenerativeModel("gemini-2.0-flash")
    return _model


def extrair_dados_frame(frame_path: Path) -> dict[str, object] | None:
    """Envia um frame ao Gemini e extrai dados estruturados.

    Args:
        frame_path: Caminho do frame JPEG.

    Returns:
        Dict com dados extraidos ou None se falhar.
    """
    if not frame_path.exists():
        raise FileNotFoundError(f"Frame nao encontrado: {frame_path}")

    model = _get_model()
    image = Image.open(frame_path)

    try:
        response = model.generate_content(
            [PROMPT_EXTRACAO, image],
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=500,
            ),
        )
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
