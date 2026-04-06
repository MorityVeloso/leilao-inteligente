"""Recorte de frames para processamento por agentes Haiku."""

import json
import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Calibração padrão (Lance Transmissão)
DEFAULT_CALIBRATION = {
    "lote": {"x_pct": 0, "y_pct": 75, "w_pct": 17, "h_pct": 25, "upscale": 3},
    "dados": {"x_pct": 15, "y_pct": 75, "w_pct": 85, "h_pct": 25},
    "full": {"width": 320, "quality": 70},
}


def recortar_frame(
    frame_path: Path,
    output_dir: Path,
    calibration: dict | None = None,
) -> dict | None:
    """Cria 3 recortes de um frame para processamento Haiku.

    Returns:
        Dict with paths: {"frame": str, "lote_crop": str, "dados_crop": str, "full_crop": str}
        None if frame can't be read.
    """
    cal = calibration or DEFAULT_CALIBRATION
    frame = cv2.imread(str(frame_path))
    if frame is None:
        return None

    h, w = frame.shape[:2]
    fname = frame_path.stem

    # 1. Lote crop (17% + upscale 3x)
    lc = cal.get("lote", DEFAULT_CALIBRATION["lote"])
    x1 = int(w * lc["x_pct"] / 100)
    y1 = int(h * lc["y_pct"] / 100)
    x2 = x1 + int(w * lc["w_pct"] / 100)
    y2 = y1 + int(h * lc["h_pct"] / 100)
    crop_lote = frame[y1:y2, x1:x2]
    upscale = lc.get("upscale", 3)
    if upscale > 1:
        crop_lote = cv2.resize(
            crop_lote,
            (crop_lote.shape[1] * upscale, crop_lote.shape[0] * upscale),
            interpolation=cv2.INTER_CUBIC,
        )
    lote_path = str(output_dir / f"{fname}_lote.jpg")
    cv2.imwrite(lote_path, crop_lote)

    # 2. Dados crop
    dc = cal.get("dados", DEFAULT_CALIBRATION["dados"])
    dx1 = int(w * dc["x_pct"] / 100)
    dy1 = int(h * dc["y_pct"] / 100)
    dx2 = dx1 + int(w * dc["w_pct"] / 100)
    dy2 = dy1 + int(h * dc["h_pct"] / 100)
    crop_dados = frame[dy1:dy2, dx1:dx2]
    dados_path = str(output_dir / f"{fname}_dados.jpg")
    cv2.imwrite(dados_path, crop_dados)

    # 3. Full frame reduced
    fc = cal.get("full", DEFAULT_CALIBRATION["full"])
    target_w = fc.get("width", 320)
    scale = target_w / w
    mini = cv2.resize(frame, (target_w, int(h * scale)))
    full_path = str(output_dir / f"{fname}_full.jpg")
    quality = fc.get("quality", 70)
    cv2.imwrite(full_path, mini, [cv2.IMWRITE_JPEG_QUALITY, quality])

    return {
        "frame": str(frame_path),
        "lote_crop": lote_path,
        "dados_crop": dados_path,
        "full_crop": full_path,
    }


def recortar_todos(
    frames: list[Path],
    output_dir: Path,
    calibration: dict | None = None,
    batch_size: int = 20,
) -> tuple[list[Path], list[Path]]:
    """Recorta todos os frames e cria batches JSON para agentes Haiku.

    Returns:
        (lote_batches, dados_batches) — lists of paths to batch JSON files.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    lote_items = []
    dados_items = []

    for fp in frames:
        result = recortar_frame(fp, output_dir, calibration)
        if result is None:
            continue
        lote_items.append({"frame": result["frame"], "lote_crop": result["lote_crop"]})
        dados_items.append({
            "frame": result["frame"],
            "dados_crop": result["dados_crop"],
            "full_crop": result["full_crop"],
        })

    logger.info("Recortados %d frames em %s", len(lote_items), output_dir)

    # Criar batches de 20
    lote_batches = []
    dados_batches = []

    for i in range(0, len(lote_items), batch_size):
        batch_num = i // batch_size

        lb = output_dir / f"lote_batch_{batch_num:03d}.json"
        lb.write_text(json.dumps(lote_items[i:i + batch_size], ensure_ascii=False))
        lote_batches.append(lb)

        db = output_dir / f"dados_batch_{batch_num:03d}.json"
        db.write_text(json.dumps(dados_items[i:i + batch_size], ensure_ascii=False))
        dados_batches.append(db)

    logger.info("Criados %d batches de lote + %d de dados", len(lote_batches), len(dados_batches))
    return lote_batches, dados_batches
