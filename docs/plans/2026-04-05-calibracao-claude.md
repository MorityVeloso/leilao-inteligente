# Calibração por Claude — Pré-análise visual de vídeos de leilão

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Substituir o prompt genérico do Gemini por um prompt calibrado visualmente por Claude antes de cada processamento, eliminando erros de layout e a Passada 4 de detecção de carimbo.

**Architecture:** Antes de processar, Claude extrai ~20 frames amostrais direto do stream do YouTube (sem baixar o vídeo), analisa visualmente o layout do overlay e o padrão de carimbo, gera um prompt Gemini específico para aquele vídeo, e salva no banco por canal (cache). O pipeline então usa esse prompt em vez do genérico. O processamento é sempre iniciado via conversa com Claude, nunca pela UI.

**Tech Stack:** Python, yt-dlp (stream URLs), ffmpeg (frames de stream), SQLAlchemy, Gemini Flash Lite (com prompt calibrado), Claude (análise visual)

---

## Visão geral do fluxo

```
Usuário manda URL no chat
    │
    ▼
Claude: yt-dlp --no-download → metadados (duração, canal, título)
    │
    ▼
Claude: yt-dlp → stream URL 360p → ffmpeg extrai 20 frames amostrais
    │  (10 espaçados + 10 em transições via change detection local)
    │
    ▼
Claude olha frames e identifica:
    ├── Mapeamento de campos (onde fica lote, qty, raça, preço)
    ├── O que ignorar (ex: "Rural XX" no canto, logos, comissário)
    ├── Padrão de carimbo (VENDIDO, martelo, posição, fade/snap)
    └── Compara com perfil do canal (se existe)
    │
    ▼
Claude gera:
    ├── prompt_extracao: prompt Gemini específico para o layout
    └── perfil_carimbo: descrição do carimbo (ou "sem carimbo")
    │
    ▼
Salva na tabela Configuracao (chave: canal + hash do layout)
    │
    ▼
Pipeline roda com prompt calibrado
    ├── Passada 1: frames + filtro + Gemini com prompt específico
    ├── Passada 2: refinamento (sem mudança)
    ├── Passada 3: arrematação (sem mudança)
    └── Passada 4: ELIMINADA (carimbo já resolvido na calibração)
```

---

### Task 1: Extrator de frames amostrais do stream

**Objetivo:** Extrair ~20 frames de um vídeo do YouTube SEM baixar o vídeo inteiro. Usa stream URL + ffmpeg para buscar frames em timestamps específicos.

**Files:**
- Create: `src/leilao_inteligente/pipeline/sampler.py`

**Step 1: Implementar `extrair_frames_amostrais`**

```python
"""Extração de frames amostrais direto do stream do YouTube."""

import logging
import subprocess
from pathlib import Path

import cv2
import numpy as np
import yt_dlp

from leilao_inteligente.config import FRAMES_DIR

logger = logging.getLogger(__name__)


def _obter_stream_url(url: str, max_height: int = 360) -> tuple[str, dict]:
    """Obtém URL do stream e metadados sem baixar o vídeo.
    
    Returns:
        (stream_url, info_dict)
    """
    ydl = yt_dlp.YoutubeDL({"quiet": True})
    info = ydl.extract_info(url, download=False)
    
    # Encontrar melhor formato até max_height
    stream_url = None
    for f in info.get("formats", []):
        if (f.get("height") and f["height"] <= max_height 
            and f.get("vcodec", "none") != "none"
            and f.get("ext") == "mp4"):
            stream_url = f["url"]
    
    if not stream_url:
        # Fallback: qualquer formato com vídeo
        for f in info.get("formats", []):
            if f.get("height") and f["height"] <= max_height and f.get("vcodec", "none") != "none":
                stream_url = f["url"]
                break
    
    if not stream_url:
        raise ValueError(f"Nenhum stream de vídeo encontrado para {url}")
    
    return stream_url, info


def _extrair_frame_de_stream(
    stream_url: str, 
    segundo: int, 
    output_path: Path,
    timeout: int = 30,
) -> bool:
    """Extrai um único frame do stream via ffmpeg."""
    cmd = [
        "ffmpeg", "-ss", str(segundo), 
        "-i", stream_url, 
        "-frames:v", "1", "-q:v", "2", 
        "-y", str(output_path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.returncode == 0 and output_path.exists()


def _calcular_timestamps_amostrais(duracao_s: int, n_espaçados: int = 10) -> list[int]:
    """Calcula timestamps espaçados uniformemente, pulando início (pré-leilão) e fim."""
    # Pular primeiros 10min (abertura) e últimos 5min (encerramento)
    inicio = min(600, duracao_s // 10)
    fim = duracao_s - 300
    
    if fim <= inicio:
        fim = duracao_s
        inicio = 0
    
    intervalo = (fim - inicio) // (n_espaçados + 1)
    return [inicio + intervalo * (i + 1) for i in range(n_espaçados)]


def _detectar_transicoes(frames: list[Path], n_transicoes: int = 10) -> list[int]:
    """Detecta frames com maior change score (transições de lote).
    
    Returns:
        Índices dos frames com maior mudança no overlay.
    """
    scores = []
    
    for i in range(1, len(frames)):
        prev = cv2.imread(str(frames[i - 1]))
        curr = cv2.imread(str(frames[i]))
        if prev is None or curr is None:
            scores.append(0.0)
            continue
        
        h = curr.shape[0]
        # Região do overlay (30% inferior)
        roi_prev = cv2.cvtColor(prev[int(h * 0.7):], cv2.COLOR_BGR2GRAY)
        roi_curr = cv2.cvtColor(curr[int(h * 0.7):], cv2.COLOR_BGR2GRAY)
        
        diff = cv2.absdiff(roi_prev, roi_curr)
        score = float(np.mean(diff > 30))
        scores.append(score)
    
    # Pegar os N frames com maior mudança
    indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return indices[:n_transicoes]


def extrair_frames_amostrais(
    url: str, 
    n_espacados: int = 10,
    n_transicoes: int = 10,
) -> tuple[list[Path], dict]:
    """Extrai frames amostrais de um vídeo do YouTube sem baixar.
    
    1. Obtém stream URL via yt-dlp
    2. Extrai N frames espaçados via ffmpeg (direto do stream)
    3. Detecta transições e extrai frames adjacentes
    
    Returns:
        (lista_de_paths, info_dict)
    """
    stream_url, info = _obter_stream_url(url)
    duracao = info.get("duration", 0)
    video_id = info.get("id", "unknown")
    canal = info.get("channel", "")
    
    output_dir = FRAMES_DIR / f"{video_id}_amostra"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("Amostrando %s (%ds = %.1fh) canal=%s", video_id, duracao, duracao/3600, canal)
    
    # 1. Frames espaçados
    timestamps = _calcular_timestamps_amostrais(duracao, n_espacados)
    frames_espacados = []
    
    for ts in timestamps:
        out = output_dir / f"amostra_{ts:06d}.jpg"
        if out.exists() or _extrair_frame_de_stream(stream_url, ts, out):
            frames_espacados.append(out)
        else:
            logger.warning("Falha ao extrair frame em %ds", ts)
    
    logger.info("Extraídos %d/%d frames espaçados", len(frames_espacados), len(timestamps))
    
    # 2. Detectar transições nos frames espaçados
    if len(frames_espacados) >= 3:
        transicao_indices = _detectar_transicoes(frames_espacados, n_transicoes)
        
        # Para cada transição, extrair frame 5s antes e 5s depois
        frames_transicao = []
        for idx in transicao_indices:
            if idx >= len(timestamps):
                continue
            ts = timestamps[idx]
            for delta in [-5, 5]:
                ts_adj = max(0, ts + delta)
                out = output_dir / f"transicao_{ts_adj:06d}.jpg"
                if out.exists() or _extrair_frame_de_stream(stream_url, ts_adj, out):
                    frames_transicao.append(out)
    else:
        frames_transicao = []
    
    logger.info("Extraídos %d frames de transição", len(frames_transicao))
    
    todos = sorted(set(frames_espacados + frames_transicao))
    
    return todos, info
```

**Step 2: Testar com vídeo real**

```bash
python -c "
from leilao_inteligente.pipeline.sampler import extrair_frames_amostrais
frames, info = extrair_frames_amostrais('https://www.youtube.com/watch?v=1q59fQN0m5E')
print(f'Canal: {info[\"channel\"]}')
print(f'Duração: {info[\"duration\"]}s')
print(f'Frames amostrados: {len(frames)}')
for f in frames:
    print(f'  {f.name}')
"
```

Expected: ~20 frames extraídos do stream sem baixar o vídeo inteiro.

**Step 3: Commit**

```bash
git add src/leilao_inteligente/pipeline/sampler.py
git commit -m "feat: extrator de frames amostrais direto do stream YouTube"
```

---

### Task 2: Persistência de perfil de calibração por canal

**Objetivo:** Salvar e recuperar perfis de calibração (prompt customizado + padrão de carimbo) por canal. O canal é cache — se o layout mudou, gera-se novo perfil.

**Files:**
- Create: `src/leilao_inteligente/pipeline/calibration.py`

**Step 1: Implementar modelo de calibração**

```python
"""Persistência de perfis de calibração por canal."""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _chave_canal(canal: str) -> str:
    return f"calibracao:{canal.strip().lower()}"


def obter_calibracao(canal: str) -> dict | None:
    """Busca calibração existente para o canal."""
    from leilao_inteligente.storage.db import get_session
    from leilao_inteligente.models.database import Configuracao
    
    session = get_session()
    try:
        cfg = session.query(Configuracao).filter(
            Configuracao.chave == _chave_canal(canal)
        ).first()
        if cfg and cfg.valor:
            return json.loads(cfg.valor)
    except Exception as e:
        logger.warning("Erro ao buscar calibração: %s", e)
    finally:
        session.close()
    return None


def salvar_calibracao(canal: str, calibracao: dict) -> None:
    """Salva calibração no banco."""
    from leilao_inteligente.storage.db import get_session
    from leilao_inteligente.models.database import Configuracao
    
    chave = _chave_canal(canal)
    calibracao["atualizado_em"] = datetime.utcnow().isoformat()
    valor = json.dumps(calibracao, ensure_ascii=False)
    
    session = get_session()
    try:
        existing = session.query(Configuracao).filter(Configuracao.chave == chave).first()
        if existing:
            existing.valor = valor
            existing.atualizado_em = datetime.utcnow()
        else:
            session.add(Configuracao(chave=chave, valor=valor, atualizado_em=datetime.utcnow()))
        session.commit()
        logger.info("Calibração salva para canal '%s'", canal)
    finally:
        session.close()


def montar_prompt_gemini(calibracao: dict) -> str:
    """Monta o prompt do Gemini a partir da calibração.
    
    O prompt é dividido em 3 partes:
    1. Instruções gerais (fixo)
    2. Mapeamento de layout (específico do canal)
    3. Formato de resposta JSON (fixo)
    """
    layout = calibracao.get("layout", "")
    ignorar = calibracao.get("ignorar", "")
    
    prompt = f"""Analise este frame de um leilão de gado brasileiro transmitido ao vivo.

A imagem mostra o topo e a base do vídeo concatenados (o meio com o gado foi removido).
O overlay do leilão contém textos sobrepostos com dados do lote sendo leiloado.

Se NÃO houver overlay de lote (pista vazia, intervalo, propaganda, telefones, tela de espera):
{{"erro": "nao_e_leilao"}}

LAYOUT ESPECÍFICO DESTE CANAL:
{layout}

{f"IGNORE: {ignorar}" if ignorar else ""}

Se houver overlay com dados do lote, retorne APENAS este JSON sem markdown:
{{
    "lote_numero": "12",
    "quantidade": 25,
    "raca": "Nelore",
    "sexo": "femea",
    "condicao": null,
    "idade_meses": 16,
    "pelagem": null,
    "preco_lance": 2680.00,
    "local_cidade": "Rianápolis",
    "local_estado": "GO",
    "fazenda_vendedor": "SITIO BOA SORTE",
    "timestamp_video": null,
    "confianca": 0.95
}}

Regras:
- lote_numero: número/código do lote. Geralmente em destaque, isolado, perto da palavra "LOTE"
- quantidade: número de animais. SEMPRE aparece ANTES de "MACHO(S)", "VACA(S)", "FEMEA(S)", "NOVILHA(S)"
- raca: Nelore, Anelorado, Mestiço, Guzera, Senepol, Tabapua, Angus (apenas raça, sem condição)
- sexo: "macho", "femea" ou "misto"
- condicao: só fêmeas — "parida", "prenhe", "solteira", "desmamada". null se macho
- idade_meses: converter "16 MS"=16, "2 ANOS"=24, "36 M"=36. null se não visível
- preco_lance: valor em R$ por animal. Se "R$ ,00" ou "R$ .00" sem valor, retorne 0. Número sem R$ (ex: 2680.00)
- local_cidade: cidade do leilão (topo do frame, logos, banners)
- local_estado: sigla UF (2 letras)
- fazenda_vendedor: nome do vendedor/fazenda ("VENDEDOR:", "FAZ.", "FAZENDA")
- timestamp_video: hora do overlay (HH:MM:SS). null se não visível
- confianca: 0.0 a 1.0
- Campo não legível: null (não invente)
"""
    return prompt
```

**Step 2: Commit**

```bash
git add src/leilao_inteligente/pipeline/calibration.py
git commit -m "feat: persistência de calibração por canal"
```

---

### Task 3: Integrar prompt calibrado no pipeline de visão

**Objetivo:** Fazer `vision.py` aceitar prompt customizado em vez de usar o `PROMPT_EXTRACAO` fixo.

**Files:**
- Modify: `src/leilao_inteligente/pipeline/vision.py` — funções `_chamar_gemini`, `extrair_dados_frame`, `extrair_dados_lote`, `extrair_dados_lote_batch`

**Step 1: Adicionar parâmetro `prompt` às funções**

Em `_chamar_gemini` (linha ~353):
```python
def _chamar_gemini(client: genai.Client, image_part: Part, prompt: str = PROMPT_EXTRACAO) -> object:
    """Chama Gemini com retry em rate limit e timeout."""
    max_retries = 3
    for tentativa in range(max_retries):
        try:
            return client.models.generate_content(
                model=MODEL_NAME,
                contents=[prompt, image_part],  # ← usa prompt parametrizado
                ...
```

Em `extrair_dados_frame` (linha ~404): adicionar `prompt: str | None = None`

Em `extrair_dados_lote` (linha ~441): adicionar `prompt: str | None = None`
- Passar para `_processar_frame` e `_chamar_gemini`

Em `extrair_dados_lote_batch` (linha ~741): adicionar `prompt: str | None = None`
- Usar na criação do JSONL em `_criar_jsonl_batch`

**Step 2: Ajustar `processor.py` para passar prompt calibrado**

Em `processar_video` (linha ~640):
```python
def processar_video(
    url: str,
    batch: bool = False,
    on_progress=None,
    canal_youtube: str = "",
    prompt_calibrado: str | None = None,  # ← NOVO
) -> list[LoteConsolidado]:
```

Na chamada a `extrair_fn` (linha ~696):
```python
resultados_gemini = extrair_fn(
    frames_relevantes, callback=_on_frame_done,
    prompt=prompt_calibrado,  # ← NOVO
)
```

**Step 3: Commit**

```bash
git add src/leilao_inteligente/pipeline/vision.py src/leilao_inteligente/pipeline/processor.py
git commit -m "feat: prompt calibrado parametrizável no pipeline de visão"
```

---

### Task 4: Fluxo de calibração interativo no chat

**Objetivo:** Definir o fluxo que Claude executa quando o usuário manda uma URL. Não é código — é o **protocolo** que Claude segue no chat.

**Files:**
- Create: `docs/FLUXO_PROCESSAMENTO.md` — documentação do protocolo

**Step 1: Documentar o fluxo**

```markdown
# Fluxo de Processamento de Vídeo de Leilão

## Quando o usuário manda uma URL do YouTube:

### 1. Metadados
- Executar: `extrair_frames_amostrais(url)`
- Obter: canal, duração, título

### 2. Verificar calibração existente
- Buscar: `obter_calibracao(canal)`
- Se existe: mostrar ao usuário, perguntar se quer recalibrar

### 3. Analisar visualmente (Claude olha os frames)
- Abrir ~5 frames com Read tool
- Identificar:
  - Layout do overlay (posição de cada campo)
  - Elementos a ignorar (logos, números de comissário, etc.)
  - Padrão de carimbo (se existe, posição, tipo)
  
### 4. Gerar calibração
- Criar dict com:
  - `layout`: descrição textual do mapeamento de campos
  - `ignorar`: elementos que NÃO são dados do lote
  - `carimbo`: descrição do carimbo ou "sem_carimbo"
  - `canal`: nome do canal
  - `exemplo_lote`: um lote extraído manualmente como referência

### 5. Salvar e processar
- `salvar_calibracao(canal, calibracao)`
- `prompt = montar_prompt_gemini(calibracao)`
- Baixar vídeo e rodar pipeline com prompt calibrado

### 6. Validação
- Após processamento, mostrar 5 lotes ao usuário para conferência
```

**Step 2: Commit**

```bash
git add docs/FLUXO_PROCESSAMENTO.md
git commit -m "docs: protocolo de calibração e processamento de vídeos"
```

---

### Task 5: Eliminar Passada 4 e limpar código legado

**Objetivo:** Remover a Passada 4 (detecção de carimbo visual automática) e o módulo de stamp_profile. A detecção de carimbo agora é feita por Claude na calibração — informando no prompt se o canal tem carimbo e como ele aparece.

**Files:**
- Modify: `src/leilao_inteligente/pipeline/processor.py` — remover Passada 4
- Delete (optional): `src/leilao_inteligente/pipeline/stamp_profile.py` — código legado

**Step 1: Modificar processor.py**

Em `processar_video`, remover as linhas 769-774:
```python
    # 8. Passada 4: detectar carimbo visual de arrematação (VENDIDO, martelo, etc)
    # REMOVIDO — carimbo agora é detectado na calibração por Claude
    # O prompt calibrado já instrui o Gemini sobre como identificar arrematação
```

Se a calibração indica que o canal tem carimbo, o prompt já inclui:
```
Se houver selo/carimbo de "VENDIDO"/"ARREMATADO" visível, adicione ao JSON:
"carimbo_vendido": true
```

**Step 2: Marcar status de arrematação na consolidação**

Se o Gemini retornar `carimbo_vendido: true` em frames do lote, marcar como `arrematado` na consolidação (código já existente no `validar_lote` ou na consolidação).

**Step 3: Commit**

```bash
git add src/leilao_inteligente/pipeline/processor.py
git commit -m "refactor: remover Passada 4, carimbo detectado na calibração"
```

---

### Task 6: Remover formulário de processamento da UI

**Objetivo:** O processamento agora é sempre via chat com Claude. Remover apenas o formulário "Processar novo leilão" (input URL + botão). Manter a lista de leilões processados e o histórico de jobs.

**Files:**
- Modify: `dashboard/src/pages/leiloes.tsx` — remover seção "Processar novo leilão"

**Step 1: Remover formulário**

Em `leiloes.tsx`, remover o card de "Processar novo leilão" que contém:
- Input de URL
- Toggle Online/Batch
- Botão "Processar"

Manter:
- Histórico de processamentos (Concluído, Cancelado, etc.)
- Lista de leilões processados
- Botão "Limpar" do histórico

**Step 2: Commit**

```bash
git add dashboard/src/pages/leiloes.tsx
git commit -m "refactor: remover formulário de processamento (agora via Claude)"
```

---

### Task 7: Edição de leilões processados

**Objetivo:** Permitir editar titulo, canal, cidade, estado e data dos leilões processados. A edição repercute automaticamente em todos os endpoints (filtros, tendência, comparativo, ranking) porque todos leem direto do banco.

**Files:**
- Modify: `src/leilao_inteligente/api.py` — novo endpoint PATCH /api/leiloes/:id
- Modify: `dashboard/src/lib/api.ts` — tipo e função atualizarLeilao
- Modify: `dashboard/src/pages/leiloes.tsx` — campos editáveis inline na tabela

**Step 1: Endpoint PATCH no backend**

Em `api.py`:
```python
class LeilaoUpdate(BaseModel):
    titulo: str | None = None
    canal_youtube: str | None = None
    local_cidade: str | None = None
    local_estado: str | None = None
    data_leilao: str | None = None  # ISO format

@app.patch("/api/leiloes/{leilao_id}")
def patch_leilao(leilao_id: int, update: LeilaoUpdate):
    """Atualiza campos de um leilão processado."""
    session = get_session()
    try:
        leilao = session.query(Leilao).filter(Leilao.id == leilao_id).first()
        if not leilao:
            return JSONResponse({"error": "Leilão não encontrado"}, status_code=404)
        
        for campo, valor in update.model_dump(exclude_none=True).items():
            if campo == "data_leilao" and valor:
                setattr(leilao, campo, datetime.fromisoformat(valor))
            else:
                setattr(leilao, campo, valor)
        
        session.commit()
        return {"id": leilao.id, "ok": True}
    finally:
        session.close()
```

**Step 2: API client no frontend**

Em `api.ts`:
```typescript
atualizarLeilao: async (leilaoId: number, update: Partial<{
  titulo: string;
  canal_youtube: string;
  local_cidade: string;
  local_estado: string;
  data_leilao: string;
}>) => {
  const res = await fetch(`${API_URL}/api/leiloes/${leilaoId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json() as Promise<{ id: number; ok: boolean }>;
},
```

**Step 3: Campos editáveis na tabela de leilões**

Em `leiloes.tsx`, na tabela "Leilões processados":
- Cada célula (Título, Canal, Local, Data) é clicável
- Ao clicar, vira input editável (mesmo padrão do `EditableField` do dashboard)
- Ao sair do campo (blur) ou Enter, chama PATCH e invalida queries

**Propagação automática:**
Todos os endpoints (`/api/filtros`, `/api/metricas`, `/api/tendencia`, `/api/comparativo`, etc.) 
leem `Leilao.titulo`, `Leilao.local_cidade`, `Leilao.local_estado`, `Leilao.data_leilao` 
direto do banco. Após o PATCH, os filtros são invalidados no frontend via `queryClient.invalidateQueries()` 
e os dados atualizados aparecem imediatamente em todas as páginas.

**Step 4: Commit**

```bash
git add src/leilao_inteligente/api.py dashboard/src/lib/api.ts dashboard/src/pages/leiloes.tsx
git commit -m "feat: edição inline de leilões processados com propagação automática"
```

---

### Task 8: Teste end-to-end com vídeo real

**Objetivo:** Testar o fluxo completo com o vídeo de Nova Crixás que falhou (27 lotes).

**Protocolo de teste:**

1. **Amostrar**: `extrair_frames_amostrais(url)` → 20 frames
2. **Claude analisa**: olhar frames, identificar layout "LOTE XX" ao lado + "Rural YY" verde (ignorar)
3. **Gerar calibração**: prompt específico para Lance Transmissão
4. **Salvar**: `salvar_calibracao("LANCE TRANSMISSÃO", calibracao)`
5. **Processar**: rodar pipeline com prompt calibrado
6. **Comparar**: resultado deve ter significativamente mais que 27 lotes
7. **Validar**: verificar 10 lotes manualmente (links YouTube)

**Critério de sucesso:**
- Pipeline detecta ≥40 lotes (estimativa: ~54 para 3h de leilão)
- Nenhum lote com número "Rural XX" confundido como lote
- Carimbo de arrematação detectado corretamente (se existir)

---

## Resumo de arquivos

| Ação | Arquivo | Descrição |
|------|---------|-----------|
| CREATE | `pipeline/sampler.py` | Extração de frames do stream |
| CREATE | `pipeline/calibration.py` | Persistência de calibração |
| CREATE | `docs/FLUXO_PROCESSAMENTO.md` | Protocolo de processamento |
| MODIFY | `pipeline/vision.py` | Aceitar prompt parametrizado |
| MODIFY | `pipeline/processor.py` | Passar prompt calibrado, remover Passada 4 |
| MODIFY | `pages/leiloes.tsx` | Remover formulário, adicionar edição inline |
| MODIFY | `lib/api.ts` | Função atualizarLeilao |
| MODIFY | `api.py` | Endpoint PATCH /api/leiloes/:id |
| KEEP | `pipeline/stamp_profile.py` | Manter por ora (não quebrar imports) |

## Não mexer

- `pipeline/change_detector.py` — continua igual
- `pipeline/frame_extractor.py` — continua igual
- `pipeline/validator.py` — continua igual
- Consolidação de lotes — continua igual (prompt melhor = menos ruído na fonte)
- Endpoints `/api/processar` — mantém (Claude chama via curl)
- Sidebar e rotas — mantém "Leilões" e "Ao Vivo" como estão
