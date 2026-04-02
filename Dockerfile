FROM python:3.13-slim

WORKDIR /app

# Dependencias Python
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir .

ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "leilao_inteligente.api:app", "--host", "0.0.0.0", "--port", "8080"]
