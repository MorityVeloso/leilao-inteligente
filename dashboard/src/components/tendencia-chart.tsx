import { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type Filtros, type PontoTendencia } from "@/lib/api";

interface TendenciaChartProps {
  filtros: Filtros;
}

export function TendenciaChart({ filtros }: TendenciaChartProps) {
  const [data, setData] = useState<PontoTendencia[]>([]);

  useEffect(() => {
    api.tendencia(filtros).then(setData);
  }, [filtros]);

  if (data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Tendência de preço</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-[200px] text-muted-foreground">
          Processe mais leiloes para ver a tendencia
        </CardContent>
      </Card>
    );
  }

  const chartData = data.map((d) => ({
    ...d,
    dataFormatada: d.data ? new Date(d.data).toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }) : "",
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">Tendência de preço</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis dataKey="dataFormatada" className="text-xs" />
            <YAxis
              domain={["auto", "auto"]}
              tickFormatter={(v: number) => `R$${(v / 1000).toFixed(1)}k`}
              className="text-xs"
            />
            <Tooltip
              formatter={(value: number) =>
                value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" })
              }
              labelFormatter={(label: string) => label}
              contentStyle={{
                background: "var(--popover)",
                border: "1px solid var(--border)",
                borderRadius: "8px",
              }}
            />
            <Line
              type="monotone"
              dataKey="media"
              stroke="hsl(142, 71%, 45%)"
              strokeWidth={2}
              dot={{ r: 5, fill: "hsl(142, 71%, 45%)" }}
              name="Média"
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
