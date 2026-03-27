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
        resultado["lote_numero"] = str(lote).strip()

    # Normalizar preco
    preco = resultado.get("preco_lance")
    if isinstance(preco, str):
        preco_limpo = preco.replace("R$", "").replace(".", "").replace(",", ".").strip()
        try:
            resultado["preco_lance"] = Decimal(preco_limpo)
        except InvalidOperation:
            resultado["preco_lance"] = None

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
        resultado["raca"] = raca.strip().title()

    # Normalizar cidade
    cidade = resultado.get("local_cidade")
    if isinstance(cidade, str):
        resultado["local_cidade"] = cidade.strip().title()

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
        resultado["fazenda_vendedor"] = fazenda.strip().upper()
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
