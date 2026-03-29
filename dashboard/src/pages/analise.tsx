import { useEffect, useState } from "react";
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
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api, type Filtros, type Fazenda, type Regiao, type PontoTendencia } from "@/lib/api";

const COLORS = ["#22c55e", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16"];

function formatBRL(value: number): string {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export function AnalisePage() {
  const [filtros, setFiltros] = useState<Filtros>({ dias: 90 });
  const [tendencia, setTendencia] = useState<PontoTendencia[]>([]);
  const [fazendas, setFazendas] = useState<Fazenda[]>([]);
  const [regioes, setRegioes] = useState<Regiao[]>([]);
  const [racaData, setRacaData] = useState<{ raca: string; count: number }[]>([]);
  const [sexoData, setSexoData] = useState<{ sexo: string; count: number }[]>([]);

  useEffect(() => {
    api.tendencia(filtros).then(setTendencia);
    api.fazendas(filtros).then(setFazendas);
    api.regioes(filtros).then(setRegioes);

    // Distribuição por raça e sexo
    api.lotes(filtros).then((lotes) => {
      const racas: Record<string, number> = {};
      const sexos: Record<string, number> = {};
      for (const l of lotes) {
        racas[l.raca] = (racas[l.raca] || 0) + 1;
        sexos[l.sexo] = (sexos[l.sexo] || 0) + 1;
      }
      setRacaData(
        Object.entries(racas)
          .map(([raca, count]) => ({ raca, count }))
          .sort((a, b) => b.count - a.count)
      );
      setSexoData(
        Object.entries(sexos)
          .map(([sexo, count]) => ({ sexo: sexo === "macho" ? "Macho" : sexo === "femea" ? "Fêmea" : "Misto", count }))
          .sort((a, b) => b.count - a.count)
      );
    });
  }, [filtros]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Análise</h1>
          <p className="text-sm text-muted-foreground">
            Gráficos detalhados e comparativos
          </p>
        </div>
        <Select
          value={String(filtros.dias ?? 90)}
          onValueChange={(v) => setFiltros({ ...filtros, dias: Number(v) })}
        >
          <SelectTrigger className="w-[130px]">
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

      {/* Tendencia */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Tendência de preço por leilão</CardTitle>
        </CardHeader>
        <CardContent>
          {tendencia.length === 0 ? (
            <div className="flex items-center justify-center h-[250px] text-muted-foreground">
              Processe mais leilões para ver a tendência
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
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
          <CardHeader>
            <CardTitle className="text-sm font-medium">Preço médio por fazenda (top 10)</CardTitle>
          </CardHeader>
          <CardContent>
            {fazendas.length === 0 ? (
              <div className="flex items-center justify-center h-[250px] text-muted-foreground">Sem dados</div>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={fazendas.slice(0, 10)} layout="vertical" margin={{ left: 80 }}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis type="number" tickFormatter={(v: number) => `R$${(v / 1000).toFixed(1)}k`} className="text-xs" />
                  <YAxis type="category" dataKey="fazenda" className="text-xs" width={80} />
                  <Tooltip formatter={(v: number) => formatBRL(v)} contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: "8px" }} />
                  <Bar dataKey="media" fill="hsl(142, 71%, 45%)" radius={[0, 4, 4, 0]} name="Média" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Regioes */}
        <Card>
          <CardHeader>
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
          <CardHeader>
            <CardTitle className="text-sm font-medium">Distribuição por raça</CardTitle>
          </CardHeader>
          <CardContent>
            {racaData.length === 0 ? (
              <div className="flex items-center justify-center h-[250px] text-muted-foreground">Sem dados</div>
            ) : (
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie data={racaData} dataKey="count" nameKey="raca" cx="50%" cy="50%" outerRadius={90} label={({ raca, percent }) => `${raca} ${(percent * 100).toFixed(0)}%`}>
                    {racaData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Distribuição por sexo */}
        <Card>
          <CardHeader>
            <CardTitle className="text-sm font-medium">Distribuição por sexo</CardTitle>
          </CardHeader>
          <CardContent>
            {sexoData.length === 0 ? (
              <div className="flex items-center justify-center h-[250px] text-muted-foreground">Sem dados</div>
            ) : (
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie data={sexoData} dataKey="count" nameKey="sexo" cx="50%" cy="50%" outerRadius={90} label={({ sexo, percent }) => `${sexo} ${(percent * 100).toFixed(0)}%`}>
                    {sexoData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
