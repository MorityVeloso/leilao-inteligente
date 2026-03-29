import { useQuery } from "@tanstack/react-query";
import { MapPin, Home } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { api, type Filtros } from "@/lib/api";

function formatBRL(value: number): string {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

interface PaineisProps {
  filtros: Filtros;
}

export function Paineis({ filtros }: PaineisProps) {
  const { data: regioes = [] } = useQuery({
    queryKey: ["regioes", filtros],
    queryFn: () => api.regioes(filtros),
  });
  const { data: fazendas = [] } = useQuery({
    queryKey: ["fazendas", filtros],
    queryFn: () => api.fazendas(filtros),
  });

  return (
    <div className="grid grid-cols-2 gap-2">
      <Card>
        <CardContent className="pt-3 pb-2 px-3">
          <div className="flex items-center gap-1.5 mb-2">
            <MapPin className="h-3 w-3 text-muted-foreground" />
            <p className="text-[11px] font-medium text-muted-foreground">Por Região</p>
          </div>
          {regioes.length === 0 ? (
            <p className="text-[11px] text-muted-foreground">Sem dados</p>
          ) : (
            <div className="space-y-1.5">
              {regioes.map((r) => (
                <div key={r.estado} className="flex items-center justify-between">
                  <div>
                    <span className="text-xs font-semibold">{r.estado}</span>
                    <span className="text-[10px] text-muted-foreground ml-1">
                      ({r.lotes} lotes)
                    </span>
                  </div>
                  <span className="font-mono text-[11px]">{formatBRL(r.media)}</span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-3 pb-2 px-3">
          <div className="flex items-center gap-1.5 mb-2">
            <Home className="h-3 w-3 text-muted-foreground" />
            <p className="text-[11px] font-medium text-muted-foreground">Melhores Fazendas</p>
          </div>
          {fazendas.length === 0 ? (
            <p className="text-[11px] text-muted-foreground">Sem dados</p>
          ) : (
            <div className="space-y-1">
              {fazendas.slice(0, 6).map((f) => (
                <div key={f.fazenda} className="flex items-center justify-between">
                  <div>
                    <span className="text-[11px] font-semibold">{f.fazenda}</span>
                    <span className="text-[9px] text-muted-foreground ml-1">
                      ({f.lotes}x, {f.cabecas} cab.)
                    </span>
                  </div>
                  <span className="font-mono text-[11px]">{formatBRL(f.media)}</span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
