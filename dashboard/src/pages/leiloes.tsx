import { useState, useEffect, useCallback, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Loader2, CheckCircle2, XCircle, Trash2, Pencil } from "lucide-react";
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

const STATUS_LABELS: Record<string, string> = {
  iniciando: "Iniciando...",
  baixando: "Obtendo metadados...",
  baixando_video: "Baixando vídeo...",
  extraindo_frames: "Extraindo frames...",
  detectando_mudancas: "Detectando mudanças...",
  analisando_ia: "Analisando com IA...",
  consolidando: "Consolidando lotes...",
  refinando: "Refinando lotes...",
  capturando_arrematacao: "Capturando arrematação...",
  processando: "Processando...",
};

function EditableCell({
  value,
  display,
  onSave,
}: {
  value: string | null;
  display?: string;
  onSave: (v: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const startEdit = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDraft(value ?? "");
    setEditing(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const save = async () => {
    if (draft !== (value ?? "")) {
      await onSave(draft);
    }
    setEditing(false);
  };

  if (editing) {
    return (
      <input
        ref={inputRef}
        className="text-sm w-full bg-transparent border-b border-primary outline-none font-medium"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={save}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          if (e.key === "Enter") save();
          if (e.key === "Escape") setEditing(false);
        }}
      />
    );
  }

  return (
    <span
      className="cursor-pointer hover:text-primary flex items-center gap-1 group"
      onClick={startEdit}
    >
      {display ?? value ?? "—"}
      <Pencil className="h-2.5 w-2.5 opacity-0 group-hover:opacity-50 shrink-0" />
    </span>
  );
}

export function LeiloesPage() {
  const queryClient = useQueryClient();
  const { data: leiloes = [], isLoading: loading } = useQuery({
    queryKey: ["leiloes"],
    queryFn: () => api.leiloes(),
  });
  const [jobs, setJobs] = useState<Job[]>([]);
  const navigate = useNavigate();

  const isFinished = (s: string) => s === "concluido" || s === "erro" || s === "cancelado";
  const activeJobs = jobs.filter((j) => !isFinished(j.status));
  const finishedJobs = jobs.filter((j) => isFinished(j.status));

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

      {/* Jobs ativos e histórico */}
      {(activeJobs.length > 0 || finishedJobs.length > 0) && (
        <Card>
          <CardContent className="pt-4 space-y-3">
            {/* Jobs ativos */}
            {activeJobs.length > 0 && (
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Processando</span>
                  <span className="text-[10px] text-muted-foreground">
                    {activeJobs.length}/{MAX_JOBS} processando
                  </span>
                </div>
                {activeJobs.map((job) => (
                  <div
                    key={job.id}
                    className="flex items-center gap-2 px-2 py-1.5 rounded-md text-xs bg-blue-500/10 text-blue-500"
                  >
                    <Loader2 className="h-3.5 w-3.5 animate-spin shrink-0" />
                    <span className="font-medium">{STATUS_LABELS[job.status] ?? job.status}</span>
                    {job.titulo && (
                      <span className="text-muted-foreground truncate">— {job.titulo}</span>
                    )}
                    {job.batch && (
                      <Badge className="bg-green-500/10 text-green-500 ml-1 text-[9px]">batch</Badge>
                    )}
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
                  </div>
                ))}
              </div>
            )}

            {/* Histórico de jobs finalizados */}
            {finishedJobs.length > 0 && (
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Historico</span>
                  <button
                    className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-red-500 transition-colors"
                    onClick={async () => {
                      await api.limparProcessamentos();
                      pollJobs();
                    }}
                  >
                    <Trash2 className="h-3 w-3" />
                    Limpar
                  </button>
                </div>
                {finishedJobs.map((job) => (
                  <div
                    key={job.id}
                    className={`flex items-center gap-2 px-2 py-1.5 rounded-md text-xs ${
                      job.status === "concluido" ? "bg-green-500/10 text-green-500" :
                      "bg-red-500/10 text-red-500"
                    }`}
                  >
                    {job.status === "concluido" ? (
                      <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                    ) : (
                      <XCircle className="h-3.5 w-3.5 shrink-0" />
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
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

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
                {leiloes.map((leilao) => {
                  const saveLeilao = async (campo: string, valor: string) => {
                    await api.atualizarLeilao(leilao.id, { [campo]: valor });
                    queryClient.invalidateQueries();
                  };
                  return (
                    <TableRow
                      key={leilao.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => navigate(`/leiloes/${leilao.id}`)}
                    >
                      <TableCell className="font-medium max-w-[350px]">
                        <EditableCell
                          value={leilao.titulo}
                          display={formatLeilao(leilao.titulo)}
                          onSave={(v) => saveLeilao("titulo", v)}
                        />
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        <EditableCell
                          value={leilao.canal}
                          display={formatCanal(leilao.canal)}
                          onSave={(v) => saveLeilao("canal_youtube", v)}
                        />
                      </TableCell>
                      <TableCell>
                        <EditableCell
                          value={leilao.local_cidade && leilao.local_estado
                            ? `${leilao.local_cidade}-${leilao.local_estado}`
                            : null}
                          display={leilao.local_cidade && leilao.local_estado
                            ? `${formatCidade(leilao.local_cidade)}-${leilao.local_estado.toUpperCase()}`
                            : "—"}
                          onSave={async (v) => {
                            const parts = v.split("-");
                            const estado = parts.pop()?.trim() ?? "";
                            const cidade = parts.join("-").trim();
                            await api.atualizarLeilao(leilao.id, {
                              local_cidade: cidade,
                              local_estado: estado,
                            });
                            queryClient.invalidateQueries();
                          }}
                        />
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {leilao.total_lotes ?? "—"}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        <EditableCell
                          value={leilao.processado_em
                            ? leilao.processado_em.split("T")[0]
                            : null}
                          display={leilao.processado_em
                            ? new Date(leilao.processado_em).toLocaleDateString("pt-BR")
                            : "—"}
                          onSave={(v) => saveLeilao("data_leilao", v)}
                        />
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
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
