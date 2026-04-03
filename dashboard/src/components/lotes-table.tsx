import { Fragment, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Camera, ChevronDown, ChevronRight, ChevronLeft, X, Play, AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, type Filtros, type Lote } from "@/lib/api";
import { formatLeilao, formatCidade } from "@/lib/format";

function formatBRL(value: number | null): string {
  if (value === null) return "—";
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function statusBadge(status: string) {
  switch (status) {
    case "arrematado":
      return <Badge className="bg-green-500/10 text-green-500 hover:bg-green-500/20 text-[11px]">Arrematado</Badge>;
    case "repescagem":
      return <Badge className="bg-red-500/10 text-red-500 hover:bg-red-500/20 text-[11px]">Repescagem</Badge>;
    default:
      return <Badge variant="secondary" className="text-[11px]">Sem Disputa</Badge>;
  }
}

interface LotesTableProps {
  filtros: Filtros;
  onPlayVideo?: (url: string, lote: string) => void;
  onSelectLote?: (lote: Lote) => void;
}

export function LotesTable({ filtros, onPlayVideo, onSelectLote }: LotesTableProps) {
  const { data: lotesRaw = [], isLoading: loading, isError } = useQuery({
    queryKey: ["lotes", filtros],
    queryFn: () => api.lotes(filtros),
  });
  // Filtro client-side para "pendentes de revisão"
  const lotes = filtros.revisar ? lotesRaw.filter((l) => l.revisar) : lotesRaw;
  const [expandido, setExpandido] = useState<number | null>(null);
  const [lightbox, setLightbox] = useState<{ paths: string[]; index: number; lote: string } | null>(null);

  const totalCols = 13;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium">
          Últimos lotes ({lotes.length})
        </CardTitle>
      </CardHeader>
      <CardContent className="px-0">
        {isError ? (
          <div className="flex items-center justify-center h-[200px] text-sm text-destructive">
            Erro ao carregar lotes
          </div>
        ) : loading ? (
          <div className="flex items-center justify-center h-[200px] text-muted-foreground">
            Carregando...
          </div>
        ) : lotes.length === 0 ? (
          <div className="flex items-center justify-center h-[200px] text-muted-foreground">
            Nenhum lote encontrado com esses filtros
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table className="text-xs">
              <TableHeader>
                <TableRow className="text-[11px]">
                  <TableHead className="w-6 px-2" />
                  <TableHead className="w-20 px-2">Data</TableHead>
                  <TableHead className="w-28 px-2">Leilão</TableHead>
                  <TableHead className="w-20 px-2">Cidade</TableHead>
                  <TableHead className="w-12 px-2">Lote</TableHead>
                  <TableHead className="w-8 px-2 text-right">Qtd</TableHead>
                  <TableHead className="w-28 px-2">Raça</TableHead>
                  <TableHead className="w-8 px-2">Sexo</TableHead>
                  <TableHead className="w-10 px-2 text-right">Idade</TableHead>
                  <TableHead className="w-28 px-2">Fazenda</TableHead>
                  <TableHead className="w-24 px-2 text-right">P. Inicial</TableHead>
                  <TableHead className="w-24 px-2 text-right">P. Final</TableHead>
                  <TableHead className="w-20 px-2">Status</TableHead>
                  <TableHead className="w-12 px-2" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {lotes.map((lote) => {
                  const precoSubiu = lote.preco_inicial != null && lote.preco_final != null && lote.preco_final > lote.preco_inicial;
                  const precoCaiu = lote.preco_inicial != null && lote.preco_final != null && lote.preco_final < lote.preco_inicial;

                  return (
                    <Fragment key={lote.id}>
                      <TableRow
                        className="cursor-pointer hover:bg-muted/50"
                        onClick={() => setExpandido(expandido === lote.id ? null : lote.id)}
                      >
                        <TableCell className="px-2">
                          {lote.frame_paths.length > 0 && (
                            expandido === lote.id
                              ? <ChevronDown className="h-3.5 w-3.5" />
                              : <ChevronRight className="h-3.5 w-3.5" />
                          )}
                        </TableCell>
                        <TableCell className="px-2 text-muted-foreground whitespace-nowrap">
                          {lote.leilao_data
                            ? new Date(lote.leilao_data).toLocaleDateString("pt-BR")
                            : "—"}
                        </TableCell>
                        <TableCell className="px-2 text-muted-foreground truncate max-w-[160px]" title={lote.leilao_titulo ?? ""}>
                          {lote.leilao_titulo
                            ? <>
                                {formatLeilao(lote.leilao_titulo)}
                                {lote.leilao_data && (
                                  <span className="text-[9px] ml-1 opacity-60">
                                    ({new Date(lote.leilao_data).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })})
                                  </span>
                                )}
                              </>
                            : "—"}
                        </TableCell>
                        <TableCell className="px-2 whitespace-nowrap">
                          {lote.local_cidade && lote.local_estado
                            ? `${formatCidade(lote.local_cidade)}-${lote.local_estado.toUpperCase()}`
                            : "—"}
                        </TableCell>
                        <TableCell className="px-2 font-mono font-bold">
                          <span className="flex items-center gap-1">
                            {lote.lote_numero}
                            {lote.revisar && (
                              <AlertTriangle className="h-3 w-3 text-amber-500" title="Pendente de revisão" />
                            )}
                          </span>
                        </TableCell>
                        <TableCell className="px-2 text-right">{lote.quantidade}</TableCell>
                        <TableCell className="px-2">
                          {lote.raca}
                          {lote.condicao === "parida" && (
                            <Badge className="ml-1 text-[9px] px-1 py-0 bg-pink-500/15 text-pink-600 hover:bg-pink-500/25">
                              parida
                            </Badge>
                          )}
                          {lote.condicao === "prenhe" && (
                            <Badge className="ml-1 text-[9px] px-1 py-0 bg-purple-500/15 text-purple-600 hover:bg-purple-500/25">
                              prenhe
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell className="px-2">{lote.sexo === "macho" ? "M" : lote.sexo === "femea" ? "F" : "Mx"}</TableCell>
                        <TableCell className="px-2 text-right">
                          {lote.idade_meses ? `${lote.idade_meses}m` : "—"}
                        </TableCell>
                        <TableCell className="px-2 truncate max-w-[120px]">
                          {lote.fazenda_vendedor ?? "—"}
                        </TableCell>
                        <TableCell className="px-2 text-right whitespace-nowrap text-muted-foreground">
                          {formatBRL(lote.preco_inicial)}
                        </TableCell>
                        <TableCell className={`px-2 text-right whitespace-nowrap font-semibold ${
                          precoCaiu ? "text-red-500" : precoSubiu ? "text-green-600" : ""
                        }`}>
                          {formatBRL(lote.preco_final)}
                        </TableCell>
                        <TableCell className="px-2">{statusBadge(lote.status)}</TableCell>
                        <TableCell className="px-2">
                          <div className="flex gap-1">
                            {lote.frame_paths.length > 0 && (
                              <Camera className="h-3.5 w-3.5 text-muted-foreground" />
                            )}
                            {lote.youtube_url && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  if (onSelectLote) {
                                    onSelectLote(lote);
                                  } else if (onPlayVideo) {
                                    onPlayVideo(lote.youtube_url!, lote.lote_numero);
                                  } else {
                                    window.open(lote.youtube_url!, "_blank");
                                  }
                                }}
                                title="Ver no YouTube"
                              >
                                <Play className="h-3.5 w-3.5 text-red-500 hover:text-red-400 fill-red-500" />
                              </button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>

                      {expandido === lote.id && lote.frame_paths.length > 0 && (
                        <TableRow key={`${lote.id}-frames`}>
                          <TableCell colSpan={totalCols + 1} className="bg-muted/30 p-4">
                            <div className="flex gap-3 overflow-x-auto">
                              {lote.frame_paths.map((path, i) => (
                                <img
                                  key={i}
                                  src={api.frameUrl(path)}
                                  alt={`Lote ${lote.lote_numero} - foto ${i + 1}`}
                                  className="h-[150px] rounded-lg border object-cover cursor-pointer hover:opacity-80 transition-opacity"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setLightbox({ paths: lote.frame_paths, index: i, lote: lote.lote_numero });
                                  }}
                                />
                              ))}
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>

      {/* Lightbox fullscreen */}
      {lightbox && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm"
          onClick={() => setLightbox(null)}
        >
          <button
            className="absolute top-4 right-4 bg-white/20 hover:bg-white/40 rounded-full p-2 transition-colors z-10"
            onClick={() => setLightbox(null)}
          >
            <X className="h-6 w-6 text-white" />
          </button>

          <img
            src={api.frameUrl(lightbox.paths[lightbox.index])}
            alt={`Lote ${lightbox.lote} - foto ${lightbox.index + 1}`}
            className="w-[45vw] max-h-[60vh] object-contain"
            onClick={(e) => e.stopPropagation()}
          />

          {lightbox.paths.length > 1 && (
            <>
              <button
                className="absolute left-4 top-1/2 -translate-y-1/2 bg-white/20 hover:bg-white/40 rounded-full p-3 transition-colors"
                onClick={(e) => {
                  e.stopPropagation();
                  setLightbox({
                    ...lightbox,
                    index: (lightbox.index - 1 + lightbox.paths.length) % lightbox.paths.length,
                  });
                }}
              >
                <ChevronLeft className="h-8 w-8 text-white" />
              </button>
              <button
                className="absolute right-4 top-1/2 -translate-y-1/2 bg-white/20 hover:bg-white/40 rounded-full p-3 transition-colors"
                onClick={(e) => {
                  e.stopPropagation();
                  setLightbox({
                    ...lightbox,
                    index: (lightbox.index + 1) % lightbox.paths.length,
                  });
                }}
              >
                <ChevronRight className="h-8 w-8 text-white" />
              </button>
            </>
          )}

          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-black/60 text-white px-5 py-2 rounded-full text-base">
            Lote {lightbox.lote} — {lightbox.index + 1} / {lightbox.paths.length}
          </div>
        </div>
      )}
    </Card>
  );
}
