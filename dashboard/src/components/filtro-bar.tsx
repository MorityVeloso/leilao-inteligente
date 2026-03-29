import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
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

export function FiltroBar({ filtros, setFiltro, setFaixaIdade, setFaixaPreco, setFaixaQtd, limpar, tags }: FiltroBarProps) {
  const { data: opcoes } = useQuery({
    queryKey: ["filtros"],
    queryFn: () => api.filtros(),
    staleTime: 60_000,
  });

  if (!opcoes) return null;

  return (
    <div className="space-y-2">
      {/* Filtros em linha unica com scroll */}
      <div className="flex gap-2 overflow-x-auto pb-1">
        <Select
          value={filtros.raca ?? ""}
          onValueChange={(v) => setFiltro("raca", v === "todas" ? undefined : v)}
        >
          <SelectTrigger className="w-[130px] h-8 text-xs">
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
          onValueChange={(v) => setFiltro("sexo", v === "todos" ? undefined : v)}
        >
          <SelectTrigger className="w-[100px] h-8 text-xs">
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
          value={filtros.idade_min !== undefined ? `${filtros.idade_min}-${filtros.idade_max}` : ""}
          onValueChange={(v) => {
            if (v === "todas") {
              setFaixaIdade(undefined, undefined);
            } else {
              const faixa = opcoes.faixas_idade.find((f) => `${f.min}-${f.max}` === v);
              if (faixa) setFaixaIdade(faixa.min, faixa.max);
            }
          }}
        >
          <SelectTrigger className="w-[110px] h-8 text-xs">
            <SelectValue placeholder="Idade" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todas">Todas</SelectItem>
            {opcoes.faixas_idade.map((f) => (
              <SelectItem key={f.label} value={`${f.min}-${f.max}`}>{f.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={filtros.estado ?? ""}
          onValueChange={(v) => setFiltro("estado", v === "todos" ? undefined : v)}
        >
          <SelectTrigger className="w-[90px] h-8 text-xs">
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
            onValueChange={(v) => setFiltro("cidade", v === "todas" ? undefined : v)}
          >
            <SelectTrigger className="w-[120px] h-8 text-xs">
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
          value={String(filtros.dias ?? 60)}
          onValueChange={(v) => setFiltro("dias", Number(v))}
        >
          <SelectTrigger className="w-[110px] h-8 text-xs">
            <SelectValue placeholder="Período" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="30">30 dias</SelectItem>
            <SelectItem value="60">60 dias</SelectItem>
            <SelectItem value="90">90 dias</SelectItem>
            <SelectItem value="180">6 meses</SelectItem>
            <SelectItem value="365">1 ano</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={filtros.fazenda ?? ""}
          onValueChange={(v) => setFiltro("fazenda", v === "todas" ? undefined : v)}
        >
          <SelectTrigger className="w-[140px] h-8 text-xs">
            <SelectValue placeholder="Fazenda" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todas">Todas</SelectItem>
            {opcoes.fazendas.map((f) => (
              <SelectItem key={f} value={f}>{f}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={filtros.status ?? ""}
          onValueChange={(v) => setFiltro("status", v === "todos" ? undefined : v)}
        >
          <SelectTrigger className="w-[130px] h-8 text-xs">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todos</SelectItem>
            <SelectItem value="arrematado">Arrematado</SelectItem>
            <SelectItem value="repescagem">Repescagem</SelectItem>
            <SelectItem value="incerto">Incerto</SelectItem>
          </SelectContent>
        </Select>

        <Select
          value={filtros.preco_min !== undefined ? `${filtros.preco_min}-${filtros.preco_max}` : ""}
          onValueChange={(v) => {
            if (v === "todos") {
              setFaixaPreco(undefined, undefined);
            } else {
              const [min, max] = v.split("-").map(Number);
              setFaixaPreco(min, max);
            }
          }}
        >
          <SelectTrigger className="w-[140px] h-8 text-xs">
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
            if (v === "todos") {
              setFaixaQtd(undefined, undefined);
            } else {
              const [min, max] = v.split("-").map(Number);
              setFaixaQtd(min, max);
            }
          }}
        >
          <SelectTrigger className="w-[130px] h-8 text-xs">
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
            value={filtros.leilao_id !== undefined ? String(filtros.leilao_id) : ""}
            onValueChange={(v) => setFiltro("leilao_id", v === "todos" ? undefined : Number(v))}
          >
            <SelectTrigger className="w-[140px] h-8 text-xs">
              <SelectValue placeholder="Leilão" />
            </SelectTrigger>
            <SelectContent position="popper" side="bottom" align="start" className="min-w-[350px]">
              <SelectItem value="todos">Todos leilões</SelectItem>
              {opcoes.leiloes.map((l) => (
                <SelectItem key={l.id} value={String(l.id)} className="text-xs">
                  {limparTituloLeilao(l.titulo)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        <Select
          value={filtros.ordenar ?? ""}
          onValueChange={(v) => setFiltro("ordenar", v === "padrao" ? undefined : v)}
        >
          <SelectTrigger className="w-[130px] h-8 text-xs">
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
                if (tag.key === "idade_min" || tag.key === "idade_max") {
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
