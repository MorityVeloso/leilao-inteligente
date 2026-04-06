"""Persistência de perfis de calibração por canal."""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _chave_canal(canal: str) -> str:
    return f"calibracao:{canal.strip().lower()}"


def obter_calibracao(canal: str) -> dict | None:
    """Busca calibração existente para o canal."""
    from leilao_inteligente.storage.db import get_session
    from leilao_inteligente.models.database import Configuracao

    session = get_session()
    try:
        cfg = session.query(Configuracao).filter(
            Configuracao.chave == _chave_canal(canal)
        ).first()
        if cfg and cfg.valor:
            return json.loads(cfg.valor)
    except Exception as e:
        logger.warning("Erro ao buscar calibração: %s", e)
    finally:
        session.close()
    return None


def salvar_calibracao(canal: str, calibracao: dict) -> None:
    """Salva calibração no banco."""
    from leilao_inteligente.storage.db import get_session
    from leilao_inteligente.models.database import Configuracao

    chave = _chave_canal(canal)
    calibracao["atualizado_em"] = datetime.utcnow().isoformat()
    valor = json.dumps(calibracao, ensure_ascii=False)

    session = get_session()
    try:
        existing = session.query(Configuracao).filter(Configuracao.chave == chave).first()
        if existing:
            existing.valor = valor
            existing.atualizado_em = datetime.utcnow()
        else:
            session.add(Configuracao(chave=chave, valor=valor, atualizado_em=datetime.utcnow()))
        session.commit()
        logger.info("Calibração salva para canal '%s'", canal)
    finally:
        session.close()


def obter_recortes(canal: str) -> dict | None:
    """Retorna coordenadas de recorte da calibração do canal."""
    cal = obter_calibracao(canal)
    if cal:
        return cal.get("recortes")
    return None


def montar_prompt_lote(calibracao: dict) -> str:
    """Prompt para agente Haiku que lê o número do lote."""
    return calibracao.get("prompt_lote",
        'Logo "Rural" + número GRANDE = NÚMERO DO LOTE. Ignore "LOTE". '
        'Sem logo: {"frame":"path","lote_numero":null}. '
        'Com: {"frame":"path","lote_numero":"XX"}'
    )


def montar_prompt_dados(calibracao: dict) -> str:
    """Prompt para agente Haiku que lê dados (qty, raça, preço, fazenda)."""
    return calibracao.get("prompt_dados",
        'QUANTIDADE (número antes da raça), RAÇA, '
        'SEXO (GARROTE/BEZERRO/BOI=macho, BEZERRA/VACA/NOVILHA=femea), '
        'IDADE (à direita, ex: "9 M"=9), PREÇO (após R$), '
        'FAZENDA (segunda linha). '
        'VENDIDO visível no full_crop? true/false.'
    )


def montar_prompt_gemini(calibracao: dict) -> str:
    """Monta o prompt do Gemini a partir da calibração.

    The prompt has 3 parts:
    1. General instructions (fixed)
    2. Layout mapping (channel-specific from calibration)
    3. JSON response format (fixed)
    """
    layout = calibracao.get("layout", "")
    ignorar = calibracao.get("ignorar", "")
    carimbo = calibracao.get("carimbo", "")

    carimbo_instrucao = ""
    if carimbo and carimbo != "sem_carimbo":
        carimbo_instrucao = f"""
Se houver selo/carimbo de arrematação visível ({carimbo}), adicione ao JSON:
"carimbo_vendido": true
"""

    prompt = f"""Analise este frame de um leilão de gado brasileiro transmitido ao vivo.

A imagem mostra o topo e a base do vídeo concatenados (o meio com o gado foi removido).
O overlay do leilão contém textos sobrepostos com dados do lote sendo leiloado.

Se NÃO houver overlay de lote (pista vazia, intervalo, propaganda, telefones, tela de espera):
{{"erro": "nao_e_leilao"}}

LAYOUT ESPECÍFICO DESTE CANAL:
{layout}

{f"IGNORE (NÃO são dados do lote): {ignorar}" if ignorar else ""}
{carimbo_instrucao}
Se houver overlay com dados do lote, retorne APENAS este JSON sem markdown:
{{
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
}}

Regras:
- lote_numero: número/código do lote. Geralmente em destaque, isolado, perto da palavra "LOTE"
- quantidade: número de animais. SEMPRE aparece ANTES de "MACHO(S)", "VACA(S)", "FEMEA(S)", "NOVILHA(S)"
- raca: Nelore, Anelorado, Mestiço, Guzera, Senepol, Tabapua, Angus (apenas raça, sem condição)
- sexo: "macho", "femea" ou "misto"
- condicao: só fêmeas — "parida", "prenhe", "solteira", "desmamada". null se macho
- idade_meses: converter "16 MS"=16, "2 ANOS"=24, "36 M"=36. null se não visível
- preco_lance: valor em R$ por animal. Se "R$ ,00" ou "R$ .00" sem valor, retorne 0. Número sem R$ (ex: 2680.00)
- local_cidade: cidade do leilão (topo do frame, logos, banners)
- local_estado: sigla UF (2 letras)
- fazenda_vendedor: nome do vendedor/fazenda ("VENDEDOR:", "FAZ.", "FAZENDA")
- timestamp_video: hora do overlay (HH:MM:SS). null se não visível
- confianca: 0.0 a 1.0
- Campo não legível: null (não invente)
"""
    return prompt
