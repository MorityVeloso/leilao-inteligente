import { useQuery } from "@tanstack/react-query";
import { TrendingUp, TrendingDown, DollarSign, ArrowDown, ArrowUp } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { api, type Filtros } from "@/lib/api";

function formatBRL(value: number | null): string {
  if (value === null) return "—";
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

interface MetricasCardsProps {
  filtros: Filtros;
}

export function MetricasCards({ filtros }: MetricasCardsProps) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["metricas", filtros],
    queryFn: () => api.metricas(filtros),
  });

  if (isError) {
    return (
      <Card>
        <CardContent className="py-4 text-center text-sm text-destructive">
          Erro ao carregar métricas
        </CardContent>
      </Card>
    );
  }

  if (isLoading || !data) {
    return (
      <div className="grid grid-cols-2 gap-2">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i} className="animate-pulse py-2">
            <CardContent className="px-3"><div className="h-6 bg-muted rounded w-24" /></CardContent>
          </Card>
        ))}
      </div>
    );
  }

  const tendencia = data.tendencia_percentual;

  return (
    <div className="grid grid-cols-2 gap-2">
      <Card className="py-2">
        <CardContent className="flex items-center justify-between px-3">
          <div>
            <p className="text-[10px] text-muted-foreground">Média</p>
            <p className="text-sm font-bold">{formatBRL(data.media)}</p>
            <p className="text-[10px] text-muted-foreground">{data.total_lotes} lotes</p>
          </div>
          <DollarSign className="h-3 w-3 text-muted-foreground" />
        </CardContent>
      </Card>

      <Card className="py-2">
        <CardContent className="flex items-center justify-between px-3">
          <div>
            <p className="text-[10px] text-muted-foreground">Mínimo</p>
            <p className="text-sm font-bold">{formatBRL(data.minimo)}</p>
            <p className="text-[10px] text-muted-foreground">{data.total_cabecas} cabeças</p>
          </div>
          <ArrowDown className="h-3 w-3 text-muted-foreground" />
        </CardContent>
      </Card>

      <Card className="py-2">
        <CardContent className="flex items-center justify-between px-3">
          <div>
            <p className="text-[10px] text-muted-foreground">Máximo</p>
            <p className="text-sm font-bold">{formatBRL(data.maximo)}</p>
          </div>
          <ArrowUp className="h-3 w-3 text-muted-foreground" />
        </CardContent>
      </Card>

      <Card className="py-2">
        <CardContent className="flex items-center justify-between px-3">
          <div>
            <p className="text-[10px] text-muted-foreground">Tendência</p>
            <p className={`text-sm font-bold ${
              tendencia !== null
                ? tendencia >= 0 ? "text-green-500" : "text-red-500"
                : ""
            }`}>
              {tendencia !== null ? `${tendencia > 0 ? "+" : ""}${tendencia}%` : "—"}
            </p>
            <p className="text-[10px] text-muted-foreground">vs período anterior</p>
          </div>
          {tendencia !== null && tendencia >= 0 ? (
            <TrendingUp className="h-3 w-3 text-green-500" />
          ) : (
            <TrendingDown className="h-3 w-3 text-red-500" />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
