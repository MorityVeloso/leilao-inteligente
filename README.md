# Leilao Inteligente

Sistema de IA para monitoramento e analise de leiloes de gado no YouTube.

## O que faz

- Baixa videos gravados de leiloes no YouTube
- Extrai frames e detecta mudancas de overlay
- Usa Gemini Flash Vision para extrair dados estruturados (lote, quantidade, raca, sexo, idade, preco, local)
- Constroi base historica para analise de tendencias
- Modo ao vivo: acompanha stream e compara com historico em tempo real

## Stack

- Python 3.12+
- Gemini 2.0 Flash (visao)
- OpenCV (deteccao de mudanca)
- yt-dlp + ffmpeg (captura)
- SQLite + SQLAlchemy (banco)
- Typer (CLI)
- Streamlit (dashboard)

## Setup

```bash
# Clonar
git clone https://github.com/MorityVeloso/leilao-inteligente.git
cd leilao-inteligente

# Ambiente virtual
python3.13 -m venv .venv
source .venv/bin/activate

# Instalar
pip install -e ".[dev]"

# Configurar
cp .env.example .env
# Editar .env com sua GEMINI_API_KEY

# Verificar
leilao --help
```

## Uso

```bash
# Processar um video gravado
leilao processar URL_DO_VIDEO

# Processar canal inteiro
leilao canal URL_DO_CANAL --limite 50

# Ver leiloes processados
leilao listar

# Dashboard
leilao dashboard

# Modo ao vivo
leilao ao-vivo URL_DO_STREAM
```

## Requisitos

- Python 3.12+
- ffmpeg
- Chave da API Gemini (gratis)
