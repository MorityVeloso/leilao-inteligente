import { useEffect, useState } from "react";
import { MapPin, Home } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type Filtros, type Fazenda, type Regiao } from "@/lib/api";

function formatBRL(value: number): string {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

interface PaineisProps {
  filtros: Filtros;
}

export function Paineis({ filtros }: PaineisProps) {
  const [regioes, setRegioes] = useState<Regiao[]>([]);
  const [fazendas, setFazendas] = useState<Fazenda[]>([]);

  useEffect(() => {
    api.regioes(filtros).then(setRegioes);
    api.fazendas(filtros).then(setFazendas);
  }, [filtros]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Card>
        <CardHeader className="flex flex-row items-center gap-2">
          <MapPin className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-sm font-medium">Por Região</CardTitle>
        </CardHeader>
        <CardContent>
          {regioes.length === 0 ? (
            <p className="text-sm text-muted-foreground">Sem dados</p>
          ) : (
            <div className="space-y-3">
              {regioes.map((r) => (
                <div key={r.estado} className="flex items-center justify-between">
                  <div>
                    <span className="font-semibold">{r.estado}</span>
                    <span className="text-xs text-muted-foreground ml-2">
                      ({r.lotes} lotes)
                    </span>
                  </div>
                  <span className="font-mono text-sm">{formatBRL(r.media)}</span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center gap-2">
          <Home className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-sm font-medium">Melhores Fazendas</CardTitle>
        </CardHeader>
        <CardContent>
          {fazendas.length === 0 ? (
            <p className="text-sm text-muted-foreground">Sem dados</p>
          ) : (
            <div className="space-y-3">
              {fazendas.slice(0, 8).map((f) => (
                <div key={f.fazenda} className="flex items-center justify-between">
                  <div>
                    <span className="font-semibold text-sm">{f.fazenda}</span>
                    <span className="text-xs text-muted-foreground ml-2">
                      ({f.lotes}x, {f.cabecas} cab.)
                    </span>
                  </div>
                  <span className="font-mono text-sm">{formatBRL(f.media)}</span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
