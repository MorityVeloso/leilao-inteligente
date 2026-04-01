"""Validacao e limpeza de dados extraidos."""

import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError

from leilao_inteligente.models.schemas import LoteExtraido


logger = logging.getLogger(__name__)

# Estados validos do Brasil
UFS_VALIDAS = {
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO",
    "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR",
    "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
}


def normalizar_dados(dados: dict[str, object]) -> dict[str, object]:
    """Normaliza dados brutos antes da validacao Pydantic."""
    resultado = dict(dados)

    # Normalizar lote_numero para string
    lote = resultado.get("lote_numero")
    if lote is not None:
        lote_str = str(lote).strip()
        # Corrigir leituras como ".0", "0.0" → "0"
        if lote_str.replace(".", "").replace("0", "") == "":
            lote_str = "0"
        # Remover ponto decimal de numeros (ex: "5.0" → "5")
        elif "." in lote_str:
            try:
                lote_str = str(int(float(lote_str)))
            except ValueError:
                pass
        resultado["lote_numero"] = lote_str

    # Normalizar preco
    preco = resultado.get("preco_lance")
    if isinstance(preco, str):
        preco_limpo = preco.replace("R$", "").replace(".", "").replace(",", ".").strip()
        try:
            resultado["preco_lance"] = Decimal(preco_limpo)
        except InvalidOperation:
            resultado["preco_lance"] = None

    # Corrigir precos visivelmente truncados pelo OCR
    # Ex: overlay mostra "2.700" mas Gemini le "27" ou "270"
    # Regra: se preco < 500, tentar ×10 e ×100. Usar o que cair na faixa 500-15000.
    preco_val = resultado.get("preco_lance")
    if isinstance(preco_val, (int, float, Decimal)) and 0 < float(preco_val) < 500:
        p = float(preco_val)
        corrigido = None
        if 500 <= p * 100 <= 15000:
            corrigido = Decimal(str(preco_val)) * 100
        elif 500 <= p * 10 <= 15000:
            corrigido = Decimal(str(preco_val)) * 10
        if corrigido:
            logger.debug("Preço corrigido: %s → %s (truncado pelo OCR)", preco_val, corrigido)
            resultado["preco_lance"] = corrigido
        else:
            # Preco irreparavel (ex: R$50 → nenhuma multiplicacao faz sentido)
            logger.debug("Preço descartado: %s (irreparável)", preco_val)
            resultado["preco_lance"] = Decimal("0")

    # Normalizar sexo
    sexo = resultado.get("sexo")
    if isinstance(sexo, str):
        sexo_lower = sexo.lower().strip()
        mapa_sexo = {
            "macho": "macho",
            "machos": "macho",
            "fêmea": "femea",
            "femea": "femea",
            "fêmeas": "femea",
            "femeas": "femea",
            "misto": "misto",
            "mistos": "misto",
        }
        resultado["sexo"] = mapa_sexo.get(sexo_lower, sexo_lower)

    # Normalizar estado
    estado = resultado.get("local_estado")
    if isinstance(estado, str):
        resultado["local_estado"] = estado.upper().strip()

    # Normalizar raca
    raca = resultado.get("raca")
    if isinstance(raca, str):
        raca = raca.strip().title()
        # Mestiço, Mestico, Cruzado, Cruzada, etc → Mestiço
        racas_mesticas = {"Mestico", "Mestiço", "Mestiça", "Cruzado", "Cruzada", "Cruzados", "Cruzadas", "Meio Sangue"}
        resultado["raca"] = "Mestiço" if raca in racas_mesticas else raca

    # Normalizar cidade
    cidade = resultado.get("local_cidade")
    if isinstance(cidade, str):
        resultado["local_cidade"] = cidade.strip().title()

    # Normalizar condicao reprodutiva
    condicao = resultado.get("condicao")
    if isinstance(condicao, str):
        condicao_lower = condicao.lower().strip()
        mapa_condicao = {
            "parida": "parida",
            "paridas": "parida",
            "com cria": "parida",
            "com cria ao pe": "parida",
            "prenhe": "prenhe",
            "prenhes": "prenhe",
            "prenha": "prenhe",
            "gestante": "prenhe",
            "solteira": "solteira",
            "solteiras": "solteira",
            "vazia": "solteira",
            "desmamada": "desmamada",
            "desmamadas": "desmamada",
            "desmamado": "desmamada",
        }
        resultado["condicao"] = mapa_condicao.get(condicao_lower, condicao_lower)
    elif condicao is None:
        resultado["condicao"] = None

    # Condicao reprodutiva so se aplica a femeas
    sexo = resultado.get("sexo")
    if isinstance(sexo, str) and sexo.lower().strip() in ("macho", "machos"):
        resultado["condicao"] = None

    # Normalizar pelagem
    pelagem = resultado.get("pelagem")
    if isinstance(pelagem, str):
        resultado["pelagem"] = pelagem.strip().lower()

    # Normalizar fazenda
    fazenda = resultado.get("fazenda_vendedor")
    if isinstance(fazenda, str):
        fazenda = fazenda.strip()
        if fazenda.upper().startswith("RECINTO "):
            fazenda = fazenda[8:]
        fazenda = fazenda.strip().upper()

        # Correcoes de OCR conhecidas
        correcoes_fazenda: dict[str, str] = {
            "TUOLO": "TIJOLO",
            "TUÓLO": "TIJOLO",
            "TIJÓLO": "TIJOLO",
            "BAN": "BRN",
        }
        resultado["fazenda_vendedor"] = correcoes_fazenda.get(fazenda, fazenda)
    elif fazenda is None:
        resultado["fazenda_vendedor"] = None

    # Normalizar timestamp_video
    ts_video = resultado.get("timestamp_video")
    if isinstance(ts_video, str):
        ts_video = ts_video.strip()
        for fmt in ["%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S"]:
            try:
                resultado["timestamp_video"] = datetime.strptime(ts_video, fmt)
                break
            except ValueError:
                continue
        else:
            resultado["timestamp_video"] = None

    return resultado


def validar_lote(
    dados: dict[str, object],
    timestamp_frame: datetime | None = None,
) -> LoteExtraido | None:
    """Valida dados extraidos e retorna LoteExtraido ou None."""
    normalizados = normalizar_dados(dados)

    # Adicionar timestamp se nao presente
    if "timestamp_frame" not in normalizados and timestamp_frame:
        normalizados["timestamp_frame"] = timestamp_frame
    elif "timestamp_frame" not in normalizados:
        normalizados["timestamp_frame"] = datetime.now(tz=timezone.utc)

    # Descartar lote numero "0" (lixo de OCR)
    lote_num = normalizados.get("lote_numero")
    if isinstance(lote_num, str) and lote_num.strip("0") == "":
        logger.debug("Lote numero '%s' descartado (OCR lixo)", lote_num)
        return None

    # Verificar UF
    estado = normalizados.get("local_estado")
    if isinstance(estado, str) and estado not in UFS_VALIDAS:
        logger.warning("UF invalida: %s", estado)
        return None

    try:
        return LoteExtraido(**normalizados)
    except ValidationError as e:
        logger.warning("Dados invalidos: %s", e.errors())
        return None
