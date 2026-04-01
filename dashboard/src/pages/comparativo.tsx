import { Fragment, useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import { Check, X, Scale, ChevronDown, ChevronRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, type ComparativoCategoria } from "@/lib/api";
import { formatBRL, formatLeilaoCompleto, formatLeilao, formatCidade } from "@/lib/format";
import { useCustos } from "@/hooks/use-custos";

function categoriaLabel(c: ComparativoCategoria): string {
  const sexo = c.sexo === "macho" ? "M" : c.sexo === "femea" ? "F" : "Mx";
  const cond = c.condicao ? ` ${c.condicao}` : "";
  return `${c.raca} ${sexo}${cond} ${c.idade_meses}m`;
}

interface SelectedLote {
  id: number;
  lote_numero: string;
  quantidade: number;
  preco_final: number | null;
  fazenda_vendedor: string | null;
  status: string;
  youtube_url: string | null;
  leilao_label: string;
}

function toEmbedUrl(url: string): string {
  const match = url.match(/[?&]v=([^&]+)/);
  const videoId = match?.[1] ?? "";
  const tMatch = url.match(/[?&]t=(\d+)/);
  const t = tMatch?.[1] ?? "0";
  return `https://www.youtube.com/embed/${videoId}?start=${t}&autoplay=1`;
}

function LoteItem({
  lote,
  leilaoLabel: label,
  isActive,
  onSelect,
}: {
  lote: { lote_numero: string; quantidade: number; preco_final: number | null; fazenda_vendedor: string | null; status: string; youtube_url: string | null };
  leilaoLabel: string;
  isActive: boolean;
  onSelect: (l: SelectedLote | null) => void;
}) {
  return (
    <div className={`flex items-center justify-between text-xs rounded px-2 py-1 bg-background ${isActive ? "ring-1 ring-blue-500" : ""}`}>
      <div>
        <span className="font-medium">Lote {lote.lote_numero}</span>
        <span className="text-muted-foreground ml-1.5">{lote.quantidade} cab</span>
        {lote.fazenda_vendedor && <span className="text-muted-foreground ml-1.5">· {lote.fazenda_vendedor}</span>}
      </div>
      <div className="flex items-center gap-1.5">
        <span className={`text-[9px] px-1 rounded ${
          lote.status === "arrematado" ? "bg-green-500/10 text-green-600" :
          lote.status === "repescagem" ? "bg-yellow-500/10 text-yellow-600" :
          "bg-muted text-muted-foreground"
        }`}>
          {lote.status === "arrematado" ? "Arrematado" : lote.status === "repescagem" ? "Repescagem" : "Sem Disputa"}
        </span>
        <span className="font-semibold">{formatBRL(lote.preco_final)}</span>
        {lote.youtube_url && (
          <button
            className={`ml-1 p-0.5 rounded hover:bg-blue-500/20 transition-colors ${isActive ? "text-blue-500 bg-blue-500/10" : "text-muted-foreground hover:text-blue-500"}`}
            onClick={(e) => { e.stopPropagation(); onSelect(isActive ? null : { ...lote, leilao_label: label }); }}
            title="Ver no vídeo"
          >
            <span className="text-[11px]">&#9654;</span>
          </button>
        )}
      </div>
    </div>
  );
}

function ExpandedLotes({
  leilaoIdA, leilaoIdB, labelA, labelB, raca, sexo, idadeMeses, condicao, selectedLote, onSelectLote,
}: {
  leilaoIdA: number; leilaoIdB: number; labelA: string; labelB: string;
  raca: string; sexo: string; idadeMeses: number; condicao: string | null;
  selectedLote: SelectedLote | null; onSelectLote: (l: SelectedLote | null) => void;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["comparativo-lotes", leilaoIdA, leilaoIdB, raca, sexo, idadeMeses, condicao],
    queryFn: () => api.comparativoLotes({ leilao_id_a: leilaoIdA, leilao_id_b: leilaoIdB, raca, sexo, idade_meses: idadeMeses, condicao: condicao || undefined }),
  });

  if (isLoading) return <div className="p-3 text-xs text-muted-foreground">Carregando lotes...</div>;

  const lotesA = data?.lotes_a ?? [];
  const lotesB = data?.lotes_b ?? [];

  return (
    <div className="bg-muted/30 px-4 py-3">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <p className="text-[10px] font-medium text-blue-500 mb-1.5">{labelA} ({lotesA.length} lotes)</p>
          <div className="space-y-1">
            {lotesA.map((l, i) => (
              <LoteItem key={i} lote={l} leilaoLabel={labelA} isActive={selectedLote?.lote_numero === l.lote_numero && selectedLote?.leilao_label === labelA} onSelect={onSelectLote} />
            ))}
          </div>
        </div>
        <div>
          <p className="text-[10px] font-medium text-green-500 mb-1.5">{labelB} ({lotesB.length} lotes)</p>
          <div className="space-y-1">
            {lotesB.map((l, i) => (
              <LoteItem key={i} lote={l} leilaoLabel={labelB} isActive={selectedLote?.lote_numero === l.lote_numero && selectedLote?.leilao_label === labelB} onSelect={onSelectLote} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export function ComparativoPage() {
  // Funil: Período → Estado → Cidade → Leilão → Detalhes
  const [dataInicio, setDataInicio] = useState<string>("");
  const [dataFim, setDataFim] = useState<string>("");
  const [estado, setEstado] = useState<string>("");
  const [cidade, setCidade] = useState<string>("");
  const [leilaoA, setLeilaoA] = useState<string>("");
  const [leilaoB, setLeilaoB] = useState<string>("");
  const [raca, setRaca] = useState<string>("");
  const [sexo, setSexo] = useState<string>("");
  const [condicao, setCondicao] = useState<string>("");
  const [idadeMin, setIdadeMin] = useState<string>("");
  const [idadeMax, setIdadeMax] = useState<string>("");
  const [precoMin, setPrecoMin] = useState<string>("");
  const [precoMax, setPrecoMax] = useState<string>("");
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [selectedLote, setSelectedLote] = useState<SelectedLote | null>(null);

  const queryClient = useQueryClient();
  const { custos, setCusto, calcularLucro } = useCustos();

  const { data: opcoes } = useQuery({
    queryKey: ["filtros"],
    queryFn: () => api.filtros(),
    staleTime: 60_000,
  });

  // Funil de filtragem: período → estado → cidade → leilões
  const leiloesFiltrados = (opcoes?.leiloes ?? []).filter((l) => {
    if (l.data) {
      const d = l.data.slice(0, 10);
      if (dataInicio && d < dataInicio) return false;
      if (dataFim && d > dataFim) return false;
    }
    if (estado && estado !== "Todos" && l.local_estado !== estado) return false;
    if (cidade && cidade !== "Todas" && l.local_cidade !== cidade) return false;
    return true;
  });

  // Cidades disponíveis (filtradas por estado e período)
  const cidadesDisponiveis = [...new Set(
    leiloesFiltrados
      .map((l) => l.local_cidade)
      .filter((c): c is string => !!c)
  )].sort();

  // Limpar seleções quando filtros superiores mudam
  const leiloesNomes = new Set(leiloesFiltrados.map((l) => formatLeilaoCompleto(l.titulo, l.local_cidade, l.local_estado, l.data)));
  useEffect(() => {
    if (leilaoA && !leiloesNomes.has(leilaoA)) setLeilaoA("");
    if (leilaoB && !leiloesNomes.has(leilaoB)) setLeilaoB("");
  }, [dataInicio, dataFim, estado, cidade]); // eslint-disable-line react-hooks/exhaustive-deps

  // Limpar cidade se estado mudou e cidade não pertence mais
  useEffect(() => {
    if (cidade && cidade !== "Todas" && !cidadesDisponiveis.includes(cidade)) setCidade("");
  }, [estado]); // eslint-disable-line react-hooks/exhaustive-deps

  // Mapa de nome formatado → id para lookup
  const leilaoMap = new Map(
    (opcoes?.leiloes ?? []).map((l) => [
      formatLeilaoCompleto(l.titulo, l.local_cidade, l.local_estado, l.data),
      l.id,
    ])
  );
  const leilaoIdA = leilaoA ? leilaoMap.get(leilaoA) : undefined;
  const leilaoIdB = leilaoB ? leilaoMap.get(leilaoB) : undefined;

  const { data, isLoading } = useQuery({
    queryKey: ["comparativo", leilaoA, leilaoB, raca, sexo, condicao, estado, idadeMin, idadeMax, precoMin, precoMax],
    queryFn: () =>
      api.comparativoCidades({
        leilao_id_a: leilaoIdA,
        leilao_id_b: leilaoIdB,
        raca: raca && raca !== "Todas" ? raca : undefined,
        sexo: sexo && sexo !== "Todos" ? sexo.toLowerCase().replace("ê", "e") : undefined,
        condicao: condicao && condicao !== "Todas" ? condicao.toLowerCase() : undefined,
        estado: estado && estado !== "Todos" ? estado : undefined,
        idade_min: idadeMin ? Number(idadeMin) : undefined,
        idade_max: idadeMax ? Number(idadeMax) : undefined,
        preco_min: precoMin ? Number(precoMin) : undefined,
        preco_max: precoMax ? Number(precoMax) : undefined,
      }),
    enabled: !!leilaoIdA && !!leilaoIdB && leilaoIdA !== leilaoIdB,
  });

  const labelA = data?.label_a ? formatLeilao(data.label_a) : "A";
  const labelB = data?.label_b ? formatLeilao(data.label_b) : "B";

  const categorias = data?.categorias ?? [];
  const comDados = categorias.filter((c) => c.media_a != null && c.media_b != null);

  const chartData = comDados.map((c) => ({
    name: categoriaLabel(c),
    [labelA]: c.media_a,
    [labelB]: c.media_b,
  }));

  const melhorOportunidade = comDados.length > 0
    ? comDados.reduce((best, c) => {
        const lucro = c.media_a != null && c.media_b != null ? calcularLucro(c.media_a, c.media_b) : -Infinity;
        const melhorLucro = best.media_a != null && best.media_b != null ? calcularLucro(best.media_a, best.media_b) : -Infinity;
        return lucro > melhorLucro ? c : best;
      })
    : null;

  const spreadMedio = comDados.length > 0
    ? comDados.reduce((sum, c) => sum + (c.diff ?? 0), 0) / comDados.length
    : 0;

  return (
    <div className="flex gap-4">
      <div className={`space-y-4 ${selectedLote ? "flex-1 min-w-0" : "w-full"}`}>
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Comparativo</h1>
        <p className="text-sm text-muted-foreground">
          Compare preços entre leilões e analise oportunidades de arbitragem
        </p>
      </div>

      {/* Linha 1: Período → Estado → Cidade */}
      <div className="flex gap-3 flex-wrap items-end">
        <div className="space-y-1">
          <label className="text-[10px] font-medium text-muted-foreground">Período</label>
          <div className="flex gap-1.5 items-center">
            <Input
              type="date"
              value={dataInicio}
              onChange={(e) => setDataInicio(e.target.value)}
              className="w-[130px] h-8 text-xs"
            />
            <span className="text-xs text-muted-foreground">a</span>
            <Input
              type="date"
              value={dataFim}
              onChange={(e) => setDataFim(e.target.value)}
              className="w-[130px] h-8 text-xs"
            />
          </div>
        </div>

        <div className="space-y-1">
          <label className="text-[10px] font-medium text-muted-foreground">Estado</label>
          <Select value={estado || "Todos"} onValueChange={(v) => setEstado(v === "Todos" ? "" : v)}>
            <SelectTrigger className="w-[90px] h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="Todos">Todos</SelectItem>
              {opcoes?.estados.map((e) => (
                <SelectItem key={e} value={e}>{e}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <label className="text-[10px] font-medium text-muted-foreground">Cidade</label>
          <Select value={cidade || "Todas"} onValueChange={(v) => setCidade(v === "Todas" ? "" : v)}>
            <SelectTrigger className="w-[140px] h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="Todas">Todas</SelectItem>
              {cidadesDisponiveis.map((c) => (
                <SelectItem key={c} value={c}>{formatCidade(c)}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Linha 2: Leilão A → Leilão B */}
      <div className="flex gap-3 flex-wrap items-end">
        <div className="space-y-1">
          <label className="text-[10px] font-medium text-muted-foreground">Leilão A (Compra)</label>
          <Select value={leilaoA} onValueChange={setLeilaoA}>
            <SelectTrigger className="w-[320px] h-8 text-xs">
              <SelectValue placeholder="Selecione o leilão..." />
            </SelectTrigger>
            <SelectContent className="max-w-[400px]">
              {leiloesFiltrados.map((l) => {
                const label = formatLeilaoCompleto(l.titulo, l.local_cidade, l.local_estado, l.data);
                return (
                  <SelectItem key={l.id} value={label} className="text-xs">
                    {label}
                  </SelectItem>
                );
              })}
              {leiloesFiltrados.length === 0 && (
                <div className="px-2 py-4 text-xs text-muted-foreground text-center">
                  Nenhum leilão encontrado
                </div>
              )}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <label className="text-[10px] font-medium text-muted-foreground">Leilão B (Venda)</label>
          <Select value={leilaoB} onValueChange={setLeilaoB}>
            <SelectTrigger className="w-[320px] h-8 text-xs">
              <SelectValue placeholder="Selecione o leilão..." />
            </SelectTrigger>
            <SelectContent className="max-w-[400px]">
              {leiloesFiltrados.map((l) => {
                const label = formatLeilaoCompleto(l.titulo, l.local_cidade, l.local_estado, l.data);
                return (
                  <SelectItem key={l.id} value={label} className="text-xs">
                    {label}
                  </SelectItem>
                );
              })}
              {leiloesFiltrados.length === 0 && (
                <div className="px-2 py-4 text-xs text-muted-foreground text-center">
                  Nenhum leilão encontrado
                </div>
              )}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Linha 3: Raça → Sexo → Condição → Idade → Preço */}
      <div className="flex gap-3 flex-wrap items-end">
        <div className="space-y-1">
          <label className="text-[10px] font-medium text-muted-foreground">Raça</label>
          <Select value={raca || "Todas"} onValueChange={(v) => setRaca(v === "Todas" ? "" : v)}>
            <SelectTrigger className="w-[120px] h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="Todas">Todas</SelectItem>
              {opcoes?.racas.map((r) => (
                <SelectItem key={r} value={r}>{r}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <label className="text-[10px] font-medium text-muted-foreground">Sexo</label>
          <Select value={sexo || "Todos"} onValueChange={(v) => setSexo(v === "Todos" ? "" : v)}>
            <SelectTrigger className="w-[100px] h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="Todos">Todos</SelectItem>
              <SelectItem value="Macho">Macho</SelectItem>
              <SelectItem value="Fêmea">Fêmea</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <label className="text-[10px] font-medium text-muted-foreground">Condição</label>
          <Select value={condicao || "Todas"} onValueChange={(v) => setCondicao(v === "Todas" ? "" : v)}>
            <SelectTrigger className="w-[110px] h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="Todas">Todas</SelectItem>
              <SelectItem value="Parida">Parida</SelectItem>
              <SelectItem value="Prenhe">Prenhe</SelectItem>
              <SelectItem value="Solteira">Solteira</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <label className="text-[10px] font-medium text-muted-foreground">Idade (meses)</label>
          <div className="flex items-center gap-1">
            <Input
              type="number"
              placeholder="min"
              value={idadeMin}
              onChange={(e) => setIdadeMin(e.target.value)}
              className="w-[70px] h-8 text-xs"
            />
            <span className="text-[10px] text-muted-foreground">a</span>
            <Input
              type="number"
              placeholder="max"
              value={idadeMax}
              onChange={(e) => setIdadeMax(e.target.value)}
              className="w-[70px] h-8 text-xs"
            />
          </div>
        </div>

        <div className="space-y-1">
          <label className="text-[10px] font-medium text-muted-foreground">Preço (R$)</label>
          <div className="flex items-center gap-1">
            <Input
              type="number"
              placeholder="min"
              value={precoMin}
              onChange={(e) => setPrecoMin(e.target.value)}
              className="w-[70px] h-8 text-xs"
            />
            <span className="text-[10px] text-muted-foreground">a</span>
            <Input
              type="number"
              placeholder="max"
              value={precoMax}
              onChange={(e) => setPrecoMax(e.target.value)}
              className="w-[70px] h-8 text-xs"
            />
          </div>
        </div>
      </div>

      {!leilaoIdA || !leilaoIdB || leilaoIdA === leilaoIdB ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-20 text-muted-foreground">
            <Scale className="h-12 w-12 mb-4 opacity-30" />
            <p className="text-lg font-medium">Selecione dois leilões diferentes</p>
            <p className="text-sm mt-1">Escolha o leilão de compra e o de venda para comparar</p>
          </CardContent>
        </Card>
      ) : isLoading ? (
        <Card>
          <CardContent className="flex items-center justify-center py-20 text-muted-foreground">
            Carregando comparativo...
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Cards resumo */}
          <div className="grid grid-cols-3 gap-2">
            <Card className="py-2">
              <CardContent className="px-3">
                <p className="text-[10px] text-muted-foreground">Melhor Oportunidade</p>
                {melhorOportunidade && melhorOportunidade.media_a && melhorOportunidade.media_b ? (
                  <>
                    <p className="text-sm font-bold">{categoriaLabel(melhorOportunidade)}</p>
                    <p className="text-xs text-green-500">
                      Lucro: {formatBRL(calcularLucro(melhorOportunidade.media_a, melhorOportunidade.media_b))}/cab
                    </p>
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">—</p>
                )}
              </CardContent>
            </Card>

            <Card className="py-2">
              <CardContent className="px-3">
                <p className="text-[10px] text-muted-foreground">Spread Médio</p>
                <p className={`text-sm font-bold ${spreadMedio >= 0 ? "text-green-500" : "text-red-500"}`}>
                  {formatBRL(spreadMedio)}
                </p>
                <p className="text-[10px] text-muted-foreground">{labelB} vs {labelA}</p>
              </CardContent>
            </Card>

            <Card className="py-2">
              <CardContent className="px-3">
                <p className="text-[10px] text-muted-foreground">Categorias Comparadas</p>
                <p className="text-sm font-bold">{comDados.length}</p>
                <p className="text-[10px] text-muted-foreground">de {categorias.length} total</p>
              </CardContent>
            </Card>
          </div>

          {/* Gráfico de barras agrupadas */}
          {chartData.length > 0 && (
            <Card>
              <CardContent className="pt-3 pb-2 px-3">
                <p className="text-[11px] font-medium text-muted-foreground mb-2">Preço médio por categoria</p>
                <ResponsiveContainer width="100%" height={Math.max(250, chartData.length * 35)}>
                  <BarChart data={chartData} layout="vertical" margin={{ left: 120 }}>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                    <XAxis
                      type="number"
                      tickFormatter={(v: number) => `R$${(v / 1000).toFixed(1)}k`}
                      className="text-[10px]"
                    />
                    <YAxis type="category" dataKey="name" className="text-[10px]" width={120} />
                    <Tooltip
                      formatter={(v: number) => formatBRL(v)}
                      contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: "8px", fontSize: "12px" }}
                    />
                    <Legend wrapperStyle={{ fontSize: "11px" }} />
                    <Bar dataKey={labelA} fill="#3b82f6" radius={[0, 4, 4, 0]} name={labelA} />
                    <Bar dataKey={labelB} fill="#22c55e" radius={[0, 4, 4, 0]} name={labelB} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {/* Custos + Tabela de arbitragem */}
          <Card>
            <CardContent className="pt-3 px-3">
              <div className="flex items-center justify-between mb-3">
                <p className="text-[11px] font-medium text-muted-foreground">Análise de Arbitragem</p>
                <div className="flex gap-3 items-center">
                  <div className="flex items-center gap-1.5">
                    <label className="text-[10px] text-muted-foreground">Frete (R$/cab)</label>
                    <Input
                      type="number"
                      value={custos.frete}
                      onChange={(e) => setCusto("frete", Number(e.target.value))}
                      className="w-[70px] h-7 text-xs"
                    />
                  </div>
                  <div className="flex items-center gap-1.5">
                    <label className="text-[10px] text-muted-foreground">Comissão (%)</label>
                    <Input
                      type="number"
                      value={custos.comissao}
                      onChange={(e) => setCusto("comissao", Number(e.target.value))}
                      className="w-[60px] h-7 text-xs"
                    />
                  </div>
                  <div className="flex items-center gap-1.5">
                    <label className="text-[10px] text-muted-foreground">Outros (R$)</label>
                    <Input
                      type="number"
                      value={custos.outros}
                      onChange={(e) => setCusto("outros", Number(e.target.value))}
                      className="w-[70px] h-7 text-xs"
                    />
                  </div>
                </div>
              </div>

              <Table className="text-xs">
                <TableHeader>
                  <TableRow className="text-[11px]">
                    <TableHead className="px-2">Categoria</TableHead>
                    <TableHead className="px-2">Idade</TableHead>
                    <TableHead className="px-2 text-right">{labelA}</TableHead>
                    <TableHead className="px-2 text-right">{labelB}</TableHead>
                    <TableHead className="px-2 text-right">Spread</TableHead>
                    <TableHead className="px-2 text-right">Custos</TableHead>
                    <TableHead className="px-2 text-right">Lucro/cab</TableHead>
                    <TableHead className="px-2 text-center w-16">Viável?</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {comDados.map((c, i) => {
                    const lucro = c.media_a != null && c.media_b != null
                      ? calcularLucro(c.media_a, c.media_b)
                      : null;
                    const custoTotal = c.media_a != null
                      ? custos.frete + (c.media_a * custos.comissao / 100) + custos.outros
                      : null;
                    const sexoLabel = c.sexo === "macho" ? "M" : c.sexo === "femea" ? "F" : "Mx";
                    const condLabel = c.condicao ? ` ${c.condicao}` : "";
                    const rowKey = `${c.raca}-${c.sexo}-${c.condicao || ""}-${c.idade_meses}`;
                    const isExpanded = expandedRow === rowKey;

                    return (
                      <Fragment key={i}>
                        <TableRow
                          className="cursor-pointer hover:bg-muted/50"
                          onClick={() => setExpandedRow(isExpanded ? null : rowKey)}
                        >
                          <TableCell className="px-2 font-medium">
                            <span className="inline-flex items-center gap-1">
                              {isExpanded
                                ? <ChevronDown className="h-3 w-3 text-muted-foreground" />
                                : <ChevronRight className="h-3 w-3 text-muted-foreground" />
                              }
                              {c.raca} {sexoLabel}{condLabel}
                              <span className="text-[10px] text-muted-foreground">
                                ({c.lotes_a}+{c.lotes_b} lotes)
                              </span>
                            </span>
                          </TableCell>
                          <TableCell className="px-2">{c.idade_meses}m</TableCell>
                          <TableCell className="px-2 text-right">
                            {c.media_a != null ? formatBRL(c.media_a) : <span className="text-muted-foreground">—</span>}
                          </TableCell>
                          <TableCell className="px-2 text-right">
                            {c.media_b != null ? formatBRL(c.media_b) : <span className="text-muted-foreground">—</span>}
                          </TableCell>
                          <TableCell className={`px-2 text-right font-semibold ${
                            c.diff != null ? (c.diff >= 0 ? "text-green-500" : "text-red-500") : ""
                          }`}>
                            {c.diff != null ? `${c.diff >= 0 ? "+" : ""}${formatBRL(c.diff)}` : "—"}
                            {c.diff_pct != null && (
                              <span className="text-[10px] ml-1">({c.diff_pct > 0 ? "+" : ""}{c.diff_pct}%)</span>
                            )}
                          </TableCell>
                          <TableCell className="px-2 text-right text-muted-foreground">
                            {custoTotal != null ? formatBRL(custoTotal) : "—"}
                          </TableCell>
                          <TableCell className={`px-2 text-right font-bold ${
                            lucro != null ? (lucro >= 0 ? "text-green-500" : "text-red-500") : ""
                          }`}>
                            {lucro != null ? formatBRL(lucro) : "—"}
                          </TableCell>
                          <TableCell className="px-2 text-center">
                            {lucro != null ? (
                              lucro >= 0
                                ? <Check className="h-4 w-4 text-green-500 mx-auto" />
                                : <X className="h-4 w-4 text-red-500 mx-auto" />
                            ) : (
                              <span className="text-muted-foreground">—</span>
                            )}
                          </TableCell>
                        </TableRow>
                        {isExpanded && leilaoIdA && leilaoIdB && (
                          <TableRow>
                            <TableCell colSpan={8} className="p-0">
                              <ExpandedLotes
                                leilaoIdA={leilaoIdA}
                                leilaoIdB={leilaoIdB}
                                labelA={labelA}
                                labelB={labelB}
                                raca={c.raca}
                                sexo={c.sexo}
                                idadeMeses={c.idade_meses}
                                condicao={c.condicao}
                                selectedLote={selectedLote}
                                onSelectLote={setSelectedLote}
                              />
                            </TableCell>
                          </TableRow>
                        )}
                      </Fragment>
                    );
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
      </div>

      {/* Painel lateral direito — igual Dashboard */}
      {selectedLote && selectedLote.youtube_url && (
        <div className="w-[35%] shrink-0 sticky top-4 self-start space-y-3 p-1 overflow-y-auto max-h-[calc(100vh-2rem)]">
          <Card>
            <CardContent className="p-2">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-bold">Lote {selectedLote.lote_numero}</p>
                <button onClick={() => setSelectedLote(null)} className="p-0.5 rounded hover:bg-muted transition-colors">
                  <X className="h-4 w-4 text-muted-foreground" />
                </button>
              </div>
              <div className="rounded-lg overflow-hidden">
                <iframe
                  src={toEmbedUrl(selectedLote.youtube_url)}
                  className="w-full aspect-video"
                  allow="autoplay; encrypted-media"
                  allowFullScreen
                />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-3 space-y-2">
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <p className="text-[10px] text-muted-foreground">Leilão</p>
                  <p className="font-medium">{selectedLote.leilao_label}</p>
                </div>
                <div>
                  <p className="text-[10px] text-muted-foreground">Quantidade</p>
                  <p className="font-medium">{selectedLote.quantidade} cabeças</p>
                </div>
                <div>
                  <p className="text-[10px] text-muted-foreground">Preço Final</p>
                  <p className="font-bold text-sm">{formatBRL(selectedLote.preco_final)}</p>
                </div>
                <div>
                  <p className="text-[10px] text-muted-foreground">Status</p>
                  <Select
                    value={selectedLote.status === "arrematado" ? "Arrematado" : selectedLote.status === "repescagem" ? "Repescagem" : "Sem Disputa"}
                    onValueChange={async (v) => {
                      const newStatus = v === "Arrematado" ? "arrematado" : v === "Repescagem" ? "repescagem" : "incerto";
                      await api.atualizarLote(selectedLote.id, { status: newStatus });
                      setSelectedLote({ ...selectedLote, status: newStatus });
                      queryClient.invalidateQueries({ queryKey: ["comparativo-lotes"] });
                    }}
                  >
                    <SelectTrigger className="h-7 text-[10px] w-[120px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Arrematado">Arrematado</SelectItem>
                      <SelectItem value="Sem Disputa">Sem Disputa</SelectItem>
                      <SelectItem value="Repescagem">Repescagem</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {selectedLote.fazenda_vendedor && (
                  <div className="col-span-2">
                    <p className="text-[10px] text-muted-foreground">Fazenda</p>
                    <p className="font-medium">{selectedLote.fazenda_vendedor}</p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
