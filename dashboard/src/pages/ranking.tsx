import { Fragment, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, ChevronDown, ChevronRight, Trophy, X } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api, type RankingCategoria, type RankingLeilao } from "@/lib/api";
import { formatBRL, formatLeilao, formatCidade } from "@/lib/format";

interface SelectedLote {
  id: number;
  lote_numero: string;
  quantidade: number;
  preco_final: number | null;
  fazenda_vendedor: string | null;
  status: string;
  youtube_url: string | null;
  leilao_label: string;
}

function leilaoLabel(l: RankingLeilao): string {
  const nome = formatLeilao(l.titulo);
  const local = l.cidade ? formatCidade(l.cidade) : "";
  return local ? `${nome} (${local})` : nome;
}

function categoriaLabel(c: RankingCategoria): string {
  const sexo = c.sexo === "macho" ? "M" : c.sexo === "femea" ? "F" : "Mx";
  const cond = c.condicao ? ` ${c.condicao}` : "";
  return `${c.raca} ${sexo}${cond} ${c.idade_meses}m`;
}

function toEmbedUrl(url: string): string {
  const match = url.match(/[?&]v=([^&]+)/);
  const videoId = match?.[1] ?? "";
  const tMatch = url.match(/[?&]t=(\d+)/);
  const t = tMatch?.[1] ?? "0";
  return `https://www.youtube.com/embed/${videoId}?start=${t}&autoplay=1`;
}

function ExpandedRankingLotes({
  categoria,
  leiloesMap,
  selectedLote,
  onSelectLote,
}: {
  categoria: RankingCategoria;
  leiloesMap: Record<string, RankingLeilao>;
  selectedLote: SelectedLote | null;
  onSelectLote: (lote: SelectedLote | null) => void;
}) {
  const leilaoIds = categoria.precos.map((p) => p.leilao_id).join(",");

  const { data, isLoading } = useQuery({
    queryKey: ["ranking-lotes", leilaoIds, categoria.raca, categoria.sexo, categoria.idade_meses, categoria.condicao],
    queryFn: () =>
      api.rankingLotes({
        leilao_ids: leilaoIds,
        raca: categoria.raca,
        sexo: categoria.sexo,
        idade_meses: categoria.idade_meses,
        condicao: categoria.condicao || undefined,
      }),
  });

  if (isLoading) {
    return <div className="p-3 text-xs text-muted-foreground">Carregando lotes...</div>;
  }

  return (
    <div className="bg-muted/30 px-4 py-3">
      <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${categoria.precos.length}, 1fr)` }}>
        {categoria.precos.map((p, i) => {
          const leilao = leiloesMap[String(p.leilao_id)];
          const lotes = data?.[String(p.leilao_id)] ?? [];
          const isFirst = i === 0;
          const isLast = i === categoria.precos.length - 1 && categoria.precos.length > 1;
          const label = leilao ? leilaoLabel(leilao) : `#${p.leilao_id}`;

          return (
            <div key={p.leilao_id}>
              <p className={`text-[10px] font-medium mb-1.5 ${
                isFirst ? "text-green-500" : isLast ? "text-red-500" : "text-muted-foreground"
              }`}>
                {label} ({lotes.length} lotes)
              </p>
              {lotes.length === 0 ? (
                <p className="text-[10px] text-muted-foreground">Nenhum lote</p>
              ) : (
                <div className="space-y-1">
                  {lotes.map((l, j) => {
                    const isActive = selectedLote?.lote_numero === l.lote_numero && selectedLote?.leilao_label === label;
                    return (
                      <div
                        key={j}
                        className={`flex items-center justify-between text-xs rounded px-2 py-1 bg-background ${
                          isActive ? "ring-1 ring-blue-500" : ""
                        }`}
                      >
                        <div>
                          <span className="font-medium">Lote {l.lote_numero}</span>
                          <span className="text-muted-foreground ml-1.5">{l.quantidade} cab</span>
                          {l.fazenda_vendedor && (
                            <span className="text-muted-foreground ml-1.5">· {l.fazenda_vendedor}</span>
                          )}
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className={`text-[9px] px-1 rounded ${
                            l.status === "arrematado" ? "bg-green-500/10 text-green-600" :
                            l.status === "repescagem" ? "bg-yellow-500/10 text-yellow-600" :
                            "bg-muted text-muted-foreground"
                          }`}>
                            {l.status === "arrematado" ? "Arrematado" : l.status === "repescagem" ? "Repescagem" : "Sem Disputa"}
                          </span>
                          <span className="font-semibold">{formatBRL(l.preco_final)}</span>
                          {l.youtube_url && (
                            <button
                              className={`ml-1 p-0.5 rounded hover:bg-blue-500/20 transition-colors ${
                                isActive ? "text-blue-500 bg-blue-500/10" : "text-muted-foreground hover:text-blue-500"
                              }`}
                              onClick={(e) => {
                                e.stopPropagation();
                                if (isActive) {
                                  onSelectLote(null);
                                } else {
                                  onSelectLote({ ...l, leilao_label: label });
                                }
                              }}
                              title="Ver no vídeo"
                            >
                              <span className="text-[11px]">&#9654;</span>
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function RankingPage() {
  const queryClient = useQueryClient();
  const [dataInicio, setDataInicio] = useState<string>("");
  const [dataFim, setDataFim] = useState<string>("");
  const [estado, setEstado] = useState<string>("");
  const [cidade, setCidade] = useState<string>("");
  const [raca, setRaca] = useState<string>("");
  const [sexo, setSexo] = useState<string>("");
  const [condicao, setCondicao] = useState<string>("");
  const [idadeMin, setIdadeMin] = useState<string>("");
  const [idadeMax, setIdadeMax] = useState<string>("");
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [selectedLote, setSelectedLote] = useState<SelectedLote | null>(null);

  const { data: opcoes } = useQuery({
    queryKey: ["filtros"],
    queryFn: () => api.filtros(),
    staleTime: 60_000,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["ranking", dataInicio, dataFim, estado, cidade, raca, sexo, condicao, idadeMin, idadeMax],
    queryFn: () =>
      api.ranking({
        raca: raca && raca !== "Todas" ? raca : undefined,
        sexo: sexo && sexo !== "Todos" ? sexo.toLowerCase().replace("ê", "e") : undefined,
        condicao: condicao && condicao !== "Todas" ? condicao.toLowerCase() : undefined,
        idade_min: idadeMin ? Number(idadeMin) : undefined,
        idade_max: idadeMax ? Number(idadeMax) : undefined,
        estado: estado && estado !== "Todos" ? estado : undefined,
        cidade: cidade && cidade !== "Todas" ? cidade : undefined,
        data_inicio: dataInicio || undefined,
        data_fim: dataFim || undefined,
      }),
  });

  const categorias = data?.categorias ?? [];
  const leiloesMap = data?.leiloes ?? {};

  const maiorSpread = categorias.length > 0 ? categorias[0] : null;
  const totalCategorias = categorias.length;
  const leiloesEnvolvidos = new Set(categorias.flatMap((c) => c.precos.map((p) => p.leilao_id))).size;

  return (
    <div className="flex gap-4">
      {/* Conteúdo principal */}
      <div className={`space-y-4 ${selectedLote ? "flex-1 min-w-0" : "w-full"}`}>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Ranking de Preços</h1>
          <p className="text-sm text-muted-foreground">
            Identifique onde cada categoria está mais barata e mais cara
          </p>
        </div>

        {/* Linha 1: Período → Estado → Cidade */}
        <div className="flex gap-3 flex-wrap items-end">
          <div className="space-y-1">
            <label className="text-[10px] font-medium text-muted-foreground">Período</label>
            <div className="flex gap-1.5 items-center">
              <Input type="date" value={dataInicio} onChange={(e) => setDataInicio(e.target.value)} className="w-[130px] h-8 text-xs" />
              <span className="text-xs text-muted-foreground">a</span>
              <Input type="date" value={dataFim} onChange={(e) => setDataFim(e.target.value)} className="w-[130px] h-8 text-xs" />
            </div>
          </div>
          <div className="space-y-1">
            <label className="text-[10px] font-medium text-muted-foreground">Estado</label>
            <Select value={estado || "Todos"} onValueChange={(v) => setEstado(v === "Todos" ? "" : v)}>
              <SelectTrigger className="w-[90px] h-8 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="Todos">Todos</SelectItem>
                {opcoes?.estados.map((e) => <SelectItem key={e} value={e}>{e}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <label className="text-[10px] font-medium text-muted-foreground">Cidade</label>
            <Select value={cidade || "Todas"} onValueChange={(v) => setCidade(v === "Todas" ? "" : v)}>
              <SelectTrigger className="w-[140px] h-8 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="Todas">Todas</SelectItem>
                {opcoes?.cidades.map((c) => <SelectItem key={c} value={c}>{formatCidade(c)}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Linha 2: Raça → Sexo → Condição → Idade */}
        <div className="flex gap-3 flex-wrap items-end">
          <div className="space-y-1">
            <label className="text-[10px] font-medium text-muted-foreground">Raça</label>
            <Select value={raca || "Todas"} onValueChange={(v) => setRaca(v === "Todas" ? "" : v)}>
              <SelectTrigger className="w-[120px] h-8 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="Todas">Todas</SelectItem>
                {opcoes?.racas.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <label className="text-[10px] font-medium text-muted-foreground">Sexo</label>
            <Select value={sexo || "Todos"} onValueChange={(v) => setSexo(v === "Todos" ? "" : v)}>
              <SelectTrigger className="w-[100px] h-8 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="Todos">Todos</SelectItem>
                <SelectItem value="Macho">Macho</SelectItem>
                <SelectItem value="Fêmea">Fêmea</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <label className="text-[10px] font-medium text-muted-foreground">Condição</label>
            <Select value={condicao || "Todas"} onValueChange={(v) => setCondicao(v === "Todas" ? "" : v)}>
              <SelectTrigger className="w-[110px] h-8 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="Todas">Todas</SelectItem>
                <SelectItem value="Parida">Parida</SelectItem>
                <SelectItem value="Prenhe">Prenhe</SelectItem>
                <SelectItem value="Solteira">Solteira</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <label className="text-[10px] font-medium text-muted-foreground">Idade (meses)</label>
            <div className="flex items-center gap-1">
              <Input type="number" placeholder="min" value={idadeMin} onChange={(e) => setIdadeMin(e.target.value)} className="w-[70px] h-8 text-xs" />
              <span className="text-[10px] text-muted-foreground">a</span>
              <Input type="number" placeholder="max" value={idadeMax} onChange={(e) => setIdadeMax(e.target.value)} className="w-[70px] h-8 text-xs" />
            </div>
          </div>
        </div>

        {/* Cards resumo */}
        <div className="grid grid-cols-3 gap-2">
          <Card className="py-2">
            <CardContent className="px-3">
              <p className="text-[10px] text-muted-foreground">Maior Oportunidade</p>
              {maiorSpread ? (
                <>
                  <p className="text-sm font-bold">{categoriaLabel(maiorSpread)}</p>
                  <p className="text-xs text-green-500">Spread: {formatBRL(maiorSpread.spread)}</p>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">—</p>
              )}
            </CardContent>
          </Card>
          <Card className="py-2">
            <CardContent className="px-3">
              <p className="text-[10px] text-muted-foreground">Categorias Comparáveis</p>
              <p className="text-sm font-bold">{totalCategorias}</p>
              <p className="text-[10px] text-muted-foreground">com 2+ leilões</p>
            </CardContent>
          </Card>
          <Card className="py-2">
            <CardContent className="px-3">
              <p className="text-[10px] text-muted-foreground">Leilões Envolvidos</p>
              <p className="text-sm font-bold">{leiloesEnvolvidos}</p>
            </CardContent>
          </Card>
        </div>

        {/* Tabela */}
        {isLoading ? (
          <Card>
            <CardContent className="flex items-center justify-center py-20 text-muted-foreground">
              Carregando ranking...
            </CardContent>
          </Card>
        ) : categorias.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-20 text-muted-foreground">
              <Trophy className="h-12 w-12 mb-4 opacity-30" />
              <p className="text-lg font-medium">Sem comparações disponíveis</p>
              <p className="text-sm mt-1">Processe mais leilões ou ajuste os filtros</p>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardContent className="pt-3 px-3">
              <p className="text-[11px] font-medium text-muted-foreground mb-2">
                Ordenado por maior spread (melhores oportunidades primeiro)
              </p>
              <Table className="text-xs">
                <TableHeader>
                  <TableRow className="text-[11px]">
                    <TableHead className="px-2 w-[180px]">Categoria</TableHead>
                    <TableHead className="px-2">Ranking de preços (mais barato → mais caro)</TableHead>
                    <TableHead className="px-2 text-right w-[100px]">Spread</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {categorias.map((c, i) => {
                    const sexoLabel = c.sexo === "macho" ? "M" : c.sexo === "femea" ? "F" : "Mx";
                    const condLabel = c.condicao ? ` ${c.condicao}` : "";
                    const rowKey = `${c.raca}-${c.sexo}-${c.condicao || ""}-${c.idade_meses}`;
                    const isExpanded = expandedRow === rowKey;

                    return (
                      <Fragment key={i}>
                        <TableRow
                          className="cursor-pointer hover:bg-muted/50"
                          onClick={() => setExpandedRow(isExpanded ? null : rowKey)}
                        >
                          <TableCell className="px-2 font-medium align-top py-3">
                            <div className="flex items-center gap-1">
                              {isExpanded
                                ? <ChevronDown className="h-3 w-3 text-muted-foreground shrink-0" />
                                : <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0" />
                              }
                              <div>
                                <div>{c.raca} {sexoLabel}{condLabel}</div>
                                <div className="text-[10px] text-muted-foreground">{c.idade_meses} meses</div>
                              </div>
                            </div>
                          </TableCell>
                          <TableCell className="px-2 py-3">
                            <div className="flex items-center gap-1 flex-wrap">
                              {c.precos.map((p, j) => {
                                const leilao = leiloesMap[String(p.leilao_id)];
                                const isFirst = j === 0;
                                const isLast = j === c.precos.length - 1;
                                return (
                                  <div key={j} className="flex items-center gap-1">
                                    <div className={`rounded px-2 py-1 text-xs ${
                                      isFirst ? "bg-green-500/10 text-green-600 font-semibold"
                                        : isLast && c.precos.length > 1 ? "bg-red-500/10 text-red-500 font-semibold"
                                        : "bg-muted"
                                    }`}>
                                      <div className="font-medium">{formatBRL(p.media)}</div>
                                      <div className="text-[9px] opacity-70">
                                        {leilao ? leilaoLabel(leilao) : `#${p.leilao_id}`}
                                        <span className="ml-1">({p.lotes})</span>
                                      </div>
                                    </div>
                                    {j < c.precos.length - 1 && (
                                      <ArrowRight className="h-3 w-3 text-muted-foreground shrink-0" />
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </TableCell>
                          <TableCell className={`px-2 text-right font-bold align-top py-3 ${c.spread > 0 ? "text-green-500" : ""}`}>
                            {formatBRL(c.spread)}
                          </TableCell>
                        </TableRow>
                        {isExpanded && (
                          <TableRow>
                            <TableCell colSpan={3} className="p-0">
                              <ExpandedRankingLotes
                                categoria={c}
                                leiloesMap={leiloesMap}
                                selectedLote={selectedLote}
                                onSelectLote={setSelectedLote}
                              />
                            </TableCell>
                          </TableRow>
                        )}
                      </Fragment>
                    );
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Painel lateral direito — igual Dashboard */}
      {selectedLote && selectedLote.youtube_url && (
        <div className="w-[35%] shrink-0 sticky top-4 self-start space-y-3 p-1 overflow-y-auto max-h-[calc(100vh-2rem)]">
          <Card>
            <CardContent className="p-2">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-bold">Lote {selectedLote.lote_numero}</p>
                <button
                  onClick={() => setSelectedLote(null)}
                  className="p-0.5 rounded hover:bg-muted transition-colors"
                >
                  <X className="h-4 w-4 text-muted-foreground" />
                </button>
              </div>
              <div className="rounded-lg overflow-hidden">
                <iframe
                  src={toEmbedUrl(selectedLote.youtube_url)}
                  className="w-full aspect-video"
                  allow="autoplay; encrypted-media"
                  allowFullScreen
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-3 space-y-2">
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <p className="text-[10px] text-muted-foreground">Leilão</p>
                  <p className="font-medium">{selectedLote.leilao_label}</p>
                </div>
                <div>
                  <p className="text-[10px] text-muted-foreground">Quantidade</p>
                  <p className="font-medium">{selectedLote.quantidade} cabeças</p>
                </div>
                <div>
                  <p className="text-[10px] text-muted-foreground">Preço Final</p>
                  <p className="font-bold text-sm">{formatBRL(selectedLote.preco_final)}</p>
                </div>
                <div>
                  <p className="text-[10px] text-muted-foreground">Status</p>
                  <Select
                    value={selectedLote.status === "arrematado" ? "Arrematado" : selectedLote.status === "repescagem" ? "Repescagem" : "Sem Disputa"}
                    onValueChange={async (v) => {
                      const newStatus = v === "Arrematado" ? "arrematado" : v === "Repescagem" ? "repescagem" : "incerto";
                      await api.atualizarLote(selectedLote.id, { status: newStatus });
                      setSelectedLote({ ...selectedLote, status: newStatus });
                      queryClient.invalidateQueries({ queryKey: ["ranking-lotes"] });
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
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
