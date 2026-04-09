import type { LoteAoVivo } from "@/lib/api";
import { formatBRL } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { ArrowUp, ArrowDown, Minus, Gavel, Clock } from "lucide-react";
import { useEffect, useState } from "react";

interface Props {
  lote: LoteAoVivo;
}

function TempoNaPista({ inicio }: { inicio: string }) {
  const [tempo, setTempo] = useState("");

  useEffect(() => {
    function atualizar() {
      const diff = Math.floor((Date.now() - new Date(inicio).getTime()) / 1000);
      const min = Math.floor(diff / 60);
      const sec = diff % 60;
      setTempo(`${min}m${sec.toString().padStart(2, "0")}s`);
    }
    atualizar();
    const interval = setInterval(atualizar, 1000);
    return () => clearInterval(interval);
  }, [inicio]);

  return (
    <span className="flex items-center gap-1 text-xs text-muted-foreground">
      <Clock className="h-3 w-3" /> {tempo}
    </span>
  );
}

export function LoteAoVivoPanel({ lote }: Props) {
  const precoSubiu = lote.preco_atual > lote.preco_inicial && lote.preco_inicial > 0;
  const precoDesceu = lote.preco_atual < lote.preco_inicial && lote.preco_inicial > 0;
  const precoEstavel = !precoSubiu && !precoDesceu;

  const precoColor = precoSubiu ? "text-green-500" : precoDesceu ? "text-red-500" : "";

  return (
    <div className="space-y-3">
      {/* Número e status */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-2xl font-bold">Lote {lote.lote_numero}</span>
          {lote.carimbo_vendido && (
            <Badge className="bg-green-500/10 text-green-500">
              <Gavel className="h-3 w-3 mr-1" /> Arrematado
            </Badge>
          )}
        </div>
        <TempoNaPista inicio={lote.inicio} />
      </div>

      {/* Detalhes do animal */}
      <div className="flex flex-wrap gap-2 text-sm">
        <Badge variant="outline">{lote.quantidade}x</Badge>
        {lote.sexo && <Badge variant="outline">{lote.sexo === "macho" ? "Macho" : "Fêmea"}</Badge>}
        {lote.raca && <Badge variant="outline">{lote.raca}</Badge>}
        {lote.idade_meses && <Badge variant="outline">{lote.idade_meses}m</Badge>}
        {lote.condicao && <Badge variant="outline">{lote.condicao}</Badge>}
      </div>

      {/* Preço */}
      <div className="space-y-1">
        <div className={`text-3xl font-bold tracking-tight ${precoColor}`}>
          {formatBRL(lote.preco_atual)}
          {precoSubiu && <ArrowUp className="inline h-5 w-5 ml-1" />}
          {precoDesceu && <ArrowDown className="inline h-5 w-5 ml-1" />}
          {precoEstavel && lote.preco_inicial > 0 && <Minus className="inline h-5 w-5 ml-1 text-muted-foreground" />}
        </div>
        {lote.preco_inicial > 0 && lote.preco_atual !== lote.preco_inicial && (
          <div className="text-xs text-muted-foreground">
            Pedida: {formatBRL(lote.preco_inicial)}
            {precoSubiu && ` → +${formatBRL(lote.preco_atual - lote.preco_inicial).replace("R$ ", "")}`}
          </div>
        )}
      </div>

      {/* Fazenda */}
      {lote.fazenda_vendedor && (
        <div className="text-xs text-muted-foreground">
          Vendedor: {lote.fazenda_vendedor}
        </div>
      )}

      {/* Métricas */}
      <div className="flex gap-4 text-[10px] text-muted-foreground">
        <span>{lote.frames_analisados} frames</span>
        <span>Confiança: {Math.round(lote.confianca_media * 100)}%</span>
        {lote.precos_historico.length > 1 && (
          <span>{new Set(lote.precos_historico).size} preços distintos</span>
        )}
      </div>
    </div>
  );
}
