const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export interface Filtros {
  raca?: string;
  sexo?: string;
  idade_min?: number;
  idade_max?: number;
  estado?: string;
  cidade?: string;
  fazenda?: string;
  dias?: number;
  data_inicio?: string;
  data_fim?: string;
  status?: string;
  preco_min?: number;
  preco_max?: number;
  qtd_min?: number;
  qtd_max?: number;
  leilao_id?: number;
  condicao?: string;
  ordenar?: string;
}

export interface Metricas {
  media: number | null;
  minimo: number | null;
  maximo: number | null;
  total_lotes: number;
  total_cabecas: number;
  tendencia_percentual: number | null;
}

export interface Lote {
  id: number;
  leilao_id: number;
  leilao_titulo: string | null;
  leilao_data: string | null;
  lote_numero: string;
  quantidade: number;
  raca: string;
  sexo: string;
  condicao: string | null;
  idade_meses: number | null;
  pelagem: string | null;
  preco_inicial: number | null;
  preco_final: number | null;
  preco_por_cabeca: number | null;
  fazenda_vendedor: string | null;
  local_cidade: string | null;
  local_estado: string | null;
  timestamp_video_inicio: string | null;
  status: string;
  aparicoes: number;
  confianca_media: number;
  frame_paths: string[];
  youtube_url: string | null;
}

export interface FiltrosOpcoes {
  racas: string[];
  sexos: string[];
  estados: string[];
  cidades: string[];
  fazendas: string[];
  leiloes: { id: number; titulo: string }[];
  idades: number[];
}

export interface Fazenda {
  fazenda: string;
  media: number;
  lotes: number;
  cabecas: number;
}

export interface Regiao {
  estado: string;
  media: number;
  lotes: number;
}

export interface LeilaoResumo {
  id: number;
  titulo: string;
  canal: string;
  local_cidade: string | null;
  local_estado: string | null;
  total_lotes: number | null;
  processado_em: string | null;
  status: string;
}

export interface PontoTendencia {
  data: string;
  leilao: string;
  media: number;
  lotes: number;
}

function buildParams(filtros: Filtros): URLSearchParams {
  const params = new URLSearchParams();
  if (filtros.raca) params.set("raca", filtros.raca);
  if (filtros.sexo) params.set("sexo", filtros.sexo);
  if (filtros.idade_min !== undefined) params.set("idade_min", String(filtros.idade_min));
  if (filtros.idade_max !== undefined) params.set("idade_max", String(filtros.idade_max));
  if (filtros.estado) params.set("estado", filtros.estado);
  if (filtros.cidade) params.set("cidade", filtros.cidade);
  if (filtros.fazenda) params.set("fazenda", filtros.fazenda);
  if (filtros.dias) params.set("dias", String(filtros.dias));
  if (filtros.data_inicio) params.set("data_inicio", filtros.data_inicio);
  if (filtros.data_fim) params.set("data_fim", filtros.data_fim);
  if (filtros.status) params.set("status", filtros.status);
  if (filtros.preco_min !== undefined) params.set("preco_min", String(filtros.preco_min));
  if (filtros.preco_max !== undefined) params.set("preco_max", String(filtros.preco_max));
  if (filtros.qtd_min !== undefined) params.set("qtd_min", String(filtros.qtd_min));
  if (filtros.qtd_max !== undefined) params.set("qtd_max", String(filtros.qtd_max));
  if (filtros.leilao_id !== undefined) params.set("leilao_id", String(filtros.leilao_id));
  if (filtros.condicao) params.set("condicao", filtros.condicao);
  if (filtros.ordenar) params.set("ordenar", filtros.ordenar);
  return params;
}

async function fetchJson<T>(path: string, params?: URLSearchParams): Promise<T> {
  const url = params ? `${API_URL}${path}?${params}` : `${API_URL}${path}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export interface ComparativoCategoria {
  raca: string;
  sexo: string;
  condicao: string | null;
  faixa_idade: string;
  media_a: number | null;
  media_b: number | null;
  diff: number | null;
  diff_pct: number | null;
  lotes_a: number;
  lotes_b: number;
}

export interface ComparativoCidades {
  cidade_a: string;
  cidade_b: string;
  categorias: ComparativoCategoria[];
}

export interface PontoEvolucao {
  data: string;
  leilao: string;
  media: number;
  minimo: number;
  maximo: number;
  lotes: number;
}

function buildSimpleParams(obj: Record<string, string | number | undefined | null>): URLSearchParams {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(obj)) {
    if (v != null && v !== "") params.set(k, String(v));
  }
  return params;
}

export const api = {
  filtros: () => fetchJson<FiltrosOpcoes>("/api/filtros"),
  metricas: (f: Filtros) => fetchJson<Metricas>("/api/metricas", buildParams(f)),
  lotes: (f: Filtros) => fetchJson<Lote[]>("/api/lotes", buildParams(f)),
  tendencia: (f: Filtros) => fetchJson<PontoTendencia[]>("/api/tendencia", buildParams(f)),
  fazendas: (f: Filtros) => fetchJson<Fazenda[]>("/api/fazendas", buildParams(f)),
  regioes: (f: Filtros) => fetchJson<Regiao[]>("/api/regioes", buildParams(f)),
  leiloes: () => fetchJson<LeilaoResumo[]>("/api/leiloes"),
  comparativoCidades: (p: { cidade_a: string; cidade_b: string; raca?: string; sexo?: string; condicao?: string; dias?: number }) =>
    fetchJson<ComparativoCidades>("/api/comparativo/cidades", buildSimpleParams(p)),
  comparativoEvolucao: (p: { cidade: string; raca?: string; sexo?: string; condicao?: string; idade_min?: number; idade_max?: number; dias?: number }) =>
    fetchJson<PontoEvolucao[]>("/api/comparativo/evolucao", buildSimpleParams(p)),
  frameUrl: (path: string) => `${API_URL}/api/frame/${path}`,
};
