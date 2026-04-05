import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { DollarSign, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { api, type TendenciaJanela } from "@/lib/api";

const CATEGORIA_LABELS: Record<string, string> = {
  boi_gordo: "Boi Gordo",
  vaca_gorda: "Vaca Gorda",
  bezerro_12m: "Bezerro 12m",
  garrote: "Garrote",
};

const DESTAQUE_CATEGORIAS = ["boi_gordo", "bezerro_12m", "garrote", "vaca_gorda"];

function TendenciaIcon({ t }: { t: TendenciaJanela | null }) {
  if (!t) return <Minus className="h-3 w-3 text-muted-foreground" />;

  if (t.tendencia === "alta_forte" || t.tendencia === "alta") {
    return <TrendingUp className="h-3 w-3 text-green-500" />;
  }
  if (t.tendencia === "baixa_forte" || t.tendencia === "baixa") {
    return <TrendingDown className="h-3 w-3 text-red-500" />;
  }
  return <Minus className="h-3 w-3 text-muted-foreground" />;
}

function tendenciaColor(t: TendenciaJanela | null): string {
  if (!t) return "text-muted-foreground";
  if (t.tendencia.startsWith("alta")) return "text-green-500";
  if (t.tendencia.startsWith("baixa")) return "text-red-500";
  return "text-muted-foreground";
}

export function MercadoIndicador() {
  const navigate = useNavigate();

  const { data: resumo } = useQuery({
    queryKey: ["mercado-resumo-dash"],
    queryFn: () => api.mercadoResumo({}),
    staleTime: 5 * 60 * 1000,
  });

  const { data: tendenciaCepea } = useQuery({
    queryKey: ["mercado-tendencia-cepea"],
    queryFn: () => api.mercadoTendencia({ categoria: "boi_gordo", fonte: "cepea" }),
    staleTime: 5 * 60 * 1000,
  });

  if (!resumo?.cotacoes || resumo.cotacoes.length === 0) return null;

  // Agregar por categoria
  const porCategoria = new Map<string, { total: number; count: number }>();
  for (const c of resumo.cotacoes) {
    if (c.unidade !== "BRL/@" && c.unidade !== "BRL/cab") continue;
    const existing = porCategoria.get(c.categoria);
    if (!existing) {
      porCategoria.set(c.categoria, { total: c.media, count: 1 });
    } else {
      existing.total += c.media;
      existing.count += 1;
    }
  }

  const destaques = DESTAQUE_CATEGORIAS
    .filter((cat) => porCategoria.has(cat))
    .map((cat) => {
      const d = porCategoria.get(cat)!;
      return {
        categoria: cat,
        label: CATEGORIA_LABELS[cat] || cat,
        media: d.total / d.count,
        unidade: cat.includes("bezerro") || cat.includes("garrote") ? "R$/cab" : "R$/@",
      };
    });

  if (destaques.length === 0) return null;

  // Tendência CEPEA (referência principal)
  const tendencia21 = tendenciaCepea?.janelas?.["21"] ?? null;

  return (
    <Card
      className="cursor-pointer hover:border-green-500/50 transition-colors"
      onClick={() => navigate("/mercado")}
    >
      <CardContent className="px-3 py-2">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1.5">
            <DollarSign className="h-3 w-3 text-green-500" />
            <span className="text-[10px] font-medium text-muted-foreground">
              Referência de Mercado
            </span>
          </div>
          {/* Tendência CEPEA boi gordo */}
          {tendencia21 && (
            <div className="flex items-center gap-1">
              <TendenciaIcon t={tendencia21} />
              <span className={`text-[10px] font-medium ${tendenciaColor(tendencia21)}`}>
                {tendencia21.variacao_pct > 0 ? "+" : ""}
                {tendencia21.variacao_pct.toFixed(1)}%
              </span>
              <span className="text-[9px] text-muted-foreground">21d</span>
            </div>
          )}
          {!tendencia21 && resumo.data && (
            <span className="text-[9px] text-muted-foreground">
              {new Date(resumo.data + "T12:00:00").toLocaleDateString("pt-BR")}
            </span>
          )}
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
          {destaques.map((d) => (
            <div key={d.categoria} className="flex items-baseline justify-between">
              <span className="text-[10px] text-muted-foreground">{d.label}</span>
              <span className="text-xs font-mono font-medium">
                {d.media.toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                <span className="text-[9px] text-muted-foreground ml-0.5">
                  {d.unidade === "R$/@" ? "/@" : "/cab"}
                </span>
              </span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
