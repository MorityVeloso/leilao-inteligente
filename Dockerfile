FROM python:3.13-slim

# ffmpeg + curl + Deno para yt-dlp
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Deno (runtime JS para yt-dlp resolver challenges do YouTube)
RUN curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh
ENV DENO_DIR=/tmp/deno

WORKDIR /app

# Dependencias Python
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir .
RUN pip install --no-cache-dir yt-dlp

# Diretorios de dados temporarios
RUN mkdir -p /app/data/frames /app/data/videos /app/data/gemini_cache /app/data/lote_frames

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "leilao_inteligente.api:app", "--host", "0.0.0.0", "--port", "8080"]
