# Fluxo de Processamento de Vídeo de Leilão

O processamento é sempre iniciado via conversa com Claude. Nunca pela UI.

## Pipeline (Haiku com recortes separados)

### 1. Amostrar frames (sem baixar vídeo)
```python
from leilao_inteligente.pipeline.sampler import extrair_frames_amostrais
frames, info = extrair_frames_amostrais(url)
```

### 2. Calibrar (Opus analisa amostras)
Claude Opus olha 5-10 frames e define:
- Coordenadas de recorte (onde fica o lote, dados, carimbo)
- Prompts específicos para cada recorte
- O que ignorar

```python
from leilao_inteligente.pipeline.calibration import salvar_calibracao
calibracao = {
    "canal": "LANCE TRANSMISSÃO",
    "recortes": {
        "lote": {"x_pct": 0, "y_pct": 75, "w_pct": 17, "h_pct": 25, "upscale": 3},
        "dados": {"x_pct": 15, "y_pct": 75, "w_pct": 85, "h_pct": 25},
        "full": {"width": 320, "quality": 70},
    },
    "prompt_lote": "Logo Rural + número GRANDE = LOTE. Ignore LOTE.",
    "prompt_dados": "QUANTIDADE, RAÇA, SEXO, IDADE, PREÇO, FAZENDA, VENDIDO.",
}
salvar_calibracao(info["channel"], calibracao)
```

### 3. Baixar vídeo + extrair frames + filtrar relevantes
```python
from leilao_inteligente.pipeline.downloader import baixar_video
from leilao_inteligente.pipeline.frame_extractor import extrair_frames
from leilao_inteligente.pipeline.change_detector import filtrar_frames_relevantes

video_path = baixar_video(url)
frames = extrair_frames(video_path, intervalo_segundos=5)
relevantes = filtrar_frames_relevantes(frames, top_percent=62, threshold=0.03)
```

### 4. Recortar frames (OpenCV)
```python
from leilao_inteligente.pipeline.cropper import recortar_todos
lote_batches, dados_batches = recortar_todos(relevantes, output_dir, calibracao["recortes"])
```

### 5. Processar com agentes Haiku (Claude Code)
Claude lança agentes em ondas de 15:
- **Agentes lote**: leem recorte 17% upscale → número do lote
- **Agentes dados**: leem dados_crop + full_crop → qty, raça, preço, fazenda, vendido
- **IMPORTANTE**: máximo 20 frames por agente (mais degrada qualidade)

### 6. Merge e consolidar
```python
from leilao_inteligente.pipeline.merger import processar_resultados
lotes = processar_resultados(resultado_dir)
```

### 7. Salvar no banco
```python
from leilao_inteligente.storage.repository import salvar_leilao
# Deletar lotes antigos se existir, inserir novos
```

### 8. Validar
Claude mostra 5 lotes ao usuário para conferência.

## Regras importantes

- **20 frames/agente** — nunca mais. Agentes com 200+ frames degradam qualidade
- **15 agentes/onda** — para não sobrecarregar o rate limit
- **Haiku para tudo** — Sonnet dá rate limit, Gemini confunde layouts
- **Recorte 17% + upscale 3x** — essencial para Haiku ler números pequenos
- **Canal = cache** — calibração salva por canal, mas verificada a cada vídeo
