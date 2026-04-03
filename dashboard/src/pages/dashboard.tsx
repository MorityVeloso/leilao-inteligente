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

function EditableField({
  label,
  value,
  display,
  onSave,
  bold,
}: {
  label: string;
  value: string | number | null;
  display?: string;
  onSave: (v: string) => Promise<void>;
  bold?: boolean;
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
    if (draft !== String(value ?? "")) {
      await onSave(draft);
    }
    setEditing(false);
  };

  return (
    <div>
      <p className="text-[10px] text-muted-foreground">{label}</p>
      {editing ? (
        <input
          ref={inputRef}
          className={`text-sm w-full bg-transparent border-b border-primary outline-none ${bold ? "font-bold" : "font-medium"}`}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={save}
          onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") setEditing(false); }}
        />
      ) : (
        <p
          className={`text-sm cursor-pointer hover:text-primary flex items-center gap-1 group ${bold ? "font-bold" : "font-medium"}`}
          onClick={startEdit}
        >
          {display ?? (value != null ? String(value) : "—")}
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

          {selectedLote && (() => {
            const save = async (campo: string, valor: string) => {
              const numFields = ["quantidade", "idade_meses", "preco_inicial", "preco_final"];
              const parsed = numFields.includes(campo) ? parseFloat(valor.replace(/[^\d.,]/g, "").replace(",", ".")) : valor;
              await api.atualizarLote(selectedLote.id, { [campo]: parsed } as Record<string, unknown>);
              setSelectedLote({ ...selectedLote, [campo]: parsed });
              queryClient.invalidateQueries({ queryKey: ["lotes"] });
            };
            return (
            <Card>
              <CardContent className="p-3 space-y-2">
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <p className="text-[10px] text-muted-foreground">Leilão</p>
                    <p className="font-medium">{selectedLote.leilao_titulo ? formatLeilao(selectedLote.leilao_titulo) : "—"}</p>
                  </div>
                  <EditableField label="Lote" value={selectedLote.lote_numero} bold onSave={(v) => save("lote_numero", v)} />
                  <EditableField label="Quantidade" value={selectedLote.quantidade} display={`${selectedLote.quantidade} cab.`} onSave={(v) => save("quantidade", v)} />
                  <EditableField label="Raça" value={selectedLote.raca} onSave={(v) => save("raca", v)} />
                  <EditableField label="Sexo" value={selectedLote.sexo} onSave={(v) => save("sexo", v)} />
                  <EditableField label="Idade (meses)" value={selectedLote.idade_meses} display={selectedLote.idade_meses ? `${selectedLote.idade_meses}m` : "—"} onSave={(v) => save("idade_meses", v)} />
                  <EditableField label="Preço Inicial" value={selectedLote.preco_inicial} display={formatBRL(selectedLote.preco_inicial)} bold onSave={(v) => save("preco_inicial", v)} />
                  <EditableField label="Preço Final" value={selectedLote.preco_final} display={formatBRL(selectedLote.preco_final)} bold onSave={(v) => save("preco_final", v)} />
                  <div>
                    <p className="text-[10px] text-muted-foreground">Status</p>
                    <Select
                      value={selectedLote.status === "arrematado" ? "Arrematado" : selectedLote.status === "repescagem" ? "Repescagem" : "Sem Disputa"}
                      onValueChange={async (v) => {
                        const newStatus = v === "Arrematado" ? "arrematado" : v === "Repescagem" ? "repescagem" : "incerto";
                        await save("status", newStatus);
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
                  <div className="col-span-2">
                    <EditableField label="Fazenda" value={selectedLote.fazenda_vendedor} onSave={(v) => save("fazenda_vendedor", v)} />
                  </div>
                  <EditableField label="Condição" value={selectedLote.condicao} onSave={(v) => save("condicao", v)} />
                  <div className="col-span-2">
                    <button
                      className={`flex items-center gap-1.5 w-full px-2 py-1 rounded text-[11px] transition-colors ${
                        selectedLote.revisar
                          ? "bg-amber-500/10 text-amber-600 hover:bg-amber-500/20"
                          : "bg-green-500/10 text-green-600 hover:bg-green-500/20"
                      }`}
                      onClick={async () => {
                        const novoValor = !selectedLote.revisar;
                        await api.atualizarLote(selectedLote.id, { revisar: novoValor });
                        setSelectedLote({ ...selectedLote, revisar: novoValor });
                        queryClient.invalidateQueries({ queryKey: ["lotes"] });
                      }}
                    >
                      {selectedLote.revisar ? (
                        <>
                          <AlertTriangle className="h-3 w-3" />
                          Pendente revisão — clique para marcar como revisado
                          <Check className="h-3 w-3 ml-auto" />
                        </>
                      ) : (
                        <>
                          <Check className="h-3 w-3" />
                          Revisado — clique para marcar para revisão
                          <AlertTriangle className="h-3 w-3 ml-auto" />
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </CardContent>
            </Card>
            );
          })()}

          <MetricasCards filtros={filtros} />
          <TendenciaChart filtros={filtros} />
          <Paineis filtros={filtros} />
        </div>
      </div>
    </div>
  );
}
