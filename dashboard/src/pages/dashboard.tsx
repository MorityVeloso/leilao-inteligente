import { useState, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { X, Pencil, AlertTriangle, Check } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FiltroBar } from "@/components/filtro-bar";
import { MetricasCards } from "@/components/metricas-cards";
import { TendenciaChart } from "@/components/tendencia-chart";
import { LotesTable } from "@/components/lotes-table";
import { Paineis } from "@/components/paineis";
import { useFiltros } from "@/hooks/use-filtros";
import { api, type Lote } from "@/lib/api";
import { formatBRL, formatLeilao } from "@/lib/format";

function EditablePrice({
  label,
  value,
  onSave,
}: {
  label: string;
  value: number | null;
  onSave: (v: number) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const startEdit = () => {
    setDraft(value != null ? String(value) : "");
    setEditing(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const save = async () => {
    const num = parseFloat(draft.replace(/[^\d.,]/g, "").replace(",", "."));
    if (!isNaN(num) && num > 0) {
      await onSave(num);
    }
    setEditing(false);
  };

  return (
    <div>
      <p className="text-[10px] text-muted-foreground">{label}</p>
      {editing ? (
        <input
          ref={inputRef}
          className="font-bold text-sm w-full bg-transparent border-b border-primary outline-none"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={save}
          onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") setEditing(false); }}
        />
      ) : (
        <p
          className="font-bold text-sm cursor-pointer hover:text-primary flex items-center gap-1 group"
          onClick={startEdit}
        >
          {formatBRL(value)}
          <Pencil className="h-2.5 w-2.5 opacity-0 group-hover:opacity-50" />
        </p>
      )}
    </div>
  );
}

function youtubeEmbedUrl(watchUrl: string): string {
  const url = watchUrl
    .replace("watch?v=", "embed/")
    .replace("&t=", "?start=")
    .replace(/s$/, "");
  return url + (url.includes("?") ? "&autoplay=1" : "?autoplay=1");
}

export function DashboardPage() {
  const { filtros, setFiltro, setFaixaIdade, setFaixaPreco, setFaixaQtd, limpar, tags } = useFiltros();
  const [selectedLote, setSelectedLote] = useState<Lote | null>(null);
  const queryClient = useQueryClient();

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
        {/* Esquerda: Tabela de lotes */}
        <div className="w-[65%] min-w-0">
          <LotesTable filtros={filtros} onSelectLote={setSelectedLote} />
        </div>

        {/* Direita: Video + Dados do lote + Cards + Tendencia + Paineis */}
        <div className="w-[35%] min-w-0 space-y-2 sticky top-4 max-h-[calc(100vh-6rem)] overflow-y-auto p-1">
          {selectedLote && selectedLote.youtube_url && (
            <Card>
              <CardContent className="p-2">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium">Lote {selectedLote.lote_numero}</span>
                  <button onClick={() => setSelectedLote(null)} className="hover:bg-muted rounded p-0.5">
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
                <div className="rounded-lg overflow-hidden">
                  <iframe
                    src={youtubeEmbedUrl(selectedLote.youtube_url)}
                    className="w-full aspect-video"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                    allowFullScreen
                  />
                </div>
              </CardContent>
            </Card>
          )}

          {selectedLote && (
            <Card>
              <CardContent className="p-3 space-y-2">
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <p className="text-[10px] text-muted-foreground">Leilão</p>
                    <p className="font-medium">{selectedLote.leilao_titulo ? formatLeilao(selectedLote.leilao_titulo) : "—"}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-muted-foreground">Quantidade</p>
                    <p className="font-medium">{selectedLote.quantidade} cabeças</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-muted-foreground">Raça / Sexo</p>
                    <p className="font-medium">{selectedLote.raca} {selectedLote.sexo === "macho" ? "M" : "F"}{selectedLote.condicao ? ` ${selectedLote.condicao}` : ""}</p>
                  </div>
                  <div>
                    <p className="text-[10px] text-muted-foreground">Idade</p>
                    <p className="font-medium">{selectedLote.idade_meses ? `${selectedLote.idade_meses} meses` : "—"}</p>
                  </div>
                  <EditablePrice
                    label="Preço Inicial"
                    value={selectedLote.preco_inicial}
                    onSave={async (v) => {
                      await api.atualizarLote(selectedLote.id, { preco_inicial: v });
                      setSelectedLote({ ...selectedLote, preco_inicial: v });
                      queryClient.invalidateQueries({ queryKey: ["lotes"] });
                    }}
                  />
                  <EditablePrice
                    label="Preço Final"
                    value={selectedLote.preco_final}
                    onSave={async (v) => {
                      await api.atualizarLote(selectedLote.id, { preco_final: v });
                      setSelectedLote({ ...selectedLote, preco_final: v });
                      queryClient.invalidateQueries({ queryKey: ["lotes"] });
                    }}
                  />
                  <div>
                    <p className="text-[10px] text-muted-foreground">Status</p>
                    <Select
                      value={selectedLote.status === "arrematado" ? "Arrematado" : selectedLote.status === "repescagem" ? "Repescagem" : "Sem Disputa"}
                      onValueChange={async (v) => {
                        const newStatus = v === "Arrematado" ? "arrematado" : v === "Repescagem" ? "repescagem" : "incerto";
                        await api.atualizarLote(selectedLote.id, { status: newStatus });
                        setSelectedLote({ ...selectedLote, status: newStatus });
                        queryClient.invalidateQueries({ queryKey: ["lotes"] });
                      }}
                    >
                      <SelectTrigger className="h-7 text-[10px] w-[120px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Arrematado">Arrematado</SelectItem>
                        <SelectItem value="Sem Disputa">Sem Disputa</SelectItem>
                        <SelectItem value="Repescagem">Repescagem</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  {selectedLote.fazenda_vendedor && (
                    <div className="col-span-2">
                      <p className="text-[10px] text-muted-foreground">Fazenda</p>
                      <p className="font-medium">{selectedLote.fazenda_vendedor}</p>
                    </div>
                  )}
                  {selectedLote.revisar && (
                    <div className="col-span-2">
                      <button
                        className="flex items-center gap-1.5 px-2 py-1 rounded text-[11px] bg-amber-500/10 text-amber-600 hover:bg-amber-500/20 transition-colors"
                        onClick={async () => {
                          await api.atualizarLote(selectedLote.id, { revisar: false });
                          setSelectedLote({ ...selectedLote, revisar: false });
                          queryClient.invalidateQueries({ queryKey: ["lotes"] });
                        }}
                      >
                        <AlertTriangle className="h-3 w-3" />
                        Pendente revisão — clique para marcar como revisado
                        <Check className="h-3 w-3 ml-auto" />
                      </button>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}

          <MetricasCards filtros={filtros} />
          <TendenciaChart filtros={filtros} />
          <Paineis filtros={filtros} />
        </div>
      </div>
    </div>
  );
}
