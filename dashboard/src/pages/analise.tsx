import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api, type Filtros } from "@/lib/api";
import { formatBRL, formatFazenda } from "@/lib/format";

const COLORS = ["#22c55e", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16"];

export function AnalisePage() {
  const [filtros, setFiltros] = useState<Filtros>({ dias: 90 });

  const setFiltro = (key: keyof Filtros, value: string | number | undefined) => {
    setFiltros((prev) => ({ ...prev, [key]: value }));
  };

  const { data: opcoes } = useQuery({
    queryKey: ["filtros"],
    queryFn: () => api.filtros(),
    staleTime: 60_000,
  });

  const { data: tendencia = [] } = useQuery({
    queryKey: ["tendencia", filtros],
    queryFn: () => api.tendencia(filtros),
  });

  const { data: fazendas = [] } = useQuery({
    queryKey: ["fazendas", filtros],
    queryFn: () => api.fazendas(filtros),
  });

  const { data: regioes = [] } = useQuery({
    queryKey: ["regioes", filtros],
    queryFn: () => api.regioes(filtros),
  });

  const { data: lotes = [] } = useQuery({
    queryKey: ["lotes-analise", filtros],
    queryFn: () => api.lotes(filtros),
  });

  // Distribuição por raça e sexo
  const racas: Record<string, number> = {};
  const sexos: Record<string, number> = {};
  for (const l of lotes) {
    racas[l.raca] = (racas[l.raca] || 0) + 1;
    sexos[l.sexo] = (sexos[l.sexo] || 0) + 1;
  }
  const racaData = Object.entries(racas)
    .map(([raca, count]) => ({ raca, count }))
    .sort((a, b) => b.count - a.count);
  const sexoData = Object.entries(sexos)
    .map(([sexo, count]) => ({ sexo: sexo === "macho" ? "Macho" : sexo === "femea" ? "Fêmea" : "Misto", count }))
    .sort((a, b) => b.count - a.count);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Análise</h1>
        <p className="text-sm text-muted-foreground">
          Gráficos detalhados e comparativos
        </p>
      </div>

      {/* Filtros */}
      <div className="flex gap-3 flex-wrap items-end">
        <div className="space-y-1">
          <label className="text-[10px] font-medium text-muted-foreground">Período</label>
          <Select
            value={String(filtros.dias ?? 90)}
            onValueChange={(v) => setFiltro("dias", Number(v))}
          >
            <SelectTrigger className="w-[110px] h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="30">30 dias</SelectItem>
              <SelectItem value="60">60 dias</SelectItem>
              <SelectItem value="90">90 dias</SelectItem>
              <SelectItem value="180">6 meses</SelectItem>
              <SelectItem value="365">1 ano</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <label className="text-[10px] font-medium text-muted-foreground">Raça</label>
          <Select
            value={filtros.raca || "Todas"}
            onValueChange={(v) => setFiltro("raca", v === "Todas" ? undefined : v)}
          >
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
          <Select
            value={filtros.sexo === "macho" ? "Macho" : filtros.sexo === "femea" ? "Fêmea" : "Todos"}
            onValueChange={(v) => setFiltro("sexo", v === "Todos" ? undefined : v.toLowerCase().replace("ê", "e"))}
          >
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
          <Select
            value={filtros.condicao ? filtros.condicao.charAt(0).toUpperCase() + filtros.condicao.slice(1) : "Todas"}
            onValueChange={(v) => setFiltro("condicao", v === "Todas" ? undefined : v.toLowerCase())}
          >
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
          <label className="text-[10px] font-medium text-muted-foreground">Estado</label>
          <Select
            value={filtros.estado || "Todos"}
            onValueChange={(v) => setFiltro("estado", v === "Todos" ? undefined : v)}
          >
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
          <label className="text-[10px] font-medium text-muted-foreground">Idade (meses)</label>
          <div className="flex items-center gap-1">
          <Input
            type="number"
            placeholder="min"
            value={filtros.idade_min ?? ""}
            onChange={(e) => setFiltro("idade_min", e.target.value ? Number(e.target.value) : undefined)}
            className="w-[70px] h-8 text-xs"
          />
          <span className="text-[10px] text-muted-foreground">a</span>
          <Input
            type="number"
            placeholder="max"
            value={filtros.idade_max ?? ""}
            onChange={(e) => setFiltro("idade_max", e.target.value ? Number(e.target.value) : undefined)}
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
            value={filtros.preco_min ?? ""}
            onChange={(e) => setFiltro("preco_min", e.target.value ? Number(e.target.value) : undefined)}
            className="w-[70px] h-8 text-xs"
          />
          <span className="text-[10px] text-muted-foreground">a</span>
          <Input
            type="number"
            placeholder="max"
            value={filtros.preco_max ?? ""}
            onChange={(e) => setFiltro("preco_max", e.target.value ? Number(e.target.value) : undefined)}
            className="w-[70px] h-8 text-xs"
          />
          </div>
        </div>
      </div>

      {/* Tendencia */}
      <Card>
        <CardHeader className="py-3">
          <CardTitle className="text-sm font-medium">Tendência de preço por leilão</CardTitle>
        </CardHeader>
        <CardContent>
          {tendencia.length === 0 ? (
            <div className="flex items-center justify-center h-[250px] text-muted-foreground">
              Processe mais leilões para ver a tendência
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={tendencia.map((d) => ({
                ...d,
                dataFmt: d.data ? new Date(d.data).toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }) : "",
              }))}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis dataKey="dataFmt" className="text-xs" />
                <YAxis tickFormatter={(v: number) => `R$${(v / 1000).toFixed(1)}k`} className="text-xs" />
                <Tooltip formatter={(v: number) => formatBRL(v)} contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: "8px" }} />
                <Line type="monotone" dataKey="media" stroke="hsl(142, 71%, 45%)" strokeWidth={2} dot={{ r: 5, fill: "hsl(142, 71%, 45%)" }} name="Média" connectNulls />
              </LineChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Fazendas */}
        <Card>
          <CardHeader className="py-3">
            <CardTitle className="text-sm font-medium">Preço médio por fazenda (top 10)</CardTitle>
          </CardHeader>
          <CardContent>
            {fazendas.length === 0 ? (
              <div className="flex items-center justify-center h-[250px] text-muted-foreground">Sem dados</div>
            ) : (
              <ResponsiveContainer width="100%" height={350}>
                <BarChart
                  data={fazendas.slice(0, 10).map((f) => ({ ...f, fazenda: formatFazenda(f.fazenda) }))}
                  layout="vertical"
                  margin={{ left: 10 }}
                >
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis type="number" tickFormatter={(v: number) => `R$${(v / 1000).toFixed(1)}k`} className="text-xs" />
                  <YAxis type="category" dataKey="fazenda" width={180} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={(v: number) => formatBRL(v)} contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: "8px" }} />
                  <Bar dataKey="media" fill="hsl(142, 71%, 45%)" radius={[0, 4, 4, 0]} name="Média" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Regioes */}
        <Card>
          <CardHeader className="py-3">
            <CardTitle className="text-sm font-medium">Preço médio por região</CardTitle>
          </CardHeader>
          <CardContent>
            {regioes.length === 0 ? (
              <div className="flex items-center justify-center h-[250px] text-muted-foreground">Sem dados</div>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={regioes}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="estado" className="text-xs" />
                  <YAxis tickFormatter={(v: number) => `R$${(v / 1000).toFixed(1)}k`} className="text-xs" />
                  <Tooltip formatter={(v: number) => formatBRL(v)} contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: "8px" }} />
                  <Bar dataKey="media" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Média" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Distribuição por raça */}
        <Card>
          <CardHeader className="py-3">
            <CardTitle className="text-sm font-medium">Distribuição por raça</CardTitle>
          </CardHeader>
          <CardContent>
            {racaData.length === 0 ? (
              <div className="flex items-center justify-center h-[250px] text-muted-foreground">Sem dados</div>
            ) : (
              <ResponsiveContainer width="100%" height={Math.max(150, racaData.length * 32)}>
                <BarChart data={racaData} layout="vertical" margin={{ left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis type="number" className="text-xs" />
                  <YAxis type="category" dataKey="raca" width={80} tick={{ fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: "8px" }} />
                  <Bar dataKey="count" name="Lotes" radius={[0, 4, 4, 0]}>
                    {racaData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Distribuição por sexo */}
        <Card>
          <CardHeader className="py-3">
            <CardTitle className="text-sm font-medium">Distribuição por sexo</CardTitle>
          </CardHeader>
          <CardContent>
            {sexoData.length === 0 ? (
              <div className="flex items-center justify-center h-[250px] text-muted-foreground">Sem dados</div>
            ) : (
              <ResponsiveContainer width="100%" height={Math.max(150, sexoData.length * 40)}>
                <BarChart data={sexoData} layout="vertical" margin={{ left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis type="number" className="text-xs" />
                  <YAxis type="category" dataKey="sexo" width={60} tick={{ fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: "8px" }} />
                  <Bar dataKey="count" name="Lotes" radius={[0, 4, 4, 0]}>
                    {sexoData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
