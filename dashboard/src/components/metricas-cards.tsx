import { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, DollarSign, ArrowDown, ArrowUp, Hash } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type Filtros, type Metricas } from "@/lib/api";

function formatBRL(value: number | null): string {
  if (value === null) return "—";
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

interface MetricasCardsProps {
  filtros: Filtros;
}

export function MetricasCards({ filtros }: MetricasCardsProps) {
  const [data, setData] = useState<Metricas | null>(null);

  useEffect(() => {
    api.metricas(filtros).then(setData);
  }, [filtros]);

  if (!data) {
    return (
      <div className="grid grid-cols-2 gap-3">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i} className="animate-pulse">
            <CardHeader className="pb-2"><div className="h-4 bg-muted rounded w-20" /></CardHeader>
            <CardContent><div className="h-8 bg-muted rounded w-32" /></CardContent>
          </Card>
        ))}
      </div>
    );
  }

  const tendencia = data.tendencia_percentual;

  return (
    <div className="grid grid-cols-2 gap-3">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Média</CardTitle>
          <DollarSign className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{formatBRL(data.media)}</div>
          <p className="text-xs text-muted-foreground">{data.total_lotes} lotes</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Mínimo</CardTitle>
          <ArrowDown className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{formatBRL(data.minimo)}</div>
          <p className="text-xs text-muted-foreground">{data.total_cabecas} cabeças</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Máximo</CardTitle>
          <ArrowUp className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{formatBRL(data.maximo)}</div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">Tendência</CardTitle>
          {tendencia !== null && tendencia >= 0 ? (
            <TrendingUp className="h-4 w-4 text-green-500" />
          ) : (
            <TrendingDown className="h-4 w-4 text-red-500" />
          )}
        </CardHeader>
        <CardContent>
          <div className={`text-2xl font-bold ${
            tendencia !== null
              ? tendencia >= 0 ? "text-green-500" : "text-red-500"
              : ""
          }`}>
            {tendencia !== null ? `${tendencia > 0 ? "+" : ""}${tendencia}%` : "—"}
          </div>
          <p className="text-xs text-muted-foreground">vs período anterior</p>
        </CardContent>
      </Card>
    </div>
  );
}
