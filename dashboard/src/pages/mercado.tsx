import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Info, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { api } from "@/lib/api";

// Mapeamento de categorias para nomes legíveis
const CATEGORIA_LABELS: Record<string, string> = {
  boi_gordo: "Boi Gordo",
  vaca_gorda: "Vaca Gorda",
  novilha_abate: "Novilha (Abate)",
  bezerro_8m: "Bezerro 8m",
  bezerro_12m: "Bezerro 12m",
  bezerra_8m: "Bezerra 8m",
  bezerra_12m: "Bezerra 12m",
  garrote: "Garrote 18m",
  boi_magro: "Boi Magro",
  novilha: "Novilha 18m",
  vaca_boiadeira: "Vaca Boiadeira",
};

const FONTE_COLORS: Record<string, string> = {
  scot: "bg-blue-600",
  datagro: "bg-purple-600",
  cepea: "bg-green-600",
  imea: "bg-amber-600",
};

const GLOSSARIO = [
  { termo: "Nelore", desc: "Inclui Anelorado, Tabapuã, Guzerá e demais zebuínos puros" },
  { termo: "Mestiço", desc: "Cruzamento industrial (Nelore × taurino: Angus, Hereford, etc.)" },
  { termo: "Bezerro 8m", desc: "Desmama, até 8 meses de idade" },
  { termo: "Bezerro 12m", desc: "12 meses, pós-desmama" },
  { termo: "Garrote 18m", desc: "18 meses, em fase de recria" },
  { termo: "Boi Magro", desc: "Acima de 24 meses, pronto para engorda" },
  { termo: "R$/@", desc: "Reais por arroba (15 kg de carcaça)" },
  { termo: "R$/cab", desc: "Reais por cabeça" },
  { termo: "CEPEA", desc: "Indicador ESALQ/BM&F — referência nacional (SP)" },
  { termo: "Scot", desc: "Scot Consultoria — cotações por praça em 17 estados" },
  { termo: "Datagro", desc: "Indicadores por estado (boi, vaca, novilha)" },
  { termo: "IMEA", desc: "Instituto Mato-Grossense — cotações por município (MT)" },
];

export function MercadoPage() {
  const queryClient = useQueryClient();
  const [estado, setEstado] = useState<string>("all");
  const [categoria, setCategoria] = useState<string>("all");
  const [fonte, setFonte] = useState<string>("all");
  const [atualizando, setAtualizando] = useState(false);
  const [showGlossario, setShowGlossario] = useState(false);

  const { data: filtros } = useQuery({
    queryKey: ["mercado-filtros"],
    queryFn: api.mercadoFiltros,
  });

  const { data: resumo, isLoading } = useQuery({
    queryKey: ["mercado-resumo", estado, categoria],
    queryFn: () => api.mercadoResumo({
      estado: estado !== "all" ? estado : undefined,
      categoria: categoria !== "all" ? categoria : undefined,
    }),
  });

  const { data: tendenciaBoi } = useQuery({
    queryKey: ["mercado-tendencia-boi", estado, fonte],
    queryFn: () => api.mercadoTendencia({
      categoria: "boi_gordo",
      estado: estado !== "all" ? estado : undefined,
      fonte: fonte !== "all" ? fonte : "cepea",
    }),
    staleTime: 5 * 60 * 1000,
  });

  // Fallback: CEPEA nacional quando estado selecionado não tem dados
  const estadoSelecionado = estado !== "all";
  const precisaFallback = estadoSelecionado && tendenciaBoi?.insuficiente;
  const { data: tendenciaFallback } = useQuery({
    queryKey: ["mercado-tendencia-fallback"],
    queryFn: () => api.mercadoTendencia({ categoria: "boi_gordo", fonte: "cepea" }),
    staleTime: 5 * 60 * 1000,
    enabled: !!precisaFallback,
  });

  const tendenciaExibida = precisaFallback ? tendenciaFallback : tendenciaBoi;
  const usandoFallback = !!precisaFallback && !!tendenciaFallback && !tendenciaFallback.insuficiente;

  const { data: cotacoes } = useQuery({
    queryKey: ["mercado-cotacoes", estado, categoria, fonte],
    queryFn: () => api.mercadoCotacoes({
      estado: estado !== "all" ? estado : undefined,
      categoria: categoria !== "all" ? categoria : undefined,
      fonte: fonte !== "all" ? fonte : undefined,
      dias: 7,
    }),
  });

  async function handleAtualizar() {
    setAtualizando(true);
    try {
      await api.mercadoAtualizar();
      queryClient.invalidateQueries({ queryKey: ["mercado-resumo"] });
      queryClient.invalidateQueries({ queryKey: ["mercado-cotacoes"] });
      queryClient.invalidateQueries({ queryKey: ["mercado-filtros"] });
    } finally {
      setAtualizando(false);
    }
  }

  // Agrupar resumo por categoria para cards
  const categoriaCards = new Map<string, { media: number; min: number; max: number; estados: number; unidade: string }>();
  if (resumo?.cotacoes) {
    for (const c of resumo.cotacoes) {
      const existing = categoriaCards.get(c.categoria);
      if (!existing) {
        categoriaCards.set(c.categoria, {
          media: c.media,
          min: c.minimo,
          max: c.maximo,
          estados: 1,
          unidade: c.unidade,
        });
      } else {
        existing.media = (existing.media * existing.estados + c.media) / (existing.estados + 1);
        existing.min = Math.min(existing.min, c.minimo);
        existing.max = Math.max(existing.max, c.maximo);
        existing.estados += 1;
      }
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Mercado de Referência</h1>
          <p className="text-sm text-muted-foreground">
            Cotações do mercado bovino — CEPEA, Scot, Datagro, IMEA
            {resumo?.data && (
              <span className="ml-2 text-xs">
                (atualizado: {new Date(resumo.data + "T12:00:00").toLocaleDateString("pt-BR")})
              </span>
            )}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowGlossario(!showGlossario)}
          >
            <Info className="mr-1 h-4 w-4" />
            Glossário
          </Button>
          <Button
            size="sm"
            onClick={handleAtualizar}
            disabled={atualizando}
          >
            <RefreshCw className={`mr-1 h-4 w-4 ${atualizando ? "animate-spin" : ""}`} />
            {atualizando ? "Atualizando..." : "Atualizar Cotações"}
          </Button>
        </div>
      </div>

      {/* Glossário */}
      {showGlossario && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Glossário de Termos</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-sm">
              {GLOSSARIO.map((g) => (
                <div key={g.termo} className="flex gap-2">
                  <span className="font-medium text-foreground min-w-[80px]">{g.termo}</span>
                  <span className="text-muted-foreground">{g.desc}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filtros */}
      <div className="flex gap-4 flex-wrap items-end">
        <div>
          <p className="text-[10px] text-muted-foreground mb-1">Estado (UF)</p>
          <Select value={estado} onValueChange={(v) => setEstado(v ?? "all")}>
            <SelectTrigger className="w-[160px]">
              <SelectValue>{estado === "all" ? "Todos os estados" : estado}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todos os estados</SelectItem>
              {filtros?.estados.map((e) => (
                <SelectItem key={e} value={e}>{e}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div>
          <p className="text-[10px] text-muted-foreground mb-1">Categoria animal</p>
          <Select value={categoria} onValueChange={(v) => setCategoria(v ?? "all")}>
            <SelectTrigger className="w-[200px]">
              <SelectValue>{categoria === "all" ? "Todas as categorias" : (CATEGORIA_LABELS[categoria] || categoria)}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas as categorias</SelectItem>
              {filtros?.categorias.map((c) => (
                <SelectItem key={c} value={c}>{CATEGORIA_LABELS[c] || c}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div>
          <p className="text-[10px] text-muted-foreground mb-1">Fonte de dados</p>
          <Select value={fonte} onValueChange={(v) => setFonte(v ?? "all")}>
            <SelectTrigger className="w-[170px]">
              <SelectValue>{fonte === "all" ? "Todas as fontes" : fonte.toUpperCase()}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Todas as fontes</SelectItem>
              {filtros?.fontes.map((f) => (
                <SelectItem key={f} value={f}>{f.toUpperCase()}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Tendência Boi Gordo */}
      {tendenciaExibida && !tendenciaExibida.insuficiente && Object.keys(tendenciaExibida.janelas).length > 0 && (
        <Card>
          <CardContent className="px-4 py-3">
            {usandoFallback && (
              <div className="mb-3 px-3 py-2 rounded-md bg-amber-500/15 border border-amber-500/30">
                <p className="text-xs font-medium text-amber-600">
                  Sem dados suficientes para {estado} — exibindo referência nacional CEPEA/ESALQ (SP)
                </p>
              </div>
            )}
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">
                Tendência — Boi Gordo {tendenciaExibida.fonte?.toUpperCase() || ""}
                {usandoFallback && " (ref. nacional)"}
              </span>
              {tendenciaExibida.ultima_data && (
                <span className="text-xs text-muted-foreground ml-auto">
                  Último: R$ {tendenciaExibida.ultimo_valor?.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}/@
                  ({new Date(tendenciaExibida.ultima_data + "T12:00:00").toLocaleDateString("pt-BR")})
                </span>
              )}
            </div>
            <div className="grid grid-cols-3 gap-4">
              {(["7", "21", "90"] as const).map((j) => {
                const t = tendenciaExibida.janelas[j];
                if (!t) return null;

                const isAlta = t.tendencia.startsWith("alta");
                const isBaixa = t.tendencia.startsWith("baixa");
                const color = isAlta ? "text-green-500" : isBaixa ? "text-red-500" : "text-muted-foreground";
                const bgColor = isAlta ? "bg-green-500/10" : isBaixa ? "bg-red-500/10" : "bg-muted/30";
                const label = j === "7" ? "7 dias" : j === "21" ? "21 dias" : "90 dias";
                const labelTend = {
                  alta_forte: "Alta forte",
                  alta: "Alta",
                  estavel: "Estável",
                  baixa: "Baixa",
                  baixa_forte: "Baixa forte",
                }[t.tendencia];

                return (
                  <div key={j} className={`rounded-lg px-3 py-2 ${bgColor}`}>
                    <p className="text-[10px] text-muted-foreground mb-1">{label}</p>
                    <div className="flex items-center gap-1.5">
                      {isAlta && <TrendingUp className={`h-4 w-4 ${color}`} />}
                      {isBaixa && <TrendingDown className={`h-4 w-4 ${color}`} />}
                      {!isAlta && !isBaixa && <Minus className={`h-4 w-4 ${color}`} />}
                      <span className={`text-sm font-bold ${color}`}>
                        {t.variacao_pct > 0 ? "+" : ""}{t.variacao_pct.toFixed(1)}%
                      </span>
                    </div>
                    <p className={`text-[10px] font-medium ${color}`}>{labelTend}</p>
                    <p className="text-[9px] text-muted-foreground mt-1">
                      R$ {t.preco_inicial.toFixed(0)} → {t.preco_final.toFixed(0)} · {t.n_pontos} pts
                      {t.r_squared >= 0.7 ? " · ★" : t.r_squared >= 0.4 ? " · ◆" : ""}
                    </p>
                  </div>
                );
              })}
            </div>
            <p className="text-[9px] text-muted-foreground mt-2">
              ★ Tendência forte (R²≥0.7) · ◆ Tendência moderada (R²≥0.4) · Sem símbolo = tendência fraca
            </p>
          </CardContent>
        </Card>
      )}

      {/* Cards de resumo por categoria */}
      {!isLoading && categoriaCards.size > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {Array.from(categoriaCards.entries())
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([cat, data]) => (
              <Card
                key={cat}
                className={`cursor-pointer transition-colors ${categoria === cat ? "border-green-500 bg-green-500/5" : "hover:border-muted-foreground/30"}`}
                onClick={() => setCategoria(categoria === cat ? "all" : cat)}
              >
                <CardContent className="p-4">
                  <div className="text-xs text-muted-foreground mb-1">
                    {CATEGORIA_LABELS[cat] || cat}
                  </div>
                  <div className="text-lg font-bold">
                    R$ {data.media.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    <span className="text-sm font-normal text-muted-foreground ml-1">
                      {data.unidade === "BRL/@" ? "/@" : "/cab"}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {data.min.toFixed(0)} — {data.max.toFixed(0)} · {data.estados} {data.estados === 1 ? "UF" : "UFs"}
                  </div>
                </CardContent>
              </Card>
            ))}
        </div>
      )}

      {/* Tabela de cotações */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center justify-between">
            <span>Cotações Detalhadas (últimos 7 dias)</span>
            <span className="text-xs text-muted-foreground font-normal">
              {cotacoes?.length || 0} registros
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="max-h-[500px] overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="sticky top-0 bg-background">Data</TableHead>
                  <TableHead className="sticky top-0 bg-background">UF</TableHead>
                  <TableHead className="sticky top-0 bg-background">Categoria</TableHead>
                  <TableHead className="sticky top-0 bg-background">Raça</TableHead>
                  <TableHead className="sticky top-0 bg-background text-right">Valor</TableHead>
                  <TableHead className="sticky top-0 bg-background">Un.</TableHead>
                  <TableHead className="sticky top-0 bg-background">Fonte</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {cotacoes?.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="text-xs">
                      {new Date(c.data + "T12:00:00").toLocaleDateString("pt-BR")}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-xs">{c.estado}</Badge>
                    </TableCell>
                    <TableCell className="text-xs">{CATEGORIA_LABELS[c.categoria] || c.categoria}</TableCell>
                    <TableCell className="text-xs capitalize">{c.raca}</TableCell>
                    <TableCell className="text-right font-mono text-sm font-medium">
                      R$ {c.valor.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">{c.unidade}</TableCell>
                    <TableCell>
                      <Badge className={`text-xs ${FONTE_COLORS[c.fonte] || "bg-gray-600"}`}>
                        {c.fonte.toUpperCase()}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
                {(!cotacoes || cotacoes.length === 0) && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                      {isLoading ? "Carregando..." : "Nenhuma cotação encontrada. Clique em 'Atualizar Cotações'."}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Resumo por estado */}
      {resumo?.cotacoes && resumo.cotacoes.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Resumo por Estado × Fonte</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="max-h-[400px] overflow-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="sticky top-0 bg-background">UF</TableHead>
                    <TableHead className="sticky top-0 bg-background">Categoria</TableHead>
                    <TableHead className="sticky top-0 bg-background">Raça</TableHead>
                    <TableHead className="sticky top-0 bg-background text-right">Média</TableHead>
                    <TableHead className="sticky top-0 bg-background text-right">Mín</TableHead>
                    <TableHead className="sticky top-0 bg-background text-right">Máx</TableHead>
                    <TableHead className="sticky top-0 bg-background">Fonte</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {resumo.cotacoes.map((c, i) => (
                    <TableRow key={i}>
                      <TableCell>
                        <Badge variant="outline" className="text-xs">{c.estado}</Badge>
                      </TableCell>
                      <TableCell className="text-xs">{CATEGORIA_LABELS[c.categoria] || c.categoria}</TableCell>
                      <TableCell className="text-xs capitalize">{c.raca}</TableCell>
                      <TableCell className="text-right font-mono text-sm font-medium">
                        R$ {c.media.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                      </TableCell>
                      <TableCell className="text-right text-xs text-muted-foreground">
                        R$ {c.minimo.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                      </TableCell>
                      <TableCell className="text-right text-xs text-muted-foreground">
                        R$ {c.maximo.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                      </TableCell>
                      <TableCell>
                        <Badge className={`text-xs ${FONTE_COLORS[c.fonte] || "bg-gray-600"}`}>
                          {c.fonte.toUpperCase()}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
