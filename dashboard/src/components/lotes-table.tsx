import { Fragment, useEffect, useState } from "react";
import { Camera, ChevronDown, ChevronRight, ChevronLeft, X, Play } from "lucide-react";
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

function formatBRL(value: number | null): string {
  if (value === null) return "—";
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function statusBadge(status: string) {
  switch (status) {
    case "arrematado":
      return <Badge className="bg-green-500/10 text-green-500 hover:bg-green-500/20">Arrematado</Badge>;
    case "repescagem":
      return <Badge className="bg-red-500/10 text-red-500 hover:bg-red-500/20">Repescagem</Badge>;
    default:
      return <Badge variant="secondary">Incerto</Badge>;
  }
}

interface LotesTableProps {
  filtros: Filtros;
  onPlayVideo?: (url: string, lote: string) => void;
}

export function LotesTable({ filtros, onPlayVideo }: LotesTableProps) {
  const [lotes, setLotes] = useState<Lote[]>([]);
  const [expandido, setExpandido] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [lightbox, setLightbox] = useState<{ paths: string[]; index: number; lote: string } | null>(null);

  useEffect(() => {
    setLoading(true);
    api.lotes(filtros).then((data) => {
      setLotes(data);
      setLoading(false);
    });
  }, [filtros]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium">
          Últimos lotes ({lotes.length})
        </CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center justify-center h-[200px] text-muted-foreground">
            Carregando...
          </div>
        ) : lotes.length === 0 ? (
          <div className="flex items-center justify-center h-[200px] text-muted-foreground">
            Nenhum lote encontrado com esses filtros
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[30px]" />
                  <TableHead>Data</TableHead>
                  <TableHead>Lote</TableHead>
                  <TableHead className="text-right">Qtd</TableHead>
                  <TableHead>Raça</TableHead>
                  <TableHead>Sexo</TableHead>
                  <TableHead className="text-right">Idade</TableHead>
                  <TableHead>Fazenda</TableHead>
                  <TableHead className="text-right">P. Inicial</TableHead>
                  <TableHead className="text-right">P. Final</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-[30px]" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {lotes.map((lote) => (
                  <Fragment key={lote.id}>
                    <TableRow
                      key={lote.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => setExpandido(expandido === lote.id ? null : lote.id)}
                    >
                      <TableCell>
                        {lote.frame_paths.length > 0 && (
                          expandido === lote.id
                            ? <ChevronDown className="h-4 w-4" />
                            : <ChevronRight className="h-4 w-4" />
                        )}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                        {lote.leilao_data
                          ? new Date(lote.leilao_data).toLocaleDateString("pt-BR")
                          : "—"}
                      </TableCell>
                      <TableCell className="font-mono font-bold">{lote.lote_numero}</TableCell>
                      <TableCell className="text-right">{lote.quantidade}</TableCell>
                      <TableCell>{lote.raca}</TableCell>
                      <TableCell>{lote.sexo === "macho" ? "M" : lote.sexo === "femea" ? "F" : "Misto"}</TableCell>
                      <TableCell className="text-right">
                        {lote.idade_meses ? `${lote.idade_meses}m` : "—"}
                      </TableCell>
                      <TableCell className="max-w-[150px] truncate text-xs">
                        {lote.fazenda_vendedor ?? "—"}
                      </TableCell>
                      <TableCell className="text-right whitespace-nowrap">{formatBRL(lote.preco_inicial)}</TableCell>
                      <TableCell className="text-right whitespace-nowrap font-semibold">{formatBRL(lote.preco_final)}</TableCell>
                      <TableCell>{statusBadge(lote.status)}</TableCell>
                      <TableCell>
                        <div className="flex gap-1.5">
                          {lote.frame_paths.length > 0 && (
                            <Camera className="h-4 w-4 text-muted-foreground" />
                          )}
                          {lote.youtube_url && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                if (onPlayVideo) {
                                  onPlayVideo(lote.youtube_url!, lote.lote_numero);
                                } else {
                                  window.open(lote.youtube_url!, "_blank");
                                }
                              }}
                              title="Ver no YouTube"
                            >
                              <Play className="h-4 w-4 text-red-500 hover:text-red-400 fill-red-500" />
                            </button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>

                    {expandido === lote.id && lote.frame_paths.length > 0 && (
                      <TableRow key={`${lote.id}-frames`}>
                        <TableCell colSpan={12} className="bg-muted/30 p-4">
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
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>

      {/* Video player embutido */}
      {video && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm"
          onClick={() => setVideo(null)}
        >
          <button
            className="absolute top-4 right-4 bg-white/20 hover:bg-white/40 rounded-full p-2 transition-colors z-10"
            onClick={() => setVideo(null)}
          >
            <X className="h-6 w-6 text-white" />
          </button>

          <div className="w-[75vw] max-w-[1200px]" onClick={(e) => e.stopPropagation()}>
            <iframe
              src={video.url.replace("watch?v=", "embed/").replace("&t=", "?start=").replace("s", "")}
              className="w-full aspect-video rounded-lg"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
            />
            <div className="text-center mt-3 text-white text-sm">
              Lote {video.lote}
            </div>
          </div>
        </div>
      )}

      {/* Lightbox fullscreen */}
      {lightbox && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm"
          onClick={() => setLightbox(null)}
        >
          {/* Fechar */}
          <button
            className="absolute top-4 right-4 bg-white/20 hover:bg-white/40 rounded-full p-2 transition-colors z-10"
            onClick={() => setLightbox(null)}
          >
            <X className="h-6 w-6 text-white" />
          </button>

          {/* Imagem */}
          <img
            src={api.frameUrl(lightbox.paths[lightbox.index])}
            alt={`Lote ${lightbox.lote} - foto ${lightbox.index + 1}`}
            className="w-[45vw] max-h-[60vh] object-contain"
            onClick={(e) => e.stopPropagation()}
          />

          {/* Setas */}
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

          {/* Info */}
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-black/60 text-white px-5 py-2 rounded-full text-base">
            Lote {lightbox.lote} — {lightbox.index + 1} / {lightbox.paths.length}
          </div>
        </div>
      )}
    </Card>
  );
}
