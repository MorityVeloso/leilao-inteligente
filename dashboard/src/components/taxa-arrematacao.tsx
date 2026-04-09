import type { FaixaPreco } from "@/lib/api";
import { formatBRL } from "@/lib/format";

interface Props {
  faixas: FaixaPreco[];
  faixaAtual: number | null;
}

const CORES = [
  "bg-green-500",   // >75% — bom preço
  "bg-yellow-500",  // 50-75%
  "bg-orange-500",  // 25-50%
  "bg-red-500",     // <25% — caro
];

function corPorTaxa(taxa: number): string {
  if (taxa >= 75) return CORES[0];
  if (taxa >= 50) return CORES[1];
  if (taxa >= 25) return CORES[2];
  return CORES[3];
}

export function TaxaArrematacao({ faixas, faixaAtual }: Props) {
  if (!faixas.length) {
    return (
      <div className="text-xs text-muted-foreground text-center py-4">
        Sem dados históricos para este perfil
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
        Taxa de Arrematação por Faixa
      </div>
      {faixas.map((f, i) => {
        const isAtual = i === faixaAtual;
        return (
          <div
            key={i}
            className={`flex items-center gap-2 text-xs ${isAtual ? "bg-accent/50 rounded px-1 py-0.5 -mx-1" : ""}`}
          >
            <div className="w-20 text-right text-muted-foreground shrink-0">
              {formatBRL(f.min)}–{formatBRL(f.max).replace("R$ ", "")}
            </div>
            <div className="flex-1 h-4 bg-muted rounded-sm overflow-hidden relative">
              <div
                className={`h-full rounded-sm transition-all ${corPorTaxa(f.taxa)}`}
                style={{ width: `${f.taxa}%` }}
              />
            </div>
            <div className="w-12 text-right font-medium shrink-0">
              {f.taxa}%
            </div>
            <div className="w-16 text-right text-muted-foreground shrink-0">
              {f.arrematados}/{f.total}
            </div>
            {isAtual && (
              <span className="text-[10px] font-bold text-primary shrink-0">← AQUI</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
