# Leilao Inteligente

Sistema de IA para monitorar leilões de gado ao vivo no YouTube, extrair dados de lotes via Gemini Vision, e apresentar analytics num dashboard React.

## Stack

- **Backend:** Python 3.12+, FastAPI, SQLAlchemy
- **AI:** Google Gemini 2.5 Flash via **Vertex AI** (visão), Claude (calibração)
- **Frontend:** React 19, TypeScript, Tailwind, shadcn/ui, Recharts
- **DB:** Supabase PostgreSQL (prod), SQLite (local)
- **Infra:** Cloud Run (API), Vercel (frontend), GCS (batch)
- **Custo Gemini:** ~R$ 1,30/hora de vídeo (Vertex AI). ~R$ 21/mês para 4 leilões de 4h

## Comandos

```bash
# Backend
uv run uvicorn leilao_inteligente.api:app --reload --port 8000
uv run pytest tests/ -v
uv run ruff check src/

# Frontend
cd dashboard && npm run dev   # localhost:5173
cd dashboard && npm run build

# CLI
uv run leilao processar <url>
uv run leilao listar
```

## Estrutura

```
src/leilao_inteligente/
  api.py              # FastAPI (30+ endpoints)
  config.py           # Settings (env vars)
  cli.py              # CLI (typer)
  pipeline/
    processor.py      # Orquestrador (3 passadas)
    downloader.py     # yt-dlp + proxy
    frame_extractor.py
    change_detector.py
    vision.py         # Gemini API (online + batch)
    validator.py      # Normalização OCR
    calibration.py    # Perfis de calibração por canal
    sampler.py        # Frames amostrais do stream
  models/
    database.py       # SQLAlchemy (Leilao, Lote, Configuracao, CotacaoMercado)
    schemas.py        # Pydantic (LoteExtraido, LoteConsolidado)
  storage/
    db.py             # Engine/session
    repository.py     # CRUD
    supabase_storage.py
  market/
    scraper.py        # Scot + Datagro
    cepea_collector.py
    collector.py      # Orquestrador + persistência
    tendencia.py      # Regressão linear

dashboard/src/
  pages/              # 8 páginas (dashboard, leiloes, analise, comparativo, ranking, mercado, ao-vivo, config)
  components/         # FiltroBar, LotesTable, MetricasCards, TendenciaChart, etc.
  lib/api.ts          # API client (todos os endpoints)
  hooks/              # useFiltros, useCustos
```

---

## Protocolo de Calibração por Canal

### QUANDO CALIBRAR

**SEMPRE.** Todo vídeo novo deve ser calibrado antes do processamento, independente de o canal já ter calibração anterior. Cada leilão pode ter layout diferente, patrocinadores novos, overlay atualizado.

Se o canal já tiver calibração, usar como base e atualizar com o que mudou. Nunca pular a análise visual assumindo que "é o mesmo canal, deve ser igual".

### COMO CALIBRAR

Use o comando `/calibrar <url>` — ele carrega o protocolo completo passo a passo.

```
/calibrar https://youtube.com/watch?v=...
```

**NUNCA processar um vídeo sem antes ter passado pelo `/calibrar`.** Se o usuário mandar uma URL pedindo pra processar direto, informe que precisa calibrar primeiro e sugira o `/calibrar`.

### COLETA DE FRAMES

Analisar no mínimo **30 frames** do vídeo, buscando:

- **10+ frames com overlay normal** (lote em andamento, preço visível)
- **5+ frames de transição** (troca de lote, preço zerando/mudando)
- **5+ frames com preço diferente do mesmo lote** (disputa em andamento)
- **3+ frames com carimbo/indicador de venda** (se o canal usar)
- **3+ frames de intervalo/propaganda** (pra saber o que ignorar)
- **2+ frames de repescagem** (mesmo lote aparecendo de novo, se houver)
- **2+ frames com R$ 0,00** (overlay carregando — pra documentar o comportamento)

### CHECKLIST DE ANÁLISE (6 seções obrigatórias)

#### 1. LAYOUT DOS CAMPOS (`layout`)

Descrever com precisão onde fica cada campo no overlay:

- [ ] Onde está o **número do lote** e como diferenciá-lo da quantidade
- [ ] Onde está a **quantidade** e sua relação com raça/sexo (ex: "2 VACA(S)")
- [ ] Onde está a **raça** e como aparece (NELORE, ANELORADO, MESTIÇO, etc.)
- [ ] Onde está o **sexo** e como inferir (GARROTE=macho, NOVILHA=fêmea)
- [ ] Onde está a **idade** e formato (meses, anos)
- [ ] Onde está o **preço** (R$) e formato exato
- [ ] Onde está a **fazenda/vendedor** (ou se não aparece neste canal)
- [ ] Onde está a **cidade/estado** (banners, logos, overlay)
- [ ] Onde está o **timestamp** (hora do vídeo no overlay)
- [ ] Cores e formatação da barra do overlay (fundo escuro, texto claro, etc.)

#### 2. ARMADILHAS E CONFUSÕES (`ignorar`)

Listar TUDO que pode confundir o Gemini:

- [ ] Números que NÃO são lote nem quantidade (comissário, sequencial, telefone)
- [ ] Logos e marcas do canal que parecem dados
- [ ] Banners de propaganda/patrocínio
- [ ] Nomes de leiloeiros vs nomes de fazendas
- [ ] QR codes, redes sociais, links
- [ ] Textos fixos que aparecem em todo frame

#### 3. CARIMBO / INDICADOR DE VENDA (`carimbo`)

Identificar como o canal sinaliza que o lote foi vendido:

- [ ] Tipo: selo "VENDIDO", martelo 3D, overlay colorido, texto "ARREMATADO", mudança de cor da barra, animação
- [ ] Posição: centro da tela, sobre o preço, barra inteira, canto
- [ ] Aparição: snap instantâneo, fade-in gradual, pisca
- [ ] Duração: fica 2-3s e some, ou permanece até trocar lote
- [ ] Se NÃO usa carimbo: registrar `"sem_carimbo"` explicitamente

**IMPORTANTE:** Carimbo visível = **certeza de arrematação**, independente de variação de preço. Mas nem toda arrematação terá carimbo (podem esquecer). O Gemini deve retornar `carimbo_vendido: true` SOMENTE quando vê o indicador visual, nunca inferir.

#### 4. COMPORTAMENTO DE PREÇO (`comportamento_preco`)

Como o preço funciona neste canal:

- [ ] O preço no overlay é por **cabeça** ou por **arroba (@)**?
- [ ] Mostra lance atual atualizado em tempo real, ou só atualiza entre frames?
- [ ] **R$ 0,00 = overlay carregando (NÃO é preço real).** Aparece brevemente quando o lote entra. Nem sempre será capturado (é rápido)
- [ ] O primeiro preço > 0 é o **preço de pedida** (mínimo que o dono do gado aceita). NÃO é lance
- [ ] Preço pode **subir** (lances de compradores), **ficar estável** (1 lance aceito ou nenhum lance), ou **cair** (dono baixou a pedida pra tentar vender)
- [ ] Faixa de preço típica deste leilão
- [ ] Há indicador visual de lance novo (pisca, muda de cor)?

#### 5. DINÂMICA DO LEILÃO (`dinamica_leilao`)

Como identificar o status de cada lote:

- [ ] **Arrematado com certeza**: carimbo visível (independente de preço)
- [ ] **Arrematado provável**: preço subiu acima do preço de pedida (disputa com múltiplos lances)
- [ ] **Ambíguo**: preço estável + sem carimbo (pode ser 1 lance aceito OU sem disputa)
- [ ] **Ambíguo**: preço caiu + sem carimbo (dono baixou pedida, pode ter vendido ou não)
- [ ] **Sem disputa (sintomas)**: preço não mudou, sem carimbo, lote simplesmente troca. NÃO tem indicador visual de "não vendeu"
- [ ] **Repescagem**: como saber? (mesmo lote reaparece — tem texto "REPESCAGEM", "2ª CHANCE", ou simplesmente repete?)
- [ ] Existe **contador de lances** visível?
- [ ] Tempo médio de cada lote na tela (30s? 1min? 3min?)
- [ ] Existe **lance mínimo** ou **incremento** visível?

**NOTA:** O status final é determinado pelo pipeline (variação de preço entre frames + carimbo), não pelo Gemini isoladamente. O Gemini extrai dados de cada frame individual — o pipeline compara frames ao longo do tempo.

#### 6. TRANSIÇÕES ENTRE LOTES (`transicoes`)

Como é a troca de lotes:

- [ ] Transição: corte seco, fade, tela preta, animação
- [ ] Há tela de **intervalo** entre lotes? (propaganda, logo, "aguarde")
- [ ] O overlay do próximo lote aparece antes ou depois do preço zerar?
- [ ] Há **numeração sequencial** previsível (lote 1, 2, 3...) ou pode pular?

### TEMPLATE DE SAÍDA

```python
from leilao_inteligente.pipeline.calibration import salvar_calibracao

salvar_calibracao(canal, {
    "canal": "nome exato do canal",
    "layout": """
    [descrição detalhada de cada campo - posição, cor, formato]
    """,
    "ignorar": """
    [lista de tudo que NÃO é dado do lote]
    """,
    "carimbo": """
    [descrição do indicador de venda OU "sem_carimbo"]
    """,
    "comportamento_preco": """
    [como o preço funciona: tipo, atualização, faixa, indicadores]
    """,
    "dinamica_leilao": """
    [como identificar arrematado vs sem disputa vs repescagem]
    """,
    "transicoes": """
    [como é a troca entre lotes, intervalos, numeração]
    """,
})
```

### VALIDAÇÃO PÓS-CALIBRAÇÃO

Antes de salvar, verificar:

- [ ] Cada uma das 6 seções está preenchida (nenhuma vazia)
- [ ] O `layout` diferencia claramente lote_numero vs quantidade
- [ ] O `carimbo` é específico o suficiente (posição + tipo + aparição)
- [ ] O `comportamento_preco` diz se é R$/cabeça ou R$/@
- [ ] O `comportamento_preco` documenta que R$ 0,00 = overlay carregando (não é preço)
- [ ] O `dinamica_leilao` explica que carimbo = certeza, preço subiu = provável, resto = ambíguo
- [ ] Testei mentalmente: "se eu fosse o Gemini lendo um frame deste canal com este prompt, eu acertaria?"

### CALIBRAÇÕES EXISTENTES

Consultar antes de calibrar (pode ser atualização, não criação):

```python
from leilao_inteligente.pipeline.calibration import obter_calibracao
cal = obter_calibracao("nome do canal")
# Se existir, comparar visualmente e decidir se precisa recalibrar
```
