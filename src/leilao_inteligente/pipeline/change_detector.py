"""Deteccao de mudanca no overlay entre frames consecutivos."""

import logging
from pathlib import Path

import cv2
import numpy as np


logger = logging.getLogger(__name__)


def detectar_mudanca(
    frame_anterior: np.ndarray,
    frame_atual: np.ndarray,
    top_percent: int = 70,
    threshold: float = 0.15,
    pixel_diff: int = 30,
) -> bool:
    """Detecta se houve mudanca significativa na regiao do overlay.

    Compara a regiao inferior do frame (onde fica o overlay com dados do lote)
    entre dois frames consecutivos.

    Args:
        frame_anterior: Frame anterior (BGR).
        frame_atual: Frame atual (BGR).
        top_percent: Porcentagem do topo a ignorar (70 = analisa os 30% inferiores).
        threshold: Limiar de mudanca (0.15 = 15% dos pixels mudaram).
        pixel_diff: Minimo de mudanca por pixel pra contar como "mudou" (default 30).
                    Overlays translucidos precisam de valor menor (10-15).

    Returns:
        True se houve mudanca significativa no overlay.
    """
    height = frame_atual.shape[0]
    top_cut = int(height * top_percent / 100)

    roi_anterior = frame_anterior[top_cut:, :]
    roi_atual = frame_atual[top_cut:, :]

    gray_anterior = cv2.cvtColor(roi_anterior, cv2.COLOR_BGR2GRAY)
    gray_atual = cv2.cvtColor(roi_atual, cv2.COLOR_BGR2GRAY)

    diff = cv2.absdiff(gray_anterior, gray_atual)
    pixels_mudaram = float(np.mean(diff > pixel_diff))

    return pixels_mudaram > threshold


def filtrar_frames_relevantes(
    frames: list[Path],
    top_percent: int = 70,
    threshold: float = 0.15,
    pixel_diff: int = 30,
) -> list[Path]:
    """Filtra frames mantendo apenas os que possuem mudanca no overlay.

    Sempre inclui o primeiro frame. Para os demais, compara com o frame
    anterior e mantem apenas se houve mudanca significativa.

    Args:
        frames: Lista de caminhos de frames ordenados.
        top_percent: Porcentagem do topo a ignorar.
        threshold: Limiar de mudanca.
        pixel_diff: Minimo de mudanca por pixel (30 padrao, 10-15 pra translucidos).

    Returns:
        Lista filtrada de frames relevantes.
    """
    if not frames:
        return []

    relevantes: list[Path] = [frames[0]]
    frame_anterior = cv2.imread(str(frames[0]))

    if frame_anterior is None:
        raise ValueError(f"Nao foi possivel ler frame: {frames[0]}")

    for frame_path in frames[1:]:
        frame_atual = cv2.imread(str(frame_path))
        if frame_atual is None:
            logger.warning("Frame ilegivel, pulando: %s", frame_path)
            continue

        if detectar_mudanca(frame_anterior, frame_atual, top_percent, threshold, pixel_diff):
            relevantes.append(frame_path)
            frame_anterior = frame_atual

    logger.info(
        "Frames relevantes: %d de %d (%.0f%% reducao, pixel_diff=%d)",
        len(relevantes),
        len(frames),
        (1 - len(relevantes) / len(frames)) * 100 if frames else 0,
        pixel_diff,
    )
    return relevantes
