"""Extração de frames amostrais direto do stream do YouTube."""

import logging
import subprocess
from pathlib import Path

import cv2
import numpy as np
import yt_dlp

from leilao_inteligente.config import FRAMES_DIR

logger = logging.getLogger(__name__)


def _obter_stream_url(url: str, max_height: int = 360) -> tuple[str, dict]:
    """Obtém URL do stream e metadados sem baixar o vídeo."""
    ydl = yt_dlp.YoutubeDL({"quiet": True})
    info = ydl.extract_info(url, download=False)

    stream_url = None
    for f in info.get("formats", []):
        if (f.get("height") and f["height"] <= max_height
            and f.get("vcodec", "none") != "none"
            and f.get("ext") == "mp4"):
            stream_url = f["url"]

    if not stream_url:
        for f in info.get("formats", []):
            if f.get("height") and f["height"] <= max_height and f.get("vcodec", "none") != "none":
                stream_url = f["url"]
                break

    if not stream_url:
        raise ValueError(f"Nenhum stream de vídeo encontrado para {url}")

    return stream_url, info


def _extrair_frame_de_stream(stream_url: str, segundo: int, output_path: Path, timeout: int = 30) -> bool:
    """Extrai um único frame do stream via ffmpeg."""
    cmd = [
        "ffmpeg", "-ss", str(segundo),
        "-i", stream_url,
        "-frames:v", "1", "-q:v", "2",
        "-y", str(output_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.returncode == 0 and output_path.exists()


def _calcular_timestamps_amostrais(duracao_s: int, n_espacados: int = 10) -> list[int]:
    """Calcula timestamps espaçados uniformemente, pulando início e fim."""
    inicio = min(600, duracao_s // 10)
    fim = duracao_s - 300
    if fim <= inicio:
        fim = duracao_s
        inicio = 0
    intervalo = (fim - inicio) // (n_espacados + 1)
    return [inicio + intervalo * (i + 1) for i in range(n_espacados)]


def _detectar_transicoes(frames: list[Path], n_transicoes: int = 10) -> list[int]:
    """Detecta frames com maior change score (transições de lote)."""
    scores = []
    for i in range(1, len(frames)):
        prev = cv2.imread(str(frames[i - 1]))
        curr = cv2.imread(str(frames[i]))
        if prev is None or curr is None:
            scores.append(0.0)
            continue
        h = curr.shape[0]
        roi_prev = cv2.cvtColor(prev[int(h * 0.7):], cv2.COLOR_BGR2GRAY)
        roi_curr = cv2.cvtColor(curr[int(h * 0.7):], cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(roi_prev, roi_curr)
        score = float(np.mean(diff > 30))
        scores.append(score)
    indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return indices[:n_transicoes]


def extrair_frames_amostrais(url: str, n_espacados: int = 10, n_transicoes: int = 10) -> tuple[list[Path], dict]:
    """Extrai frames amostrais de um vídeo do YouTube sem baixar.

    Returns: (lista_de_paths, info_dict)
    """
    stream_url, info = _obter_stream_url(url)
    duracao = info.get("duration", 0)
    video_id = info.get("id", "unknown")
    canal = info.get("channel", "")

    output_dir = FRAMES_DIR / f"{video_id}_amostra"
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Amostrando %s (%ds = %.1fh) canal=%s", video_id, duracao, duracao / 3600, canal)

    timestamps = _calcular_timestamps_amostrais(duracao, n_espacados)
    frames_espacados = []

    for ts in timestamps:
        out = output_dir / f"amostra_{ts:06d}.jpg"
        if out.exists() or _extrair_frame_de_stream(stream_url, ts, out):
            frames_espacados.append(out)
        else:
            logger.warning("Falha ao extrair frame em %ds", ts)

    logger.info("Extraídos %d/%d frames espaçados", len(frames_espacados), len(timestamps))

    frames_transicao = []
    if len(frames_espacados) >= 3:
        transicao_indices = _detectar_transicoes(frames_espacados, n_transicoes)
        for idx in transicao_indices:
            if idx >= len(timestamps):
                continue
            ts = timestamps[idx]
            for delta in [-5, 5]:
                ts_adj = max(0, ts + delta)
                out = output_dir / f"transicao_{ts_adj:06d}.jpg"
                if out.exists() or _extrair_frame_de_stream(stream_url, ts_adj, out):
                    frames_transicao.append(out)

    logger.info("Extraídos %d frames de transição", len(frames_transicao))

    todos = sorted(set(frames_espacados + frames_transicao))
    return todos, info
