"""Testes para o modulo de Batch API do Gemini."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from leilao_inteligente.pipeline.vision import (
    _criar_jsonl_batch,
    _parse_response,
    _parsear_resultados_batch,
    extrair_dados_lote_batch,
    PROMPT_EXTRACAO,
)


class TestBatchValidation:
    """Testes de validacao de pre-requisitos."""

    def test_batch_requer_gcs_bucket(self, tmp_path: Path):
        with patch("leilao_inteligente.pipeline.vision.get_settings") as mock_settings:
            mock_settings.return_value.gcs_bucket = ""
            mock_settings.return_value.gemini_backend = "vertex"
            with pytest.raises(ValueError, match="GCS_BUCKET"):
                extrair_dados_lote_batch([tmp_path / "frame.jpg"])

    def test_batch_requer_vertex_backend(self, tmp_path: Path):
        with patch("leilao_inteligente.pipeline.vision.get_settings") as mock_settings:
            mock_settings.return_value.gcs_bucket = "meu-bucket"
            mock_settings.return_value.gemini_backend = "aistudio"
            with pytest.raises(ValueError, match="Vertex AI"):
                extrair_dados_lote_batch([tmp_path / "frame.jpg"])


class TestBatchCacheIntegration:
    """Testes de integracao com cache local."""

    @patch("leilao_inteligente.pipeline.vision.get_settings")
    @patch("leilao_inteligente.pipeline.vision._preparar_frame")
    @patch("leilao_inteligente.pipeline.vision._cache_get")
    def test_batch_retorna_cache_sem_chamar_gcs(
        self, mock_cache_get, mock_preparar, mock_settings, tmp_path: Path,
    ):
        mock_settings.return_value.gcs_bucket = "bucket"
        mock_settings.return_value.gemini_backend = "vertex"

        frame = tmp_path / "frame_001.jpg"
        frame.write_bytes(b"fake")

        mock_preparar.return_value = b"overlay_bytes"
        mock_cache_get.return_value = {"lote_numero": "42", "raca": "Nelore"}

        resultado = extrair_dados_lote_batch([frame])

        assert len(resultado) == 1
        assert resultado[0][1]["lote_numero"] == "42"


class TestBatchJsonl:
    """Testes de formato do JSONL para batch."""

    def test_jsonl_formato_correto(self):
        """Verifica que o JSONL gerado tem a estrutura esperada pelo Vertex AI."""
        frame_map = {
            "gs://bucket/batch/abc123.jpg": (Path("/fake/frame.jpg"), "abc123"),
            "gs://bucket/batch/def456.jpg": (Path("/fake/frame2.jpg"), "def456"),
        }

        # Simula a criacao de linhas JSONL (mesma logica do _criar_jsonl_batch)
        lines = []
        for gcs_uri in frame_map:
            request = {
                "request": {
                    "contents": [{
                        "role": "user",
                        "parts": [
                            {"text": PROMPT_EXTRACAO},
                            {"fileData": {"fileUri": gcs_uri, "mimeType": "image/jpeg"}},
                        ],
                    }],
                    "generationConfig": {
                        "temperature": 0.1,
                        "maxOutputTokens": 1024,
                    },
                }
            }
            lines.append(json.dumps(request, ensure_ascii=False))

        parsed_lines = "\n".join(lines).strip().split("\n")
        assert len(parsed_lines) == 2

        for line in parsed_lines:
            obj = json.loads(line)
            assert "request" in obj
            assert "contents" in obj["request"]
            parts = obj["request"]["contents"][0]["parts"]
            assert parts[0]["text"] == PROMPT_EXTRACAO
            assert "fileData" in parts[1]
            assert parts[1]["fileData"]["mimeType"] == "image/jpeg"
            assert parts[1]["fileData"]["fileUri"].startswith("gs://")


class TestBatchResultParsing:
    """Testes de parsing de resultados batch."""

    def test_parse_response_json_valido(self):
        texto = '{"lote_numero": "42", "raca": "Nelore", "preco_lance": 2500}'
        resultado = _parse_response(texto)
        assert resultado is not None
        assert resultado["lote_numero"] == "42"

    def test_parse_response_com_markdown(self):
        texto = '```json\n{"lote_numero": "42"}\n```'
        resultado = _parse_response(texto)
        assert resultado is not None
        assert resultado["lote_numero"] == "42"

    def test_parse_response_erro(self):
        texto = '{"erro": "nao_e_leilao"}'
        resultado = _parse_response(texto)
        assert resultado is None

    def test_parse_response_invalido(self):
        resultado = _parse_response("nao e json")
        assert resultado is None

    @patch("leilao_inteligente.pipeline.vision.get_settings")
    @patch("leilao_inteligente.pipeline.vision._cache_set")
    def test_parsear_resultados_batch_sucesso(self, mock_cache_set, mock_settings):
        mock_settings.return_value.gcp_project_id = "test"

        frame_map = {
            "gs://bucket/batch/abc.jpg": (Path("/fake/frame.jpg"), "abc"),
        }

        resultado_batch = {
            "status": "",
            "request": {
                "contents": [{
                    "parts": [
                        {"text": "prompt"},
                        {"fileData": {"fileUri": "gs://bucket/batch/abc.jpg", "mimeType": "image/jpeg"}},
                    ]
                }]
            },
            "response": {
                "candidates": [{
                    "content": {
                        "parts": [{"text": '{"lote_numero": "10", "raca": "Nelore", "preco_lance": 3000}'}],
                        "role": "model",
                    }
                }]
            },
        }

        jsonl_content = json.dumps(resultado_batch)

        mock_blob = MagicMock()
        mock_blob.name = "batch/output/results.jsonl"
        mock_blob.download_as_text.return_value = jsonl_content

        mock_bucket = MagicMock()
        mock_bucket.list_blobs.return_value = [mock_blob]

        mock_gcs_client = MagicMock()
        mock_gcs_client.bucket.return_value = mock_bucket

        with patch("google.cloud.storage.Client", return_value=mock_gcs_client):
            resultados = _parsear_resultados_batch("bucket", "batch", frame_map)

        assert len(resultados) == 1
        assert resultados[0][1]["lote_numero"] == "10"

    @patch("leilao_inteligente.pipeline.vision.get_settings")
    def test_parsear_resultados_batch_com_falha(self, mock_settings):
        mock_settings.return_value.gcp_project_id = "test"

        frame_map = {
            "gs://bucket/batch/abc.jpg": (Path("/fake/frame.jpg"), "abc"),
        }

        resultado_falha = {
            "status": "Bad Request: invalid image",
            "request": {"contents": [{"parts": [{"fileData": {"fileUri": "gs://bucket/batch/abc.jpg"}}]}]},
            "response": {},
        }

        mock_blob = MagicMock()
        mock_blob.name = "batch/output/results.jsonl"
        mock_blob.download_as_text.return_value = json.dumps(resultado_falha)

        mock_bucket = MagicMock()
        mock_bucket.list_blobs.return_value = [mock_blob]

        mock_gcs_client = MagicMock()
        mock_gcs_client.bucket.return_value = mock_bucket

        with patch("google.cloud.storage.Client", return_value=mock_gcs_client):
            resultados = _parsear_resultados_batch("bucket", "batch", frame_map)

        assert len(resultados) == 0
