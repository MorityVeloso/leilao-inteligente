import { useState } from "react";
import { X } from "lucide-react";
import { FiltroBar } from "@/components/filtro-bar";
import { MetricasCards } from "@/components/metricas-cards";
import { TendenciaChart } from "@/components/tendencia-chart";
import { LotesTable } from "@/components/lotes-table";
import { Paineis } from "@/components/paineis";
import { useFiltros } from "@/hooks/use-filtros";

function youtubeEmbedUrl(watchUrl: string): string {
  const url = watchUrl
    .replace("watch?v=", "embed/")
    .replace("&t=", "?start=")
    .replace(/s$/, "");
  return url + (url.includes("?") ? "&autoplay=1" : "?autoplay=1");
}

export function DashboardPage() {
  const { filtros, setFiltro, setFaixaIdade, setFaixaPreco, setFaixaQtd, limpar, tags } = useFiltros();
  const [video, setVideo] = useState<{ url: string; lote: string } | null>(null);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Análise de preços de gado em leilões
        </p>
      </div>

      <FiltroBar
        filtros={filtros}
        setFiltro={setFiltro}
        setFaixaIdade={setFaixaIdade}
        setFaixaPreco={setFaixaPreco}
        setFaixaQtd={setFaixaQtd}
        limpar={limpar}
        tags={tags}
      />

      <div className="flex gap-4 items-start">
        {/* Esquerda: Tabela de lotes (maior) */}
        <div className="w-[65%] min-w-0">
          <LotesTable filtros={filtros} onPlayVideo={(url, lote) => setVideo({ url, lote })} />
        </div>

        {/* Direita: Video + Cards + Tendencia + Paineis */}
        <div className="w-[35%] min-w-0 space-y-2 sticky top-4 max-h-[calc(100vh-6rem)] overflow-y-auto px-px">
          {video && (
            <div className="rounded-lg border overflow-hidden bg-black">
              <div className="flex items-center justify-between px-3 py-1.5 bg-muted/50">
                <span className="text-xs font-medium">Lote {video.lote}</span>
                <button onClick={() => setVideo(null)} className="hover:bg-muted rounded p-0.5">
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
              <iframe
                src={youtubeEmbedUrl(video.url)}
                className="w-full aspect-video"
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
              />
            </div>
          )}

          <MetricasCards filtros={filtros} />
          <TendenciaChart filtros={filtros} />
          <Paineis filtros={filtros} />
        </div>
      </div>
    </div>
  );
}
