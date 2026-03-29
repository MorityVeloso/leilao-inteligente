"""Testes para o endpoint /api/frame — path traversal, 404, e frame valido."""

from unittest.mock import patch
from pathlib import Path

from fastapi.testclient import TestClient

from leilao_inteligente.api import app

client = TestClient(app)


def test_rejeita_path_traversal():
    """Path traversal com ..%2F deve retornar 403."""
    resp = client.get("/api/frame/..%2F..%2F.env")
    assert resp.status_code == 403


def test_frame_nao_encontrado():
    """Frame inexistente deve retornar 404."""
    resp = client.get("/api/frame/nao_existe.jpg")
    assert resp.status_code == 404


def test_frame_valido(tmp_path: Path):
    """Frame existente em DATA_DIR deve retornar 200."""
    frame = tmp_path / "test_frame.jpg"
    frame.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg")

    with patch("leilao_inteligente.api.DATA_DIR", tmp_path):
        resp = client.get("/api/frame/test_frame.jpg")

    assert resp.status_code == 200
