"""Calibração e detecção de carimbo de arrematação por canal.

Cada canal de leilão tem um carimbo visual diferente (martelo, selo VENDIDO, etc).
Este módulo:
1. Calibra o padrão do carimbo no primeiro vídeo de um canal (posição, cores, formato)
2. Salva o perfil persistente no banco (tabela Configuracao)
3. Usa o perfil para filtrar candidatos localmente (custo zero) antes de enviar ao Gemini
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

CALIBRACAO_MIN_AMOSTRAS = 2   # mínimo de carimbos confirmados para criar perfil
CALIBRACAO_MAX_LOTES = 5      # lotes arrematados a testar na calibração
CALIBRACAO_THRESHOLD_DIFF = 0.10  # threshold baixo para calibração (pegar mais candidatos)
DETECCAO_DEFAULT_THRESHOLD = 0.25  # threshold padrão para detecção sem perfil


def _normalizar_canal(canal: str) -> str:
    return canal.strip().lower()


def obter_perfil(canal: str) -> dict | None:
    """Busca perfil de carimbo calibrado para o canal."""
    from leilao_inteligente.storage.db import get_session

    chave = f"carimbo_perfil:{_normalizar_canal(canal)}"
    session = get_session()
    try:
        from leilao_inteligente.models.database import Configuracao
        cfg = session.query(Configuracao).filter(Configuracao.chave == chave).first()
        if cfg and cfg.valor:
            return json.loads(cfg.valor)
    except Exception as e:
        logger.warning("Erro ao buscar perfil de carimbo: %s", e)
    finally:
        session.close()
    return None


def salvar_perfil(canal: str, perfil: dict) -> None:
    """Salva perfil de carimbo no banco."""
    from leilao_inteligente.storage.db import get_session
    from leilao_inteligente.models.database import Configuracao
    from sqlalchemy import text

    chave = f"carimbo_perfil:{_normalizar_canal(canal)}"
    session = get_session()
    try:
        existente = session.query(Configuracao).filter(Configuracao.chave == chave).first()
        valor = json.dumps(perfil, ensure_ascii=False)
        if existente:
            existente.valor = valor
            existente.atualizado_em = datetime.now(timezone.utc)
        else:
            session.add(Configuracao(chave=chave, valor=valor))
        session.commit()
        logger.info("Perfil de carimbo salvo para canal '%s'", canal)
    except Exception as e:
        logger.error("Erro ao salvar perfil: %s", e)
        session.rollback()
    finally:
        session.close()


def change_score_frame_inteiro(frame_a: np.ndarray, frame_b: np.ndarray) -> float:
    """Calcula % de mudança entre dois frames (frame inteiro, grayscale)."""
    ga = cv2.cvtColor(frame_a, cv2.COLOR_BGR2GRAY)
    gb = cv2.cvtColor(frame_b, cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(ga, gb)
    return float(np.sum(diff > 30) / diff.size)


def change_score_regiao(
    frame_a: np.ndarray,
    frame_b: np.ndarray,
    regiao: dict,
) -> float:
    """Calcula % de mudança apenas na região especificada (em % do frame)."""
    h, w = frame_a.shape[:2]
    y1 = int(h * regiao["y1_pct"])
    y2 = int(h * regiao["y2_pct"])
    x1 = int(w * regiao["x1_pct"])
    x2 = int(w * regiao["x2_pct"])

    ga = cv2.cvtColor(frame_a[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
    gb = cv2.cvtColor(frame_b[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(ga, gb)
    return float(np.sum(diff > 30) / diff.size)


def _extrair_bbox_carimbo(frame_com: np.ndarray, frame_sem: np.ndarray) -> dict | None:
    """Extrai bounding box do carimbo comparando frame com vs sem carimbo.

    Retorna região em % do frame: {"x1_pct", "y1_pct", "x2_pct", "y2_pct"}
    """
    ga = cv2.cvtColor(frame_sem, cv2.COLOR_BGR2GRAY)
    gb = cv2.cvtColor(frame_com, cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(ga, gb)

    # Binarizar e dilatar para conectar regiões próximas
    _, thresh = cv2.threshold(diff, 40, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    thresh = cv2.dilate(thresh, kernel, iterations=2)

    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    # Pegar o maior contorno (provável carimbo)
    maior = max(contours, key=cv2.contourArea)
    x, y, w_box, h_box = cv2.boundingRect(maior)

    h, w = frame_com.shape[:2]

    # Ignorar contornos muito pequenos (< 5% da área) ou muito grandes (> 80%)
    area_pct = (w_box * h_box) / (w * h)
    if area_pct < 0.05 or area_pct > 0.80:
        return None

    # Expandir bbox com margem de 10%
    margem_x = int(w_box * 0.10)
    margem_y = int(h_box * 0.10)
    x1 = max(0, x - margem_x)
    y1 = max(0, y - margem_y)
    x2 = min(w, x + w_box + margem_x)
    y2 = min(h, y + h_box + margem_y)

    return {
        "x1_pct": round(x1 / w, 3),
        "y1_pct": round(y1 / h, 3),
        "x2_pct": round(x2 / w, 3),
        "y2_pct": round(y2 / h, 3),
    }


def _extrair_cores_dominantes(frame_com: np.ndarray, frame_sem: np.ndarray, k: int = 3) -> list[list[int]]:
    """Extrai cores dominantes do carimbo via K-Means nos pixels que mudaram."""
    diff = cv2.absdiff(frame_sem, frame_com)
    gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    mask = gray_diff > 40

    pixels = frame_com[mask]
    if len(pixels) < 100:
        return []

    # Subsample para velocidade
    if len(pixels) > 5000:
        indices = np.random.choice(len(pixels), 5000, replace=False)
        pixels = pixels[indices]

    pixels = np.float32(pixels)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, _, centers = cv2.kmeans(pixels, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS)

    return [[int(c) for c in center] for center in centers]


def calibrar_carimbo(
    video_path: Path,
    canal: str,
    lotes_arrematados: list,
    lotes_com_frame: list,
    intervalo_original: int,
) -> dict:
    """Calibra o padrão de carimbo para um canal novo.

    Usa lotes arrematados (preço subiu) como ground truth — sabemos que
    DEVE haver carimbo no gap após eles.

    Returns:
        Perfil dict (já salvo no banco).
    """
    from leilao_inteligente.pipeline.vision import detectar_carimbo_calibracao
    from leilao_inteligente.pipeline.frame_extractor import extrair_frames_janela
    from leilao_inteligente.config import FRAMES_DIR

    video_name = video_path.stem
    calib_dir = FRAMES_DIR / video_name / "calibracao"
    calib_dir.mkdir(parents=True, exist_ok=True)

    # Selecionar lotes arrematados equidistantes
    arrematados = sorted(lotes_arrematados, key=lambda c: c.timestamp_inicio)
    step = max(1, len(arrematados) // CALIBRACAO_MAX_LOTES)
    amostra = arrematados[::step][:CALIBRACAO_MAX_LOTES]

    logger.info("Calibrando carimbo para canal '%s' com %d lotes", canal, len(amostra))

    # Mapear timestamps dos frames por lote
    por_lote: dict[str, list] = defaultdict(list)
    for lcf in lotes_com_frame:
        por_lote[lcf.lote.lote_numero].append(lcf)

    amostras_confirmadas: list[dict] = []

    for consolidado in amostra:
        # Calcular janela: usar segundo_video + duração do lote
        seg_inicio = consolidado.segundo_video
        if seg_inicio is None:
            continue

        # Duração do lote: diferença entre timestamps
        duracao = 0
        if consolidado.timestamp_fim and consolidado.timestamp_inicio:
            duracao = int((consolidado.timestamp_fim - consolidado.timestamp_inicio).total_seconds())

        # Janela: últimos 30s do lote + 60s depois (carimbo aparece perto do fim)
        ultimo_estimado = seg_inicio + max(duracao, 30)
        janela_inicio = max(seg_inicio, ultimo_estimado - 30)
        janela_fim = ultimo_estimado + 60

        # Extrair frames 1fps
        lote_dir = calib_dir / consolidado.lote_numero
        lote_dir.mkdir(exist_ok=True)
        frames = extrair_frames_janela(video_path, janela_inicio, janela_fim, lote_dir, intervalo_segundos=1)

        if len(frames) < 3:
            continue

        # Change detection frame inteiro — encontrar picos
        video_cap = cv2.VideoCapture(str(video_path))
        fps = video_cap.get(cv2.CAP_PROP_FPS)

        prev_frame = None
        picos: list[tuple[Path, Path, float]] = []  # (frame_com, frame_sem, score)

        for fp in frames:
            frame = cv2.imread(str(fp))
            if frame is None:
                continue
            if prev_frame is not None:
                score = change_score_frame_inteiro(prev_frame, frame)
                if score > CALIBRACAO_THRESHOLD_DIFF:
                    picos.append((fp, prev_fp, score))
            prev_frame = frame
            prev_fp = fp

        video_cap.release()

        encontrou_neste_lote = False

        if picos:
            # Pegar os 2 maiores picos (provável aparição e desaparição do carimbo)
            picos.sort(key=lambda x: x[2], reverse=True)

            for frame_com_path, frame_sem_path, score in picos[:2]:
                resultado = detectar_carimbo_calibracao(frame_sem_path, frame_com_path)
                if resultado is None:
                    continue

                frame_com = cv2.imread(str(frame_com_path))
                frame_sem = cv2.imread(str(frame_sem_path))
                if frame_com is None or frame_sem is None:
                    continue

                bbox = _extrair_bbox_carimbo(frame_com, frame_sem)
                cores = _extrair_cores_dominantes(frame_com, frame_sem)

                if bbox:
                    amostras_confirmadas.append({
                        "bbox": bbox,
                        "cores": cores,
                        "score": score,
                        "descricao": resultado,
                    })
                    logger.info(
                        "Carimbo encontrado lote %s (pré-filtro): bbox=%s, score=%.1f%%",
                        consolidado.lote_numero, bbox, score * 100,
                    )
                    encontrou_neste_lote = True
                    break

        # Fallback: se pré-filtro não achou, enviar frames direto ao Gemini
        # (cobre canais com fade-in gradual onde change detection não pega)
        if not encontrou_neste_lote:
            from leilao_inteligente.pipeline.vision import detectar_carimbo_arrematacao

            logger.info(
                "Lote %s: pré-filtro não achou picos, tentando Gemini direto (sampling 8s)...",
                consolidado.lote_numero,
            )
            for i, fp in enumerate(frames):
                if i % 8 != 0:  # cada 8s
                    continue
                if detectar_carimbo_arrematacao(fp):
                    # Achou! Usar frame anterior como referência para bbox/cores
                    idx = max(0, frames.index(fp) - 1)
                    frame_sem_path = frames[idx]
                    frame_com = cv2.imread(str(fp))
                    frame_sem = cv2.imread(str(frame_sem_path))
                    if frame_com is None or frame_sem is None:
                        continue

                    bbox = _extrair_bbox_carimbo(frame_com, frame_sem)
                    cores = _extrair_cores_dominantes(frame_com, frame_sem)

                    amostras_confirmadas.append({
                        "bbox": bbox or {"x1_pct": 0.1, "y1_pct": 0.2, "x2_pct": 0.9, "y2_pct": 0.8},
                        "cores": cores,
                        "score": 0.0,
                        "descricao": {"posicao": "detectado via gemini direto"},
                    })
                    logger.info(
                        "Carimbo encontrado lote %s (Gemini direto): bbox=%s",
                        consolidado.lote_numero, bbox,
                    )
                    break

    # Agregar resultados
    if len(amostras_confirmadas) < CALIBRACAO_MIN_AMOSTRAS:
        logger.info("Canal '%s': poucos carimbos encontrados (%d), salvando perfil vazio", canal, len(amostras_confirmadas))
        perfil = {
            "versao": 1,
            "confianca": 0,
            "amostras": len(amostras_confirmadas),
            "calibrado_em": datetime.now(timezone.utc).isoformat(),
            "video_calibracao": video_path.stem,
        }
        salvar_perfil(canal, perfil)
        return perfil

    # Calcular região média (mediana das bboxes)
    bboxes = [a["bbox"] for a in amostras_confirmadas]
    regiao = {
        "x1_pct": round(float(np.median([b["x1_pct"] for b in bboxes])), 3),
        "y1_pct": round(float(np.median([b["y1_pct"] for b in bboxes])), 3),
        "x2_pct": round(float(np.median([b["x2_pct"] for b in bboxes])), 3),
        "y2_pct": round(float(np.median([b["y2_pct"] for b in bboxes])), 3),
    }

    # Merge cores de todas as amostras
    todas_cores = []
    for a in amostras_confirmadas:
        todas_cores.extend(a["cores"])

    # Tipo do carimbo (descrição mais comum)
    descricoes = [a["descricao"] for a in amostras_confirmadas]
    tipo = descricoes[0] if descricoes else {}

    # Threshold calibrado: média dos scores × 0.7 (margem)
    scores = [a["score"] for a in amostras_confirmadas]
    threshold_calibrado = round(float(np.mean(scores)) * 0.7, 3)
    threshold_calibrado = max(threshold_calibrado, 0.10)  # mínimo 10%

    perfil = {
        "versao": 1,
        "regiao": regiao,
        "cores_dominantes": todas_cores[:6],  # top 6 cores
        "threshold_mudanca": threshold_calibrado,
        "tipo_carimbo": tipo,
        "confianca": round(len(amostras_confirmadas) / CALIBRACAO_MAX_LOTES, 2),
        "amostras": len(amostras_confirmadas),
        "calibrado_em": datetime.now(timezone.utc).isoformat(),
        "video_calibracao": video_path.stem,
    }

    salvar_perfil(canal, perfil)

    logger.info(
        "Perfil calibrado para '%s': regiao=%s, threshold=%.1f%%, confianca=%.0f%% (%d amostras)",
        canal, regiao, threshold_calibrado * 100, perfil["confianca"] * 100, len(amostras_confirmadas),
    )

    return perfil


def detectar_com_perfil(
    frame_atual: np.ndarray,
    frame_anterior: np.ndarray,
    perfil: dict,
) -> bool:
    """Detecta candidato a carimbo usando perfil calibrado (custo zero, local).

    Verifica mudança apenas na região calibrada do canal.
    """
    regiao = perfil.get("regiao")
    if not regiao:
        # Perfil sem região → fallback para frame inteiro
        return change_score_frame_inteiro(frame_anterior, frame_atual) > DETECCAO_DEFAULT_THRESHOLD

    threshold = perfil.get("threshold_mudanca", DETECCAO_DEFAULT_THRESHOLD)
    score = change_score_regiao(frame_anterior, frame_atual, regiao)
    return score > threshold
