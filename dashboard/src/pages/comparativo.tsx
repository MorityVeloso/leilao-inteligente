import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
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
import { Check, X, TrendingUp, BarChart3, Scale } from "lucide-react";
import { Badge } from "@/components/ui/badge";
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
import { useCustos } from "@/hooks/use-custos";

function formatBRL(value: number | null): string {
  if (value === null) return "—";
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function categoriaLabel(c: ComparativoCategoria): string {
  const sexo = c.sexo === "macho" ? "M" : c.sexo === "femea" ? "F" : "Mx";
  const cond = c.condicao ? ` ${c.condicao}` : "";
  return `${c.raca} ${sexo}${cond} ${c.idade_meses}m`;
}

export function ComparativoPage() {
  const [cidadeA, setCidadeA] = useState<string>("");
  const [cidadeB, setCidadeB] = useState<string>("");
  const [raca, setRaca] = useState<string>("");
  const [sexo, setSexo] = useState<string>("");
  const [dias, setDias] = useState(180);

  const { custos, setCusto, calcularLucro } = useCustos();

  const { data: opcoes } = useQuery({
    queryKey: ["filtros"],
    queryFn: () => api.filtros(),
    staleTime: 60_000,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["comparativo", cidadeA, cidadeB, raca, sexo, dias],
    queryFn: () =>
      api.comparativoCidades({
        cidade_a: cidadeA,
        cidade_b: cidadeB,
        raca: raca || undefined,
        sexo: sexo || undefined,
        dias,
      }),
    enabled: !!cidadeA && !!cidadeB && cidadeA !== cidadeB,
  });

  const categorias = data?.categorias ?? [];
  const comDados = categorias.filter((c) => c.media_a != null && c.media_b != null);

  // Dados do gráfico
  const chartData = comDados.map((c) => ({
    name: categoriaLabel(c),
    [cidadeA]: c.media_a,
    [cidadeB]: c.media_b,
  }));

  // Cards resumo
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
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Comparativo</h1>
        <p className="text-sm text-muted-foreground">
          Compare preços entre cidades e analise oportunidades de arbitragem
        </p>
      </div>

      {/* Controles */}
      <div className="flex gap-2 flex-wrap items-end">
        <div className="space-y-1">
          <label className="text-[10px] font-medium text-muted-foreground">Cidade A (Compra)</label>
          <Select value={cidadeA} onValueChange={setCidadeA}>
            <SelectTrigger className="w-[160px] h-8 text-xs">
              <SelectValue placeholder="Selecione..." />
            </SelectTrigger>
            <SelectContent>
              {opcoes?.cidades.map((c) => (
                <SelectItem key={c} value={c}>{c}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <label className="text-[10px] font-medium text-muted-foreground">Cidade B (Venda)</label>
          <Select value={cidadeB} onValueChange={setCidadeB}>
            <SelectTrigger className="w-[160px] h-8 text-xs">
              <SelectValue placeholder="Selecione..." />
            </SelectTrigger>
            <SelectContent>
              {opcoes?.cidades.map((c) => (
                <SelectItem key={c} value={c}>{c}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <Select value={raca || "todas"} onValueChange={(v) => setRaca(v === "todas" ? "" : v)}>
          <SelectTrigger className="w-[120px] h-8 text-xs">
            <SelectValue placeholder="Raça" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todas">Todas raças</SelectItem>
            {opcoes?.racas.map((r) => (
              <SelectItem key={r} value={r}>{r}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={sexo || "todos"} onValueChange={(v) => setSexo(v === "todos" ? "" : v)}>
          <SelectTrigger className="w-[100px] h-8 text-xs">
            <SelectValue placeholder="Sexo" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todos</SelectItem>
            <SelectItem value="macho">Macho</SelectItem>
            <SelectItem value="femea">Fêmea</SelectItem>
          </SelectContent>
        </Select>

        <Select value={String(dias)} onValueChange={(v) => setDias(Number(v))}>
          <SelectTrigger className="w-[110px] h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="30">30 dias</SelectItem>
            <SelectItem value="90">90 dias</SelectItem>
            <SelectItem value="180">6 meses</SelectItem>
            <SelectItem value="365">1 ano</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {!cidadeA || !cidadeB || cidadeA === cidadeB ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-20 text-muted-foreground">
            <Scale className="h-12 w-12 mb-4 opacity-30" />
            <p className="text-lg font-medium">Selecione duas cidades diferentes</p>
            <p className="text-sm mt-1">Escolha a cidade de compra e a cidade de venda para comparar</p>
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
                <p className="text-[10px] text-muted-foreground">{cidadeB} vs {cidadeA}</p>
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
                    <Bar dataKey={cidadeA} fill="#3b82f6" radius={[0, 4, 4, 0]} name={cidadeA} />
                    <Bar dataKey={cidadeB} fill="#22c55e" radius={[0, 4, 4, 0]} name={cidadeB} />
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
                    <TableHead className="px-2 text-right">Preço {cidadeA}</TableHead>
                    <TableHead className="px-2 text-right">Preço {cidadeB}</TableHead>
                    <TableHead className="px-2 text-right">Spread</TableHead>
                    <TableHead className="px-2 text-right">Custos</TableHead>
                    <TableHead className="px-2 text-right">Lucro/cab</TableHead>
                    <TableHead className="px-2 text-center w-16">Viável?</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {categorias.map((c, i) => {
                    const lucro = c.media_a != null && c.media_b != null
                      ? calcularLucro(c.media_a, c.media_b)
                      : null;
                    const custoTotal = c.media_a != null
                      ? custos.frete + (c.media_a * custos.comissao / 100) + custos.outros
                      : null;
                    const sexoLabel = c.sexo === "macho" ? "M" : c.sexo === "femea" ? "F" : "Mx";
                    const condLabel = c.condicao ? ` ${c.condicao}` : "";

                    return (
                      <TableRow key={i}>
                        <TableCell className="px-2 font-medium">
                          {c.raca} {sexoLabel}{condLabel}
                          <span className="text-[10px] text-muted-foreground ml-1">
                            ({c.lotes_a}+{c.lotes_b} lotes)
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
                    );
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
