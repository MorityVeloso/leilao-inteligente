"""Testes para o detector de mudanca de overlay."""

import numpy as np

from leilao_inteligente.pipeline.change_detector import detectar_mudanca


class TestDetectarMudanca:
    def test_frames_identicos_sem_mudanca(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        assert detectar_mudanca(frame, frame) is False

    def test_frames_totalmente_diferentes(self):
        frame_a = np.zeros((480, 640, 3), dtype=np.uint8)
        frame_b = np.ones((480, 640, 3), dtype=np.uint8) * 255
        assert detectar_mudanca(frame_a, frame_b) is True

    def test_mudanca_apenas_no_topo_ignorada(self):
        """Mudanca fora da regiao de overlay (topo) deve ser ignorada."""
        frame_a = np.zeros((480, 640, 3), dtype=np.uint8)
        frame_b = frame_a.copy()
        # Mudar apenas os 50% superiores (acima do overlay)
        frame_b[:240, :] = 255
        # Com top_percent=70, analisa apenas os 30% inferiores (336-480)
        assert detectar_mudanca(frame_a, frame_b, top_percent=70) is False

    def test_mudanca_no_overlay_detectada(self):
        """Mudanca na regiao de overlay (inferior) deve ser detectada."""
        frame_a = np.zeros((480, 640, 3), dtype=np.uint8)
        frame_b = frame_a.copy()
        # Mudar os 30% inferiores (regiao de overlay)
        frame_b[336:, :] = 255
        assert detectar_mudanca(frame_a, frame_b, top_percent=70) is True

    def test_mudanca_pequena_abaixo_threshold(self):
        """Mudanca pequena (poucos pixels) deve ser ignorada."""
        frame_a = np.zeros((480, 640, 3), dtype=np.uint8)
        frame_b = frame_a.copy()
        # Mudar apenas 5% dos pixels na regiao de overlay
        frame_b[470:480, :32] = 255
        assert detectar_mudanca(frame_a, frame_b, top_percent=70, threshold=0.15) is False

    def test_threshold_customizado(self):
        """Threshold alto rejeita mudancas moderadas, baixo aceita."""
        frame_a = np.zeros((480, 640, 3), dtype=np.uint8)
        frame_b = frame_a.copy()
        # Mudanca moderada no overlay (~35% da regiao)
        frame_b[400:480, :320] = 255
        # Com threshold alto (50%), nao detecta
        assert detectar_mudanca(frame_a, frame_b, top_percent=70, threshold=0.5) is False
        # Com threshold baixo (1%), detecta
        assert detectar_mudanca(frame_a, frame_b, top_percent=70, threshold=0.01) is True
