import { useState, useEffect, useRef, useCallback } from "react";
import { Radio, Play, Pause, Square, Link, AlertCircle, Settings2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import type { LoteAoVivo, EventoAoVivo, ComparacaoResponse } from "@/lib/api";
import { formatBRL } from "@/lib/format";
import { TaxaArrematacao } from "@/components/taxa-arrematacao";
import { ComparacaoCamadas } from "@/components/comparacao-camadas";
import { LoteAoVivoPanel } from "@/components/lote-ao-vivo";

type Status = "desconectado" | "conectando" | "conectado" | "analisando" | "pausado" | "encerrando" | "encerrado" | "erro";

const STATUS_LABELS: Record<string, string> = {
  desconectado: "Aguardando URL",
  conectando: "Validando stream...",
  conectado: "Conectado — pronto para iniciar",
  analisando: "Analisando ao vivo",
  pausado: "Pausado",
  encerrando: "Encerrando...",
  encerrado: "Encerrado",
  erro: "Erro",
};

const STATUS_COLORS: Record<string, string> = {
  desconectado: "bg-muted text-muted-foreground",
  conectando: "bg-yellow-500/10 text-yellow-500",
  conectado: "bg-blue-500/10 text-blue-500",
  analisando: "bg-green-500/10 text-green-500",
  pausado: "bg-yellow-500/10 text-yellow-500",
  encerrado: "bg-muted text-muted-foreground",
  erro: "bg-red-500/10 text-red-500",
};

export function AoVivoPage() {
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState<Status>("desconectado");
  const [erro, setErro] = useState<string | null>(null);
  const [videoId, setVideoId] = useState<string | null>(null);
  const [titulo, setTitulo] = useState("");
  const [canal, setCanal] = useState("");
  const [temCalibracao, setTemCalibracao] = useState(false);
  const [loteAtual, setLoteAtual] = useState<LoteAoVivo | null>(null);
  const [lotesFinalizados, setLotesFinalizados] = useState<LoteAoVivo[]>([]);
  const [comparacao, setComparacao] = useState<ComparacaoResponse | null>(null);
  const [nLeiloes, setNLeiloes] = useState(5);
  const [frameCount, setFrameCount] = useState(0);

  const eventSourceRef = useRef<EventSource | null>(null);
  const comparacaoTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Buscar comparação quando lote atualiza
  const fetchComparacao = useCallback(async () => {
    try {
      const data = await api.aoVivoComparacao({ n_leiloes: nLeiloes });
      setComparacao(data);
    } catch {
      // Silenciar — comparação é opcional
    }
  }, [nLeiloes]);

  // Conectar ao stream SSE
  const conectarSSE = useCallback(() => {
    const es = new EventSource(api.aoVivoEventosUrl());

    es.onmessage = (event) => {
      const evt: EventoAoVivo = JSON.parse(event.data);

      switch (evt.tipo) {
        case "lote_atualizado":
          if (evt.lote) {
            setLoteAtual(evt.lote);
            // Buscar comparação a cada atualização (debounced)
            if (comparacaoTimerRef.current) clearTimeout(comparacaoTimerRef.current);
            comparacaoTimerRef.current = setTimeout(fetchComparacao, 500);
          }
          if (evt.frame) setFrameCount(evt.frame);
          break;

        case "novo_lote":
          setComparacao(null); // Limpar comparação do lote anterior
          break;

        case "lote_finalizado":
          if (evt.lote) {
            setLotesFinalizados((prev) => [evt.lote!, ...prev]);
          }
          break;

        case "frame_sem_dados":
          if (evt.frame) setFrameCount(evt.frame);
          break;

        case "erro":
          setErro(evt.mensagem || "Erro desconhecido");
          break;

        case "sessao_encerrada":
        case "fim":
          setStatus("encerrado");
          es.close();
          break;

        case "heartbeat":
          break;
      }
    };

    es.onerror = () => {
      // SSE reconecta automaticamente
    };

    eventSourceRef.current = es;
  }, [fetchComparacao]);

  // Cleanup SSE on unmount
  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
      if (comparacaoTimerRef.current) clearTimeout(comparacaoTimerRef.current);
    };
  }, []);

  // Handlers
  async function handleConectar() {
    if (!url.trim()) return;
    setStatus("conectando");
    setErro(null);

    try {
      const data = await api.aoVivoConectar(url.trim());
      if (data.erro) {
        setErro(data.erro);
        setStatus("erro");
        return;
      }
      setVideoId(data.video_id);
      setTitulo(data.titulo);
      setCanal(data.canal);
      setTemCalibracao(data.tem_calibracao);
      setStatus("conectado");
    } catch (e) {
      setErro(String(e));
      setStatus("erro");
    }
  }

  async function handleIniciar() {
    try {
      await api.aoVivoIniciar();
      setStatus("analisando");
      conectarSSE();
    } catch (e) {
      setErro(String(e));
    }
  }

  async function handlePausar() {
    await api.aoVivoPausar();
    setStatus("pausado");
  }

  async function handleRetomar() {
    await api.aoVivoRetomar();
    setStatus("analisando");
  }

  async function handleEncerrar() {
    setStatus("encerrando");
    eventSourceRef.current?.close();
    try {
      const data = await api.aoVivoEncerrar();
      setStatus("encerrado");
      if (data.leilao_id) {
        setErro(null);
      }
    } catch (e) {
      setErro(String(e));
      setStatus("erro");
    }
  }

  // Estatísticas acumuladas
  const totalLotes = lotesFinalizados.length + (loteAtual ? 1 : 0);
  const arrematados = lotesFinalizados.filter((l) => l.status === "arrematado").length;
  const mediaPreco = lotesFinalizados.length > 0
    ? lotesFinalizados.reduce((s, l) => s + l.preco_atual, 0) / lotesFinalizados.length
    : 0;

  const isAnalisando = status === "analisando" || status === "pausado";

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Radio className={`h-5 w-5 ${status === "analisando" ? "text-green-500 animate-pulse" : "text-muted-foreground"}`} />
            {titulo || "Ao Vivo"}
          </h1>
          {canal && <p className="text-sm text-muted-foreground">{canal}</p>}
        </div>
        <div className="flex items-center gap-2">
          <Badge className={STATUS_COLORS[status] || ""}>{STATUS_LABELS[status]}</Badge>
          {isAnalisando && (
            <span className="text-xs text-muted-foreground">Frame #{frameCount}</span>
          )}
        </div>
      </div>

      {/* Conexão — Input URL */}
      {status === "desconectado" || status === "erro" ? (
        <Card>
          <CardContent className="pt-6">
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Link className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Cole a URL do YouTube ao vivo..."
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleConectar()}
                  className="pl-10"
                />
              </div>
              <Button onClick={handleConectar} disabled={!url.trim()}>
                Conectar
              </Button>
            </div>
            {erro && (
              <div className="flex items-center gap-2 mt-3 text-sm text-red-500">
                <AlertCircle className="h-4 w-4" /> {erro}
              </div>
            )}
          </CardContent>
        </Card>
      ) : null}

      {/* Conectado — Player + Botão Iniciar */}
      {status === "conectado" && (
        <div className="space-y-4">
          {!temCalibracao && (
            <div className="flex items-center gap-2 p-3 rounded-md bg-yellow-500/10 text-yellow-600 text-sm">
              <AlertCircle className="h-4 w-4 shrink-0" />
              Canal sem calibração. A análise usará prompt genérico (menos preciso). Considere calibrar antes com /calibrar.
            </div>
          )}
          <div className="flex justify-center">
            <Button size="lg" onClick={handleIniciar} className="gap-2">
              <Play className="h-5 w-5" /> Iniciar Análise
            </Button>
          </div>
        </div>
      )}

      {/* Analisando — Layout principal */}
      {isAnalisando || status === "encerrado" ? (
        <div className="grid grid-cols-12 gap-4">

          {/* Coluna esquerda: Player + Taxa + Comparações */}
          <div className="col-span-7 space-y-4">

            {/* Player YouTube */}
            {videoId && (
              <div className="aspect-video rounded-lg overflow-hidden bg-black">
                <iframe
                  src={`https://www.youtube.com/embed/${videoId}?autoplay=1&mute=1`}
                  className="w-full h-full"
                  allow="autoplay; encrypted-media"
                  allowFullScreen
                />
              </div>
            )}

            {/* Botões de controle */}
            {status !== "encerrado" && (
              <div className="flex gap-2">
                {status === "analisando" ? (
                  <Button variant="outline" size="sm" onClick={handlePausar} className="gap-1">
                    <Pause className="h-3 w-3" /> Pausar
                  </Button>
                ) : status === "pausado" ? (
                  <Button variant="outline" size="sm" onClick={handleRetomar} className="gap-1">
                    <Play className="h-3 w-3" /> Retomar
                  </Button>
                ) : null}
                <Button variant="destructive" size="sm" onClick={handleEncerrar} className="gap-1">
                  <Square className="h-3 w-3" /> Encerrar
                </Button>
                <div className="flex-1" />
                <div className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Settings2 className="h-3 w-3" />
                  <span>Comparar últimos</span>
                  <Input
                    type="number"
                    value={nLeiloes}
                    onChange={(e) => setNLeiloes(Number(e.target.value) || 5)}
                    className="w-14 h-6 text-xs text-center"
                    min={1}
                    max={50}
                  />
                  <span>leilões</span>
                </div>
              </div>
            )}

            {/* Taxa de Arrematação */}
            {comparacao && comparacao.comparacoes.length > 0 && (
              <Card>
                <CardHeader className="pb-2 pt-4 px-4">
                  <CardTitle className="text-sm">Taxa de Arrematação</CardTitle>
                </CardHeader>
                <CardContent className="px-4 pb-4">
                  <TaxaArrematacao
                    faixas={comparacao.comparacoes[comparacao.comparacoes.length - 1].taxa_faixas}
                    faixaAtual={comparacao.comparacoes[comparacao.comparacoes.length - 1].faixa_atual}
                  />
                </CardContent>
              </Card>
            )}

            {/* Comparações Multicamada */}
            {comparacao && comparacao.comparacoes.length > 0 && (
              <Card>
                <CardHeader className="pb-2 pt-4 px-4">
                  <CardTitle className="text-sm">
                    Comparações — {comparacao.perfil.raca} {comparacao.perfil.sexo} {comparacao.perfil.idade_meses}m
                  </CardTitle>
                </CardHeader>
                <CardContent className="px-4 pb-4">
                  <ComparacaoCamadas
                    camadas={comparacao.comparacoes}
                    precoAtual={comparacao.perfil.preco_atual}
                  />
                </CardContent>
              </Card>
            )}
          </div>

          {/* Coluna direita: Lote Atual + Histórico */}
          <div className="col-span-5 space-y-4">

            {/* Lote Atual */}
            <Card>
              <CardHeader className="pb-2 pt-4 px-4">
                <CardTitle className="text-sm">Lote Atual</CardTitle>
              </CardHeader>
              <CardContent className="px-4 pb-4">
                {loteAtual ? (
                  <LoteAoVivoPanel lote={loteAtual} />
                ) : (
                  <div className="text-sm text-muted-foreground text-center py-8">
                    Aguardando primeiro lote...
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Estatísticas da Sessão */}
            <Card>
              <CardContent className="pt-4 px-4 pb-4">
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div>
                    <div className="text-lg font-bold">{totalLotes}</div>
                    <div className="text-[10px] text-muted-foreground">Lotes</div>
                  </div>
                  <div>
                    <div className="text-lg font-bold text-green-500">{arrematados}</div>
                    <div className="text-[10px] text-muted-foreground">Arrematados</div>
                  </div>
                  <div>
                    <div className="text-lg font-bold">{mediaPreco > 0 ? formatBRL(mediaPreco) : "—"}</div>
                    <div className="text-[10px] text-muted-foreground">Média</div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Histórico */}
            <Card className="max-h-[400px] overflow-y-auto">
              <CardHeader className="pb-2 pt-4 px-4 sticky top-0 bg-card z-10">
                <CardTitle className="text-sm">Histórico ({lotesFinalizados.length})</CardTitle>
              </CardHeader>
              <CardContent className="px-4 pb-4">
                {lotesFinalizados.length === 0 ? (
                  <div className="text-xs text-muted-foreground text-center py-4">
                    Lotes finalizados aparecerão aqui
                  </div>
                ) : (
                  <div className="space-y-1">
                    {lotesFinalizados.map((l, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-2 text-xs py-1 border-b last:border-0"
                      >
                        <span className="font-medium w-8 shrink-0">#{l.lote_numero}</span>
                        <span className="text-muted-foreground truncate flex-1">
                          {l.quantidade}x {l.raca || "?"} {l.sexo === "macho" ? "M" : "F"}
                        </span>
                        <span className="font-medium shrink-0">{formatBRL(l.preco_atual)}</span>
                        <Badge
                          variant="outline"
                          className={`text-[9px] px-1 shrink-0 ${
                            l.status === "arrematado"
                              ? "border-green-500 text-green-500"
                              : "border-muted-foreground text-muted-foreground"
                          }`}
                        >
                          {l.status === "arrematado" ? "Arr" : l.status === "incerto" ? "?" : l.status}
                        </Badge>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      ) : null}
    </div>
  );
}
