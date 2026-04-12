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


def calibrar_captura(frames: list) -> dict:
    """Auto-calibra parâmetros de captura analisando frames amostrais.

    Analisa pares de frames consecutivos para determinar:
    - threshold ideal de change detection
    - região do overlay (onde fica a barra de dados)
    - sensibilidade de pixel

    Args:
        frames: Lista de paths de frames (mínimo 10, idealmente 30+).

    Returns:
        dict com: threshold, overlay_top_percent, pixel_diff, stats
    """
    import cv2
    import numpy as np

    if len(frames) < 5:
        return {"threshold": 0.01, "overlay_top_percent": 62, "pixel_diff": 30}

    # Calcular change scores para cada região vertical
    # Testar: bottom 15%, 20%, 25%, 30%, 38%, 50%
    regioes = [85, 80, 75, 70, 62, 50]  # overlay_top_percent
    scores_por_regiao: dict[int, list[float]] = {r: [] for r in regioes}

    frames_paths = [str(f) for f in frames]
    prev_img = cv2.imread(frames_paths[0])

    for fp in frames_paths[1:]:
        img = cv2.imread(fp)
        if img is None or prev_img is None:
            prev_img = img
            continue
        if img.shape != prev_img.shape:
            prev_img = img
            continue

        h = img.shape[0]
        for regiao in regioes:
            top = int(h * regiao / 100)
            roi_prev = cv2.cvtColor(prev_img[top:, :], cv2.COLOR_BGR2GRAY)
            roi_curr = cv2.cvtColor(img[top:, :], cv2.COLOR_BGR2GRAY)
            diff = np.abs(roi_curr.astype(float) - roi_prev.astype(float))
            pct = float(np.sum(diff > 30) / diff.size)
            scores_por_regiao[regiao].append(pct)

        prev_img = img

    # Encontrar a melhor região: aquela onde os scores têm maior VARIÂNCIA
    # (= onde a diferença entre "lote mudou" e "mesmo lote" é mais clara)
    melhor_regiao = 62
    melhor_separacao = 0.0

    for regiao, scores in scores_por_regiao.items():
        if not scores:
            continue
        arr = np.array(scores)
        # Separação = diferença entre percentil 90 e mediana
        # Quanto maior, mais fácil distinguir "mudou" de "não mudou"
        p90 = float(np.percentile(arr, 90))
        mediana = float(np.median(arr))
        separacao = p90 - mediana

        if separacao > melhor_separacao:
            melhor_separacao = separacao
            melhor_regiao = regiao

    # Calcular threshold ideal para a melhor região
    scores = np.array(scores_por_regiao[melhor_regiao])
    mediana = float(np.median(scores))
    p75 = float(np.percentile(scores, 75))
    p90 = float(np.percentile(scores, 90))

    # Threshold = entre mediana e p75 (captura mudanças significativas, ignora ruído)
    # Mas não menor que 0.001 (0.1%)
    threshold = max(0.001, (mediana + p75) / 2)

    # Verificar quantos frames passariam com esse threshold
    passam = int(np.sum(scores > threshold))
    taxa = passam / len(scores) * 100

    # Se menos de 15% passa, threshold muito alto — baixar
    if taxa < 15:
        threshold = max(0.001, mediana * 1.5)
        passam = int(np.sum(scores > threshold))
        taxa = passam / len(scores) * 100

    # Se mais de 80% passa, threshold muito baixo — subir
    if taxa > 80:
        threshold = p75
        passam = int(np.sum(scores > threshold))
        taxa = passam / len(scores) * 100

    resultado = {
        "threshold": round(threshold, 4),
        "overlay_top_percent": melhor_regiao,
        "pixel_diff": 30,
        "stats": {
            "frames_analisados": len(scores),
            "mediana_score": round(mediana, 4),
            "p75_score": round(p75, 4),
            "p90_score": round(p90, 4),
            "taxa_passagem": round(taxa, 1),
            "melhor_separacao": round(melhor_separacao, 4),
        },
    }

    logger.info(
        "Auto-calibração captura: região=%d%%, threshold=%.4f, taxa=%.1f%% (%d/%d frames)",
        melhor_regiao, threshold, taxa, passam, len(scores),
    )

    return resultado


def obter_captura(canal: str) -> dict | None:
    """Retorna parâmetros de captura da calibração do canal."""
    cal = obter_calibracao(canal)
    if cal:
        return cal.get("captura")
    return None


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

    Seções do prompt (channel-specific):
    1. layout — posição e formato de cada campo no overlay
    2. ignorar — elementos visuais que NÃO são dados do lote
    3. carimbo — indicador visual de venda (selo, martelo, overlay)
    4. comportamento_preco — como o preço funciona neste canal
    5. dinamica_leilao — como identificar arrematado/sem disputa/repescagem
    6. transicoes — como é a troca entre lotes
    """
    layout = calibracao.get("layout", "")
    ignorar = calibracao.get("ignorar", "")
    carimbo = calibracao.get("carimbo", "")
    comportamento_preco = calibracao.get("comportamento_preco", "")
    dinamica_leilao = calibracao.get("dinamica_leilao", "")
    transicoes = calibracao.get("transicoes", "")

    # Carimbo
    carimbo_instrucao = ""
    if carimbo and carimbo != "sem_carimbo":
        carimbo_instrucao = f"""
INDICADOR DE VENDA (CARIMBO):
{carimbo}
Se este indicador estiver visível, retorne "carimbo_vendido": true.
"""
    else:
        carimbo_instrucao = """
Este canal NÃO usa carimbo/selo visual de venda. Retorne "carimbo_vendido": false sempre.
"""

    # Comportamento de preço
    preco_instrucao = ""
    if comportamento_preco:
        preco_instrucao = f"""
COMPORTAMENTO DE PREÇO NESTE CANAL:
{comportamento_preco}
"""

    # Dinâmica do leilão
    dinamica_instrucao = ""
    if dinamica_leilao:
        dinamica_instrucao = f"""
DINÂMICA DO LEILÃO:
{dinamica_leilao}
"""

    # Transições
    transicoes_instrucao = ""
    if transicoes:
        transicoes_instrucao = f"""
TRANSIÇÕES ENTRE LOTES:
{transicoes}
"""

    # Detectar se fazenda não aparece neste canal (busca na linha específica de fazenda)
    sem_fazenda = False
    for line in layout.split("\n"):
        if "fazenda" in line.lower() and "não aparece" in line.lower():
            sem_fazenda = True
            break
    fazenda_regra = ""
    if sem_fazenda:
        fazenda_regra = "- fazenda_vendedor: este canal NÃO mostra fazenda no overlay. Retorne SEMPRE null. Nomes na linha de LANCES são LEILOEIROS, NÃO fazendas"

    prompt = f"""Analise este frame de um leilão de gado brasileiro transmitido ao vivo.

A imagem mostra o frame inteiro do vídeo. O overlay do leilão contém textos sobrepostos com dados do lote sendo leiloado.

Se NÃO houver overlay de lote (pista vazia, intervalo, propaganda, telefones, tela de espera):
{{"erro": "nao_e_leilao"}}

LAYOUT ESPECÍFICO DESTE CANAL:
{layout}

{f"IGNORE (NÃO são dados do lote): {ignorar}" if ignorar else ""}
{carimbo_instrucao}
{preco_instrucao}
{dinamica_instrucao}
{transicoes_instrucao}
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
    "confianca": 0.95,
    "carimbo_vendido": false
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
{fazenda_regra}
- timestamp_video: hora do overlay (HH:MM:SS). null se não visível
- confianca: 0.0 a 1.0
- carimbo_vendido: true se houver indicador visual de venda. false se não houver
- Campo não legível: null (não invente)
"""
    return prompt
