import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api, type FiltrosOpcoes, type Filtros } from "@/lib/api";

interface FiltroBarProps {
  filtros: Filtros;
  setFiltro: <K extends keyof Filtros>(key: K, value: Filtros[K]) => void;
  setFaixaIdade: (min?: number, max?: number) => void;
  limpar: () => void;
  tags: { key: keyof Filtros; label: string }[];
}

export function FiltroBar({ filtros, setFiltro, setFaixaIdade, limpar, tags }: FiltroBarProps) {
  const [opcoes, setOpcoes] = useState<FiltrosOpcoes | null>(null);

  useEffect(() => {
    api.filtros().then(setOpcoes);
  }, []);

  if (!opcoes) return null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <Select
          value={filtros.raca ?? ""}
          onValueChange={(v) => setFiltro("raca", v === "todas" ? undefined : v)}
        >
          <SelectTrigger className="w-[140px]">
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
          <SelectTrigger className="w-[120px]">
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
          value={
            filtros.idade_min !== undefined
              ? `${filtros.idade_min}-${filtros.idade_max}`
              : ""
          }
          onValueChange={(v) => {
            if (v === "todas") {
              setFaixaIdade(undefined, undefined);
            } else {
              const faixa = opcoes.faixas_idade.find((f) => `${f.min}-${f.max}` === v);
              if (faixa) setFaixaIdade(faixa.min, faixa.max);
            }
          }}
        >
          <SelectTrigger className="w-[130px]">
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
          <SelectTrigger className="w-[100px]">
            <SelectValue placeholder="Estado" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todos</SelectItem>
            {opcoes.estados.map((e) => (
              <SelectItem key={e} value={e}>{e}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={String(filtros.dias ?? 60)}
          onValueChange={(v) => setFiltro("dias", Number(v))}
        >
          <SelectTrigger className="w-[130px]">
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
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="Fazenda" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todas">Todas</SelectItem>
            {opcoes.fazendas.map((f) => (
              <SelectItem key={f} value={f}>{f}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {tags.map((tag) => (
            <Badge
              key={tag.key}
              variant="secondary"
              className="cursor-pointer gap-1"
              onClick={() => {
                if (tag.key === "idade_min") {
                  setFaixaIdade(undefined, undefined);
                } else {
                  setFiltro(tag.key, undefined);
                }
              }}
            >
              {tag.label}
              <X className="h-3 w-3" />
            </Badge>
          ))}
          <Badge variant="outline" className="cursor-pointer" onClick={limpar}>
            Limpar tudo
          </Badge>
        </div>
      )}
    </div>
  );
}
