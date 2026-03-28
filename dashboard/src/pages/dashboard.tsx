import { FiltroBar } from "@/components/filtro-bar";
import { MetricasCards } from "@/components/metricas-cards";
import { TendenciaChart } from "@/components/tendencia-chart";
import { LotesTable } from "@/components/lotes-table";
import { Paineis } from "@/components/paineis";
import { useFiltros } from "@/hooks/use-filtros";

export function DashboardPage() {
  const { filtros, setFiltro, setFaixaIdade, limpar, tags } = useFiltros();

  return (
    <div className="space-y-6">
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
        limpar={limpar}
        tags={tags}
      />

      <MetricasCards filtros={filtros} />

      <TendenciaChart filtros={filtros} />

      <Paineis filtros={filtros} />

      <LotesTable filtros={filtros} />
    </div>
  );
}
