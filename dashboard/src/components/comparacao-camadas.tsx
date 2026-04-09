import type { ComparacaoCamada } from "@/lib/api";
import { formatBRL } from "@/lib/format";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface Props {
  camadas: ComparacaoCamada[];
  precoAtual: number;
}

function TendenciaIcon({ valor }: { valor: number | null }) {
  if (valor === null) return <Minus className="h-3 w-3 text-muted-foreground" />;
  if (valor > 1) return <TrendingUp className="h-3 w-3 text-green-500" />;
  if (valor < -1) return <TrendingDown className="h-3 w-3 text-red-500" />;
  return <Minus className="h-3 w-3 text-muted-foreground" />;
}

export function ComparacaoCamadas({ camadas, precoAtual }: Props) {
  if (!camadas.length) {
    return (
      <div className="text-xs text-muted-foreground text-center py-4">
        Sem dados para comparação
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
        Comparação Histórica
      </div>
      {camadas.map((c, i) => {
        const diffPct = c.media > 0
          ? ((precoAtual - c.media) / c.media * 100)
          : 0;
        const diffColor = diffPct > 5 ? "text-red-500" : diffPct < -5 ? "text-green-500" : "text-muted-foreground";

        return (
          <div key={i} className="border rounded-md p-2 space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium truncate">{c.label}</span>
              <div className="flex items-center gap-1">
                <TendenciaIcon valor={c.tendencia} />
                {c.tendencia !== null && (
                  <span className="text-[10px] text-muted-foreground">{c.tendencia > 0 ? "+" : ""}{c.tendencia}%</span>
                )}
              </div>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-sm font-bold">{formatBRL(c.media)}</span>
              <span className={`text-[10px] font-medium ${diffColor}`}>
                {diffPct > 0 ? "+" : ""}{diffPct.toFixed(1)}%
              </span>
            </div>
            <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
              <span>Min {formatBRL(c.minimo)}</span>
              <span>Max {formatBRL(c.maximo)}</span>
              <span>{c.lotes} lotes</span>
              <span>{c.n_leiloes_real} leilões</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary rounded-full transition-all"
                  style={{ width: `${Math.min(c.percentual, 100)}%` }}
                />
              </div>
              <span className="text-[10px] font-medium w-10 text-right">
                &gt;{c.percentual}%
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
