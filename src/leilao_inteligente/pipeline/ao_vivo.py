"""Motor de monitoramento de leilão ao vivo."""

import logging
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from queue import Queue

logger = logging.getLogger(__name__)


@dataclass
class LoteAoVivo:
    """Estado incremental de um lote durante monitoramento ao vivo."""
    lote_numero: str
    quantidade: int = 0
    raca: str | None = None
    sexo: str | None = None
    condicao: str | None = None
    idade_meses: int | None = None
    fazenda_vendedor: str | None = None
    preco_atual: Decimal = Decimal("0")
    preco_inicial: Decimal = Decimal("0")
    preco_maximo: Decimal = Decimal("0")
    frames_analisados: int = 0
    confianca_media: float = 0.0
    carimbo_vendido: bool = False
    status: str = "em_curso"  # em_curso, arrematado, incerto
    inicio: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    fim: datetime | None = None
    _precos: list[Decimal] = field(default_factory=list, repr=False)
    _confiancas: list[float] = field(default_factory=list, repr=False)

    def atualizar_com_frame(self, dados: dict) -> None:
        """Atualiza o lote com dados de um novo frame."""
        preco = Decimal(str(dados.get("preco_lance", 0)))

        if preco > 0:
            self._precos.append(preco)
            self.preco_atual = preco
            if self.preco_inicial == 0:
                self.preco_inicial = preco
            self.preco_maximo = max(self.preco_maximo, preco)

        # Atualizar campos com valor mais recente não-nulo
        for campo in ["quantidade", "raca", "sexo", "condicao", "idade_meses", "fazenda_vendedor"]:
            valor = dados.get(campo)
            if valor is not None:
                setattr(self, campo, valor)

        # Carimbo: uma vez true, sempre true
        if dados.get("carimbo_vendido"):
            self.carimbo_vendido = True
            self.status = "arrematado"

        conf = dados.get("confianca", 0.0)
        if conf:
            self._confiancas.append(float(conf))
            self.confianca_media = sum(self._confiancas) / len(self._confiancas)

        self.frames_analisados += 1

    def finalizar(self) -> None:
        """Chamado quando o lote sai da pista (trocou pro próximo)."""
        self.fim = datetime.now(tz=timezone.utc)
        if self.status == "em_curso":
            if self.carimbo_vendido:
                self.status = "arrematado"
            elif self.preco_atual > self.preco_inicial and self.preco_inicial > 0:
                self.status = "arrematado"
            elif len(set(self._precos)) >= 3:
                self.status = "arrematado"
            else:
                self.status = "incerto"

    def to_dict(self) -> dict:
        """Serializa para enviar via SSE."""
        return {
            "lote_numero": self.lote_numero,
            "quantidade": self.quantidade,
            "raca": self.raca,
            "sexo": self.sexo,
            "condicao": self.condicao,
            "idade_meses": self.idade_meses,
            "fazenda_vendedor": self.fazenda_vendedor,
            "preco_atual": float(self.preco_atual),
            "preco_inicial": float(self.preco_inicial),
            "preco_maximo": float(self.preco_maximo),
            "frames_analisados": self.frames_analisados,
            "confianca_media": round(self.confianca_media, 2),
            "carimbo_vendido": self.carimbo_vendido,
            "status": self.status,
            "inicio": self.inicio.isoformat(),
            "fim": self.fim.isoformat() if self.fim else None,
            "precos_historico": [float(p) for p in self._precos],
        }


@dataclass
class SessaoAoVivo:
    """Sessão de monitoramento ao vivo."""
    id: str
    url: str
    canal: str
    titulo: str
    status: str = "conectado"  # conectado, analisando, pausado, encerrando, encerrado
    lote_atual: LoteAoVivo | None = None
    lotes_finalizados: list[LoteAoVivo] = field(default_factory=list)
    eventos: Queue = field(default_factory=Queue, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)
    _parar: threading.Event = field(default_factory=threading.Event, repr=False)
    criado_em: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    iniciado_em: datetime | None = None
    encerrado_em: datetime | None = None

    def total_lotes(self) -> int:
        n = len(self.lotes_finalizados)
        if self.lote_atual:
            n += 1
        return n

    def iniciar(self, prompt_calibrado: str | None = None) -> None:
        """Inicia a captura ao vivo em thread separada."""
        self.status = "analisando"
        self.iniciado_em = datetime.now(tz=timezone.utc)
        self._thread = threading.Thread(
            target=_loop_captura,
            args=(self, prompt_calibrado),
            daemon=True,
        )
        self._thread.start()

    def pausar(self) -> None:
        self.status = "pausado"

    def retomar(self) -> None:
        self.status = "analisando"

    def encerrar(self) -> None:
        self._parar.set()
        self.status = "encerrando"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "canal": self.canal,
            "titulo": self.titulo,
            "status": self.status,
            "lote_atual": self.lote_atual.to_dict() if self.lote_atual else None,
            "lotes_finalizados": [l.to_dict() for l in self.lotes_finalizados],
            "total_lotes": self.total_lotes(),
            "criado_em": self.criado_em.isoformat(),
            "iniciado_em": self.iniciado_em.isoformat() if self.iniciado_em else None,
        }


# --- Validação e captura ---


def validar_live(url: str) -> dict:
    """Valida se a URL é um stream ao vivo do YouTube."""
    import yt_dlp
    from leilao_inteligente.config import get_settings

    settings = get_settings()
    ydl_opts = {"quiet": True, "no_warnings": True}
    if settings.cookies_path:
        ydl_opts["cookiefile"] = str(settings.cookies_path)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            is_live = info.get("is_live", False)
            return {
                "is_live": is_live,
                "canal": info.get("channel", ""),
                "titulo": info.get("title", ""),
                "video_id": info.get("id", ""),
                "erro": None if is_live else "Vídeo não é uma transmissão ao vivo",
            }
    except Exception as e:
        return {"is_live": False, "canal": "", "titulo": "", "video_id": "", "erro": str(e)}


def _obter_stream_url(url: str) -> str | None:
    """Obtém URL do stream via yt-dlp."""
    import yt_dlp
    from leilao_inteligente.config import get_settings

    settings = get_settings()
    ydl_opts = {
        "format": "best[height<=360][ext=mp4]/best[height<=360]/best",
        "quiet": True,
        "no_warnings": True,
    }
    if settings.cookies_path:
        ydl_opts["cookiefile"] = str(settings.cookies_path)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get("url")
    except Exception as e:
        logger.error("Erro obtendo stream URL: %s", e)
        return None


def _capturar_frame_stream(stream_url: str, output_path: Path) -> bool:
    """Captura 1 frame do stream ao vivo via ffmpeg."""
    import subprocess

    cmd = [
        "ffmpeg", "-y",
        "-i", stream_url,
        "-frames:v", "1",
        "-q:v", "2",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        return result.returncode == 0 and output_path.exists()
    except Exception:
        return False


def _loop_captura(sessao: SessaoAoVivo, prompt_calibrado: str | None = None) -> None:
    """Loop principal: captura frame → Gemini → atualiza lote → emite evento.

    Roda em thread separada. Para quando sessao._parar é setado.
    """
    import json
    import tempfile
    import numpy as np
    import cv2
    from google.genai.types import Part
    from leilao_inteligente.pipeline.vision import (
        _preparar_frame, _chamar_gemini, _parse_response, _get_client, PROMPT_EXTRACAO,
    )
    from leilao_inteligente.pipeline.validator import normalizar_dados

    intervalo = 5
    stream_url = _obter_stream_url(sessao.url)
    if not stream_url:
        sessao.status = "erro"
        sessao.eventos.put({"tipo": "erro", "mensagem": "Não foi possível obter stream URL"})
        return

    client = _get_client()
    prompt = prompt_calibrado or PROMPT_EXTRACAO
    frame_anterior_bytes: bytes | None = None
    frame_num = 0

    logger.info("Iniciando captura ao vivo: %s", sessao.titulo)

    while not sessao._parar.is_set():
        if sessao.status == "pausado":
            time.sleep(1)
            continue

        frame_num += 1
        frame_path = Path(tempfile.mktemp(suffix=".jpg"))

        try:
            # 1. Capturar frame
            if not _capturar_frame_stream(stream_url, frame_path):
                logger.info("Frame falhou, renovando stream URL...")
                stream_url = _obter_stream_url(sessao.url)
                if not stream_url:
                    sessao.eventos.put({"tipo": "erro", "mensagem": "Stream perdido"})
                    break
                continue

            # 2. Preparar e detectar mudança
            overlay_bytes = _preparar_frame(frame_path)

            if frame_anterior_bytes is not None:
                img_atual = cv2.imdecode(np.frombuffer(overlay_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
                img_anterior = cv2.imdecode(np.frombuffer(frame_anterior_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
                if img_atual.shape == img_anterior.shape:
                    diff = np.mean(np.abs(img_atual.astype(float) - img_anterior.astype(float)))
                    if diff < 3.0:
                        frame_anterior_bytes = overlay_bytes
                        time.sleep(intervalo)
                        continue

            frame_anterior_bytes = overlay_bytes

            # 3. Enviar ao Gemini
            image_part = Part.from_bytes(data=overlay_bytes, mime_type="image/jpeg")
            response = _chamar_gemini(client, image_part, prompt=prompt)

            if not response.text:
                time.sleep(intervalo)
                continue

            dados = _parse_response(response.text)
            if not dados:
                sessao.eventos.put({"tipo": "frame_sem_dados", "frame": frame_num})
                time.sleep(intervalo)
                continue

            # 4. Normalizar
            dados = normalizar_dados(dados)
            lote_numero = str(dados.get("lote_numero", ""))

            if not lote_numero or lote_numero == "0":
                time.sleep(intervalo)
                continue

            # 5. Detectar troca de lote
            if sessao.lote_atual and sessao.lote_atual.lote_numero != lote_numero:
                sessao.lote_atual.finalizar()
                sessao.lotes_finalizados.append(sessao.lote_atual)
                sessao.eventos.put({
                    "tipo": "lote_finalizado",
                    "lote": sessao.lote_atual.to_dict(),
                })
                sessao.lote_atual = None

            # 6. Criar ou atualizar lote
            if sessao.lote_atual is None:
                sessao.lote_atual = LoteAoVivo(lote_numero=lote_numero)
                sessao.eventos.put({"tipo": "novo_lote", "lote_numero": lote_numero})

            sessao.lote_atual.atualizar_com_frame(dados)

            # 7. Emitir evento
            sessao.eventos.put({
                "tipo": "lote_atualizado",
                "lote": sessao.lote_atual.to_dict(),
                "frame": frame_num,
            })

        except Exception as e:
            logger.error("Erro no frame %d: %s", frame_num, e)
            sessao.eventos.put({"tipo": "erro", "mensagem": str(e)})

        finally:
            if frame_path.exists():
                frame_path.unlink()

        time.sleep(intervalo)

    # Finalizar último lote
    if sessao.lote_atual:
        sessao.lote_atual.finalizar()
        sessao.lotes_finalizados.append(sessao.lote_atual)
        sessao.lote_atual = None

    sessao.encerrado_em = datetime.now(tz=timezone.utc)
    sessao.status = "encerrado"
    sessao.eventos.put({"tipo": "sessao_encerrada"})
    logger.info("Sessão ao vivo encerrada: %d lotes", len(sessao.lotes_finalizados))
