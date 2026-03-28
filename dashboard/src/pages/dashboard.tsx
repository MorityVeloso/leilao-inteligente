import { FiltroBar } from "@/components/filtro-bar";
import { MetricasCards } from "@/components/metricas-cards";
import { TendenciaChart } from "@/components/tendencia-chart";
import { LotesTable } from "@/components/lotes-table";
import { Paineis } from "@/components/paineis";
import { useFiltros } from "@/hooks/use-filtros";

export function DashboardPage() {
  const { filtros, setFiltro, setFaixaIdade, setFaixaPreco, setFaixaQtd, limpar, tags } = useFiltros();

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Analise de precos de gado em leiloes
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

      <div className="flex gap-4">
        {/* Esquerda: Tabela de lotes (maior) */}
        <div className="w-[58%] min-w-0">
          <LotesTable filtros={filtros} />
        </div>

        {/* Direita: Cards + Tendencia + Paineis */}
        <div className="w-[42%] min-w-0 space-y-4">
          <MetricasCards filtros={filtros} />
          <TendenciaChart filtros={filtros} />
          <Paineis filtros={filtros} />
        </div>
      </div>
    </div>
  );
}
