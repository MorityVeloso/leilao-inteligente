import { useState, useEffect, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Play, MapPin, Loader2, CheckCircle2, XCircle, Zap, Clock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { api } from "@/lib/api";
import { formatLeilao, formatCidade, formatCanal } from "@/lib/format";

interface Job {
  id: string;
  status: string;
  titulo: string | null;
  lotes: number | null;
  erro: string | null;
  batch: boolean;
}

const MAX_JOBS = 5;

export function LeiloesPage() {
  const queryClient = useQueryClient();
  const { data: leiloes = [], isLoading: loading } = useQuery({
    queryKey: ["leiloes"],
    queryFn: () => api.leiloes(),
  });
  const [url, setUrl] = useState("");
  const [batch, setBatch] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]);
  const navigate = useNavigate();

  const activeJobs = jobs.filter((j) => j.status !== "concluido" && j.status !== "erro" && j.status !== "cancelado");
  const canSubmit = url.trim() && activeJobs.length < MAX_JOBS;

  // Polling de todos os jobs ativos
  const pollJobs = useCallback(async () => {
    try {
      const data = await api.processarAtivos();
      const jobList: Job[] = Object.entries(data).map(([id, j]) => ({
        id,
        status: j.status,
        titulo: j.titulo,
        lotes: j.lotes,
        erro: j.erro,
        batch: j.batch,
      }));

      setJobs(jobList);

      const temAtivo = jobList.some((j) => j.status !== "concluido" && j.status !== "erro" && j.status !== "cancelado");
      if (temAtivo) {
        setTimeout(pollJobs, 3000);
      } else {
        queryClient.invalidateQueries({ queryKey: ["leiloes"] });
        queryClient.invalidateQueries({ queryKey: ["filtros"] });
      }
    } catch {
      setTimeout(pollJobs, 5000);
    }
  }, [queryClient]);

  // Ao carregar, verificar jobs existentes
  useEffect(() => {
    pollJobs();
  }, [pollJobs]);

  const handleProcessar = async () => {
    if (!canSubmit) return;
    try {
      await api.processar(url.trim(), batch);
      setUrl("");
      pollJobs();
    } catch (e) {
      console.error("Erro ao iniciar processamento:", e);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Leilões</h1>
          <p className="text-sm text-muted-foreground">
            Leilões processados e novos processamentos
          </p>
        </div>
      </div>

      {/* Processar novo */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">Processar novo leilão</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Input
              placeholder="Cole a URL do YouTube (ex: https://www.youtube.com/live/...)"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="flex-1"
            />
            <Button
              onClick={handleProcessar}
              disabled={!canSubmit}
            >
              <Play className="h-4 w-4 mr-2" />
              Processar
            </Button>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setBatch(!batch)}
                className={`
                  relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent
                  transition-colors duration-200 ease-in-out focus-visible:outline-none focus-visible:ring-2
                  focus-visible:ring-ring
                  ${batch ? "bg-green-600" : "bg-muted"}
                `}
              >
                <span
                  className={`
                    pointer-events-none inline-block h-4 w-4 transform rounded-full bg-background shadow-lg
                    ring-0 transition duration-200 ease-in-out
                    ${batch ? "translate-x-4" : "translate-x-0"}
                  `}
                />
              </button>
              <div className="flex items-center gap-1.5">
                {batch ? (
                  <Clock className="h-3.5 w-3.5 text-green-500" />
                ) : (
                  <Zap className="h-3.5 w-3.5 text-yellow-500" />
                )}
                <span className="text-xs text-muted-foreground">
                  {batch ? (
                    <><span className="font-medium text-green-500">Batch</span> — 50% mais barato, pode levar horas (vídeos gravados)</>
                  ) : (
                    <><span className="font-medium text-yellow-500">Online</span> — processamento em tempo real (~10 min/leilão)</>
                  )}
                </span>
              </div>
            </div>
            {activeJobs.length > 0 && (
              <span className="text-[10px] text-muted-foreground">
                {activeJobs.length}/{MAX_JOBS} processando
              </span>
            )}
          </div>

          {/* Lista de jobs */}
          {jobs.length > 0 && (
            <div className="space-y-1.5">
              {jobs.map((job) => (
                <div
                  key={job.id}
                  className={`flex items-center gap-2 px-2 py-1.5 rounded-md text-xs ${
                    job.status === "concluido" ? "bg-green-500/10 text-green-500" :
                    job.status === "erro" || job.status === "cancelado" ? "bg-red-500/10 text-red-500" :
                    "bg-blue-500/10 text-blue-500"
                  }`}
                >
                  {job.status === "concluido" ? (
                    <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                  ) : job.status === "erro" || job.status === "cancelado" ? (
                    <XCircle className="h-3.5 w-3.5 shrink-0" />
                  ) : (
                    <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0" />
                  )}
                  <span className="font-medium capitalize">{job.status}</span>
                  {job.titulo && (
                    <span className="text-muted-foreground truncate">— {job.titulo}</span>
                  )}
                  {job.status === "concluido" && job.lotes != null && (
                    <span className="font-medium ml-auto shrink-0">{job.lotes} lotes</span>
                  )}
                  {job.status === "erro" && job.erro && (
                    <span className="truncate ml-auto">{job.erro}</span>
                  )}
                  {job.batch && (
                    <Badge className="bg-green-500/10 text-green-500 ml-1 text-[9px]">batch</Badge>
                  )}
                  {job.status !== "concluido" && job.status !== "erro" && job.status !== "cancelado" && (
                    <button
                      className="ml-auto shrink-0 p-0.5 rounded hover:bg-red-500/20 transition-colors text-muted-foreground hover:text-red-500"
                      onClick={async () => {
                        await api.cancelarProcessamento(job.id);
                        pollJobs();
                      }}
                      title="Cancelar"
                    >
                      <XCircle className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Lista */}
      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-medium">
            Leilões processados ({leiloes.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center h-[200px] text-muted-foreground">
              Carregando...
            </div>
          ) : leiloes.length === 0 ? (
            <div className="flex items-center justify-center h-[200px] text-muted-foreground">
              Nenhum leilão processado ainda
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Titulo</TableHead>
                  <TableHead>Canal</TableHead>
                  <TableHead>Local</TableHead>
                  <TableHead className="text-right">Lotes</TableHead>
                  <TableHead>Data</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {leiloes.map((leilao) => (
                  <TableRow
                    key={leilao.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => navigate(`/leiloes/${leilao.id}`)}
                  >
                    <TableCell className="font-medium max-w-[350px] truncate">
                      {formatLeilao(leilao.titulo)}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatCanal(leilao.canal)}
                    </TableCell>
                    <TableCell>
                      {leilao.local_cidade && leilao.local_estado ? (
                        <span className="flex items-center gap-1 text-sm">
                          <MapPin className="h-3 w-3" />
                          {formatCidade(leilao.local_cidade)}-{leilao.local_estado.toUpperCase()}
                        </span>
                      ) : (
                        "—"
                      )}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {leilao.total_lotes ?? "—"}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {leilao.processado_em
                        ? new Date(leilao.processado_em).toLocaleDateString("pt-BR")
                        : "—"}
                    </TableCell>
                    <TableCell>
                      <Badge
                        className={
                          leilao.status === "completo"
                            ? "bg-green-500/10 text-green-500"
                            : "bg-yellow-500/10 text-yellow-500"
                        }
                      >
                        {leilao.status}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
