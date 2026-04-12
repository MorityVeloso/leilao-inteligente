# Calibrar vídeo de leilão

Argumento recebido (URL do vídeo): $ARGUMENTS

---

## PROTOCOLO DE CALIBRAÇÃO — EXECUTAR PASSO A PASSO

Você recebeu uma URL de vídeo de leilão de gado brasileiro. Você DEVE calibrar antes de processar. Siga cada etapa abaixo na ordem. NÃO pule etapas. NÃO processe o vídeo sem completar todo o protocolo.

---

## CONTEXTO: COMO FUNCIONA UM LEILÃO DE GADO

Antes de analisar qualquer frame, entenda a mecânica:

### Fluxo de um lote

1. **Lote entra na pista** — o overlay aparece com os dados (número, raça, sexo, quantidade, idade)
2. **Preço R$ 0,00** — overlay recém-carregado, NÃO é preço real. Aparece por poucos segundos
3. **Preço de pedida** — primeiro valor > 0. É o **preço mínimo** que o dono do gado aceita receber por cabeça. Este é o preço inicial real
4. **Lances** — compradores fazem lances via WhatsApp ou presencialmente. O preço sobe a cada lance
5. **Desfecho** — três possibilidades:
   - **Arrematado com disputa**: preço subiu acima do preço de pedida (vários lances). Pode ter carimbo
   - **Arrematado com lance único**: alguém aceitou o preço de pedida (preço estável). Pode ter carimbo
   - **Sem disputa**: ninguém deu lance. Lote sai e vem o próximo. Sem carimbo, sem sinalização

### Sobre o preço

- **R$ 0,00 NÃO É PREÇO.** É o overlay carregando. Ignorar. Nem sempre será capturado (é rápido)
- O **primeiro preço > 0** é o preço de pedida (mínimo do dono). Pode ser o único preço visível
- Preço pode **subir** (lances), **ficar estável** (1 lance ou nenhum), ou **cair** (dono aceita menos)
- Quando o preço cai, não há indicador visual — simplesmente o número diminui. Isso significa que o dono reduziu o mínimo aceitável, mas NÃO garante que houve lance

### Sobre o carimbo

- Carimbo visível = **CERTEZA de arrematação**, independente de variação de preço
- Mas **nem toda arrematação terá carimbo** — às vezes esquecem de colocar
- Sem carimbo + preço subiu = provavelmente arrematado (disputa)
- Sem carimbo + preço estável = **ambíguo** (pode ser 1 lance aceito OU sem disputa)
- Sem carimbo + preço caiu = **ambíguo** (dono baixou preço, pode ter vendido ou não)

### Sobre "sem disputa"

- NÃO existe indicador visual de "não vendeu" — o lote simplesmente sai e o próximo entra
- "Sem disputa" é determinado pelo pipeline baseado em sintomas: preço não mudou, sem carimbo
- Um lote pode ter preço estável e ser arrematado (1 lance = preço de pedida aceito)

---

## ETAPAS

### ETAPA 1 — METADADOS

Obtenha informações do vídeo:

```python
from leilao_inteligente.pipeline.downloader import obter_info_video
from leilao_inteligente.config import get_settings
info = obter_info_video("$ARGUMENTS", cookies_file=get_settings().cookies_path)
```

Extraia: título, canal, duração. Identifique o nome do canal.

### ETAPA 2 — CALIBRAÇÃO ANTERIOR

Verifique se já existe calibração para este canal:

```python
from leilao_inteligente.pipeline.calibration import obter_calibracao
cal = obter_calibracao(canal)
```

Se existir, use como referência — mas NÃO pule a análise visual. Cada leilão pode ter layout diferente, patrocinadores novos, overlay atualizado.

### ETAPA 3 — COLETA DE FRAMES (mínimo 30)

Extraia no mínimo 30 frames do vídeo, buscando variedade:

- **10+ frames com overlay normal** (lote em andamento, preço visível > 0)
- **5+ frames de transição** (troca de lote, preço zerando/mudando)
- **5+ frames com preço diferente do mesmo lote** (disputa — preço subindo)
- **3+ frames com carimbo/indicador de venda** (se o canal usar — nem sempre aparece)
- **3+ frames de intervalo/propaganda** (pra saber o que ignorar)
- **2+ frames de repescagem** (mesmo lote reaparecendo, se houver)
- **2+ frames com R$ 0,00** (overlay carregando — pra documentar o comportamento)

Use o sampler (ffmpeg direto do stream), download parcial, ou acesse frames do cache se o vídeo já foi baixado.

### ETAPA 4 — ANÁLISE VISUAL (6 seções obrigatórias)

Analise os frames coletados e preencha CADA seção. Nenhuma pode ficar vazia.

#### 4.1 LAYOUT DOS CAMPOS (`layout`)

Descreva com precisão onde fica cada campo no overlay:

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

#### 4.2 ARMADILHAS E CONFUSÕES (`ignorar`)

Listar TUDO que pode confundir o Gemini:

- [ ] Números que NÃO são lote nem quantidade (comissário, sequencial, telefone)
- [ ] Logos e marcas do canal que parecem dados
- [ ] Banners de propaganda/patrocínio
- [ ] Nomes de leiloeiros vs nomes de fazendas
- [ ] QR codes, redes sociais, links
- [ ] Textos fixos que aparecem em todo frame

#### 4.3 CARIMBO / INDICADOR DE VENDA (`carimbo`)

Identificar como o canal sinaliza que o lote foi vendido:

- [ ] Tipo: selo "VENDIDO", martelo 3D, overlay colorido, texto "ARREMATADO", mudança de cor da barra, animação
- [ ] Posição: centro da tela, sobre o preço, barra inteira, canto
- [ ] Aparição: snap instantâneo, fade-in gradual, pisca
- [ ] Duração: fica 2-3s e some, ou permanece até trocar lote
- [ ] Se NÃO usa carimbo: registrar `"sem_carimbo"` explicitamente

**IMPORTANTE:** Carimbo visível = certeza de arrematação. Mas nem toda arrematação terá carimbo (podem esquecer). O Gemini deve retornar `carimbo_vendido: true` SOMENTE quando vê o indicador visual, nunca inferir.

#### 4.4 COMPORTAMENTO DE PREÇO (`comportamento_preco`)

Como o preço funciona neste canal:

- [ ] O preço no overlay é por **cabeça** ou por **arroba (@)**?
- [ ] Mostra lance atual atualizado em tempo real, ou só atualiza entre frames?
- [ ] Quando não tem lance: mostra "R$ 0,00", campo vazio, "LANCE INICIAL", ou o preço base?
- [ ] **R$ 0,00 = overlay carregando (NÃO é preço real).** Documentar que aparece brevemente
- [ ] O primeiro preço > 0 é o **preço de pedida** (mínimo que o dono aceita). NÃO é lance
- [ ] Preço pode subir (lances), ficar estável (1 lance ou nenhum), ou cair (dono baixou pedida)
- [ ] Faixa de preço típica deste leilão
- [ ] Há indicador visual de lance novo (pisca, muda de cor)?

#### 4.5 DINÂMICA DO LEILÃO (`dinamica_leilao`)

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

#### 4.6 TRANSIÇÕES ENTRE LOTES (`transicoes`)

Como é a troca de lotes:

- [ ] Transição: corte seco, fade, tela preta, animação
- [ ] Há tela de **intervalo** entre lotes? (propaganda, logo, "aguarde")
- [ ] O overlay do próximo lote aparece antes ou depois do preço zerar?
- [ ] Há **numeração sequencial** previsível (lote 1, 2, 3...) ou pode pular?

### ETAPA 5 — AUTO-CALIBRAR CAPTURA

Rodar a auto-calibração para descobrir threshold e região do overlay ideais para este canal:

```python
from leilao_inteligente.pipeline.calibration import calibrar_captura
from pathlib import Path

# Usar os frames coletados na etapa 3
frames_dir = Path(f"data/frames/{video_id}_calib_frames")
frames = sorted(frames_dir.glob("calib_*.jpg"))
captura = calibrar_captura(frames)
print(captura)
```

Verificar os resultados:
- `threshold`: deve ser baixo o suficiente pra capturar mudanças de preço, alto o suficiente pra ignorar ruído
- `overlay_top_percent`: região onde fica a barra de dados (85 = bottom 15%, 62 = bottom 38%)
- `taxa_passagem`: ideal entre 20-50%. Se <15% = muito restritivo, se >80% = muito permissivo

Se os valores parecerem errados (ex: threshold muito alto, região errada), ajustar manualmente.

### ETAPA 6 — SALVAR CALIBRAÇÃO

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
    "captura": captura,  # da etapa 5
})
```

### ETAPA 7 — VALIDAÇÃO

Antes de salvar, verificar:

- [ ] Cada uma das 6 seções textuais está preenchida (NENHUMA vazia)
- [ ] `captura` presente com threshold, overlay_top_percent e taxa_passagem entre 20-50%
- [ ] O `layout` diferencia claramente lote_numero vs quantidade
- [ ] O `carimbo` é específico o suficiente (posição + tipo + aparição) ou explicitamente "sem_carimbo"
- [ ] O `comportamento_preco` diz se é R$/cabeça ou R$/@
- [ ] O `comportamento_preco` documenta que R$ 0,00 = overlay carregando (não é preço)
- [ ] O `dinamica_leilao` explica que carimbo = certeza, preço subiu = provável, resto = ambíguo
- [ ] Testei mentalmente: "se eu fosse o Gemini lendo um frame deste canal com este prompt, eu acertaria?"

### ETAPA 7 — PROCESSAR

Só agora, com a calibração salva, processar o vídeo:

```python
# A API busca a calibração automaticamente pelo canal
# POST /api/processar ou via CLI:
# uv run leilao processar "$ARGUMENTS"
```

Confirme ao usuário: calibração feita, processamento iniciado.

---

**REGRA ABSOLUTA:** Se qualquer etapa acima não foi completada, NÃO processe o vídeo. Informe ao usuário o que falta.
