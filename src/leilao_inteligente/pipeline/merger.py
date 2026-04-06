"""Merge e consolidação de resultados dos agentes Haiku."""

import json
import logging
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

logger = logging.getLogger(__name__)


def carregar_lotes(resultado_dir: Path) -> dict[str, str | None]:
    """Carrega resultados dos agentes de lote → mapa frame→lote_numero."""
    lote_map = {}
    for f in sorted(resultado_dir.glob("lote_resultado_*.json")):
        try:
            dados = json.loads(f.read_text())
            if isinstance(dados, list):
                for d in dados:
                    if isinstance(d, dict) and d.get("frame"):
                        lote_map[d["frame"]] = d.get("lote_numero")
        except (json.JSONDecodeError, OSError):
            logger.warning("Erro lendo %s", f)
    logger.info("Lotes carregados: %d frames", len(lote_map))
    return lote_map


def carregar_dados(resultado_dir: Path) -> list[dict]:
    """Carrega resultados dos agentes de dados."""
    dados_all = []
    for f in sorted(resultado_dir.glob("dados_resultado_*.json")):
        try:
            dados = json.loads(f.read_text())
            if isinstance(dados, list):
                dados_all.extend(dados)
        except (json.JSONDecodeError, OSError):
            logger.warning("Erro lendo %s", f)
    logger.info("Dados carregados: %d frames", len(dados_all))
    return dados_all


def merge(lote_map: dict[str, str | None], dados_all: list[dict]) -> list[dict]:
    """Merge lote + dados por frame path."""
    merged = []
    for item in dados_all:
        if not isinstance(item, dict):
            continue
        frame = item.get("frame", "")
        if item.get("erro"):
            continue
        lote = lote_map.get(frame)
        if not lote or lote == "0":
            continue
        item["lote_numero"] = lote
        # Extrair segundo do vídeo do nome do frame
        try:
            fname = Path(frame).stem
            num = int(fname.split("_")[1])
            item["segundo_video"] = (num - 1) * 5
        except (ValueError, IndexError):
            item["segundo_video"] = 0
        merged.append(item)
    logger.info("Merge: %d frames com lote e dados", len(merged))
    return merged


def _moda(lst: list):
    """Retorna valor mais frequente da lista."""
    if not lst:
        return None
    return Counter(lst).most_common(1)[0][0]


def consolidar(merged: list[dict]) -> list[dict]:
    """Consolida frames mergeados em lotes únicos.

    Returns:
        Lista de dicts prontos para inserção no banco.
    """
    por_lote = defaultdict(list)
    for d in merged:
        por_lote[str(d["lote_numero"])].append(d)

    lotes = []
    for num, frames in por_lote.items():
        precos = [
            d["preco_lance"] for d in frames
            if d.get("preco_lance") and isinstance(d["preco_lance"], (int, float)) and d["preco_lance"] > 0
        ]
        precos_positivos = [p for p in precos if p > 10]  # Ignorar valores < 10 (erros de OCR)

        qtds = [d["quantidade"] for d in frames if d.get("quantidade")]
        racas = [d["raca"] for d in frames if d.get("raca")]
        sexos = [d["sexo"] for d in frames if d.get("sexo")]
        idades = [d["idade_meses"] for d in frames if d.get("idade_meses")]
        fazendas = [d["fazenda_vendedor"] for d in frames if d.get("fazenda_vendedor")]
        vendido = any(d.get("vendido") for d in frames)
        segundos = [d["segundo_video"] for d in frames if d.get("segundo_video")]

        qty = _moda(qtds) or 1
        raca = _moda(racas) or "Nelore"
        sexo = _moda(sexos) or "macho"
        idade = _moda(idades)
        fazenda = _moda(fazendas)

        preco_inicial = min(precos_positivos) if precos_positivos else 0
        preco_final = max(precos_positivos) if precos_positivos else 0

        status = "arrematado" if vendido else (
            "arrematado" if preco_final > preco_inicial and len(precos_positivos) >= 3 else "incerto"
        )

        lotes.append({
            "lote_numero": num,
            "quantidade": qty,
            "raca": raca,
            "sexo": sexo,
            "idade_meses": idade,
            "preco_inicial": preco_inicial,
            "preco_final": preco_final,
            "preco_por_cabeca": preco_final / qty if qty > 0 and preco_final > 0 else None,
            "fazenda_vendedor": fazenda,
            "status": status,
            "vendido": vendido,
            "frames_analisados": len(frames),
            "segundo_video": min(segundos) if segundos else 0,
            "confianca_media": 0.9,
        })

    lotes.sort(key=lambda x: x["segundo_video"])
    logger.info("Consolidados %d lotes de %d frames", len(lotes), len(merged))
    return lotes


def processar_resultados(resultado_dir: Path) -> list[dict]:
    """Pipeline completo: carrega → merge → consolida."""
    lote_map = carregar_lotes(resultado_dir)
    dados_all = carregar_dados(resultado_dir)
    merged = merge(lote_map, dados_all)
    return consolidar(merged)
