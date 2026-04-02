import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CalendarDays, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api, type Filtros } from "@/lib/api";

function limparTituloLeilao(titulo: string): string {
  return titulo
    .replace(/LEIL[ÃA]O\s*/gi, "")
    .replace(/\bLIVE\b/gi, "")
    .replace(/\bLEILOEIRO\b/gi, "")
    .replace(/\d{2}\/\d{2}\/\d{4}/g, "")
    .replace(/\b(JENILSON|ROCHA)\b/gi, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

interface FiltroBarProps {
  filtros: Filtros;
  setFiltro: <K extends keyof Filtros>(key: K, value: Filtros[K]) => void;
  setFaixaIdade: (min?: number, max?: number) => void;
  setFaixaPreco: (min?: number, max?: number) => void;
  setFaixaQtd: (min?: number, max?: number) => void;
  limpar: () => void;
  tags: { key: keyof Filtros; label: string }[];
}

function PeriodoPersonalizado({
  dataInicio,
  dataFim,
  onAplicar,
}: {
  dataInicio?: string;
  dataFim?: string;
  onAplicar: (inicio: string, fim: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [inicio, setInicio] = useState(dataInicio ?? "");
  const [fim, setFim] = useState(dataFim ?? "");

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger
        render={
          <button className="flex items-center gap-1 h-8 px-2 rounded-md border text-xs text-muted-foreground hover:bg-muted transition-colors">
            <CalendarDays className="h-3.5 w-3.5" />
          </button>
        }
      />
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Período personalizado</DialogTitle>
          <DialogDescription>Selecione a data inicial e final</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-4 py-2">
          <div className="space-y-1.5">
            <label className="text-xs font-medium">Data inicial</label>
            <Input
              type="date"
              value={inicio}
              onChange={(e) => setInicio(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium">Data final</label>
            <Input
              type="date"
              value={fim}
              onChange={(e) => setFim(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            size="sm"
            disabled={!inicio || !fim}
            onClick={() => {
              onAplicar(inicio, fim);
              setOpen(false);
            }}
          >
            Aplicar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const ACTIVE_STYLE = "ring-2 ring-green-500/40 border-green-500/50";

function triggerClass(base: string, active: boolean) {
  return active ? `${base} ${ACTIVE_STYLE}` : base;
}

export function FiltroBar({ filtros, setFiltro, setFaixaIdade, setFaixaPreco, setFaixaQtd, limpar, tags }: FiltroBarProps) {
  const { data: opcoes } = useQuery({
    queryKey: ["filtros"],
    queryFn: () => api.filtros(),
    staleTime: 60_000,
  });

  if (!opcoes) return null;

  // Se leilao_id selecionado não existe mais na lista, calcular valor válido para o select
  const leilaoIdValue = filtros.leilao_id !== undefined
    && opcoes.leiloes?.some((l) => l.id === filtros.leilao_id)
    ? String(filtros.leilao_id)
    : "";

  return (
    <div className="space-y-2">
      {/* Filtros em linha unica com scroll */}
      <div className="flex gap-2 overflow-x-auto pb-1">
        <Select
          value={filtros.raca ?? ""}
          onValueChange={(v) => setFiltro("raca", (v ?? "") === "todas" ? undefined : (v ?? undefined))}
        >
          <SelectTrigger className={triggerClass("w-[130px] h-8 text-xs", !!filtros.raca)}>
            <SelectValue placeholder="Raça" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todas">Todas</SelectItem>
            {opcoes.racas.map((r) => (
              <SelectItem key={r} value={r}>{r}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={filtros.sexo ?? ""}
          onValueChange={(v) => setFiltro("sexo", (v ?? "") === "todos" ? undefined : (v ?? undefined))}
        >
          <SelectTrigger className={triggerClass("w-[100px] h-8 text-xs", !!filtros.sexo)}>
            <SelectValue placeholder="Sexo" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todos</SelectItem>
            {opcoes.sexos.map((s) => (
              <SelectItem key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={filtros.idade_min !== undefined ? String(filtros.idade_min) : ""}
          onValueChange={(v) => {
            const val = v ?? "";
            if (val === "todas") {
              setFaixaIdade(undefined, undefined);
            } else {
              const idade = Number(val);
              setFaixaIdade(idade, idade);
            }
          }}
        >
          <SelectTrigger className={triggerClass("w-[110px] h-8 text-xs", filtros.idade_min !== undefined)}>
            <SelectValue placeholder="Idade" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todas">Todas</SelectItem>
            {opcoes.idades.map((i) => (
              <SelectItem key={i} value={String(i)}>{i}m</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={filtros.estado ?? ""}
          onValueChange={(v) => setFiltro("estado", (v ?? "") === "todos" ? undefined : (v ?? undefined))}
        >
          <SelectTrigger className={triggerClass("w-[90px] h-8 text-xs", !!filtros.estado)}>
            <SelectValue placeholder="Estado" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todos</SelectItem>
            {opcoes.estados.map((e) => (
              <SelectItem key={e} value={e}>{e}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        {opcoes.cidades && opcoes.cidades.length > 0 && (
          <Select
            value={filtros.cidade ?? ""}
            onValueChange={(v) => setFiltro("cidade", (v ?? "") === "todas" ? undefined : (v ?? undefined))}
          >
            <SelectTrigger className={triggerClass("w-[120px] h-8 text-xs", !!filtros.cidade)}>
              <SelectValue placeholder="Cidade" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="todas">Todas</SelectItem>
              {opcoes.cidades.map((c) => (
                <SelectItem key={c} value={c}>{c}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        <Select
          value={filtros.data_inicio ? "custom" : String(filtros.dias ?? 60)}
          onValueChange={(v) => {
            const val = v ?? "";
            if (val !== "custom") {
              setFiltro("data_inicio", undefined);
              setFiltro("data_fim", undefined);
              setFiltro("dias", Number(val));
            }
          }}
        >
          <SelectTrigger className="w-[130px] h-8 text-xs">
            <SelectValue placeholder="Período">
              {filtros.data_inicio && filtros.data_fim
                ? `${new Date(filtros.data_inicio + "T00:00:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "short" })} — ${new Date(filtros.data_fim + "T00:00:00").toLocaleDateString("pt-BR", { day: "2-digit", month: "short" })}`
                : undefined}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="30">30 dias</SelectItem>
            <SelectItem value="60">60 dias</SelectItem>
            <SelectItem value="90">90 dias</SelectItem>
            <SelectItem value="180">6 meses</SelectItem>
            <SelectItem value="365">1 ano</SelectItem>
          </SelectContent>
        </Select>

        <PeriodoPersonalizado
          dataInicio={filtros.data_inicio}
          dataFim={filtros.data_fim}
          onAplicar={(inicio, fim) => {
            setFiltro("dias", undefined);
            setFiltro("data_inicio", inicio);
            setFiltro("data_fim", fim);
          }}
        />

        <Select
          value={filtros.fazenda ?? ""}
          onValueChange={(v) => setFiltro("fazenda", (v ?? "") === "todas" ? undefined : (v ?? undefined))}
        >
          <SelectTrigger className={triggerClass("w-[140px] h-8 text-xs", !!filtros.fazenda)}>
            <SelectValue placeholder="Fazenda" />
          </SelectTrigger>
          <SelectContent side="bottom" align="start" className="min-w-[280px]">
            <SelectItem value="todas">Todas</SelectItem>
            {opcoes.fazendas.map((f) => (
              <SelectItem key={f} value={f} className="text-xs">{f}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={filtros.status ?? ""}
          onValueChange={(v) => setFiltro("status", (v ?? "") === "todos" ? undefined : (v ?? undefined))}
        >
          <SelectTrigger className={triggerClass("w-[130px] h-8 text-xs", !!filtros.status)}>
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todos</SelectItem>
            <SelectItem value="arrematado">Arrematado</SelectItem>
            <SelectItem value="repescagem">Repescagem</SelectItem>
            <SelectItem value="incerto">Sem Disputa</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={filtros.condicao ?? ""}
          onValueChange={(v) => setFiltro("condicao", (v ?? "") === "todas" ? undefined : (v ?? undefined))}
        >
          <SelectTrigger className={triggerClass("w-[120px] h-8 text-xs", !!filtros.condicao)}>
            <SelectValue placeholder="Condição" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todas">Todas</SelectItem>
            <SelectItem value="parida">Parida</SelectItem>
            <SelectItem value="prenhe">Prenhe</SelectItem>
            <SelectItem value="solteira">Solteira</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={filtros.preco_min !== undefined ? `${filtros.preco_min}-${filtros.preco_max}` : ""}
          onValueChange={(v) => {
            const val = v ?? "";
            if (val === "todos") {
              setFaixaPreco(undefined, undefined);
            } else {
              const [min, max] = val.split("-").map(Number);
              setFaixaPreco(min, max);
            }
          }}
        >
          <SelectTrigger className={triggerClass("w-[140px] h-8 text-xs", filtros.preco_min !== undefined)}>
            <SelectValue placeholder="Faixa preço" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todos</SelectItem>
            <SelectItem value="0-2000">Ate R$2.000</SelectItem>
            <SelectItem value="2000-3000">R$2.000–3.000</SelectItem>
            <SelectItem value="3000-4000">R$3.000–4.000</SelectItem>
            <SelectItem value="4000-5000">R$4.000–5.000</SelectItem>
            <SelectItem value="5000-100000">Acima R$5.000</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={filtros.qtd_min !== undefined ? `${filtros.qtd_min}-${filtros.qtd_max}` : ""}
          onValueChange={(v) => {
            const val = v ?? "";
            if (val === "todos") {
              setFaixaQtd(undefined, undefined);
            } else {
              const [min, max] = val.split("-").map(Number);
              setFaixaQtd(min, max);
            }
          }}
        >
          <SelectTrigger className={triggerClass("w-[130px] h-8 text-xs", filtros.qtd_min !== undefined)}>
            <SelectValue placeholder="Quantidade" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todas</SelectItem>
            <SelectItem value="1-5">1–5 cab.</SelectItem>
            <SelectItem value="6-15">6–15 cab.</SelectItem>
            <SelectItem value="16-30">16–30 cab.</SelectItem>
            <SelectItem value="31-500">31+ cab.</SelectItem>
          </SelectContent>
        </Select>

        {opcoes.leiloes && opcoes.leiloes.length > 0 && (
          <Select
            value={leilaoIdValue}
            onValueChange={(v) => setFiltro("leilao_id", (v ?? "") === "todos" ? undefined : Number(v))}
          >
            <SelectTrigger className={triggerClass("w-[140px] h-8 text-xs", leilaoIdValue !== "")}>
              <SelectValue placeholder="Leilão" />
            </SelectTrigger>
            <SelectContent side="bottom" align="start" className="min-w-[350px]">
              <SelectItem value="todos">Todos leilões</SelectItem>
              {opcoes.leiloes.map((l) => (
                <SelectItem key={l.id} value={String(l.id)} className="text-xs">
                  {limparTituloLeilao(l.titulo)}
                  {l.data && (
                    <span className="text-[10px] ml-1 opacity-60">
                      ({new Date(l.data).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })})
                    </span>
                  )}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        <Select
          value={filtros.ordenar ?? ""}
          onValueChange={(v) => setFiltro("ordenar", (v ?? "") === "padrao" ? undefined : (v ?? undefined))}
        >
          <SelectTrigger className={triggerClass("w-[130px] h-8 text-xs", !!filtros.ordenar)}>
            <SelectValue placeholder="Ordenar" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="padrao">Mais recente</SelectItem>
            <SelectItem value="preco_asc">Preço ↑</SelectItem>
            <SelectItem value="preco_desc">Preço ↓</SelectItem>
            <SelectItem value="qtd_desc">Maior qtd</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Tags ativas */}
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {tags.map((tag) => (
            <Badge
              key={tag.key}
              variant="secondary"
              className="cursor-pointer gap-1 text-xs"
              onClick={() => {
                if (tag.key === "data_inicio" || tag.key === "data_fim") {
                  setFiltro("data_inicio", undefined);
                  setFiltro("data_fim", undefined);
                  setFiltro("dias", 60);
                } else if (tag.key === "idade_min" || tag.key === "idade_max") {
                  setFaixaIdade(undefined, undefined);
                } else if (tag.key === "preco_min" || tag.key === "preco_max") {
                  setFaixaPreco(undefined, undefined);
                } else if (tag.key === "qtd_min" || tag.key === "qtd_max") {
                  setFaixaQtd(undefined, undefined);
                } else {
                  setFiltro(tag.key, undefined);
                }
              }}
            >
              {tag.label}
              <X className="h-3 w-3" />
            </Badge>
          ))}
          <Badge variant="outline" className="cursor-pointer text-xs" onClick={limpar}>
            Limpar tudo
          </Badge>
        </div>
      )}
    </div>
  );
}
