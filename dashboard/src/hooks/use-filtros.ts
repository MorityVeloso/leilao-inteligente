import { useState, useCallback } from "react";
import type { Filtros } from "@/lib/api";

const INITIAL_FILTROS: Filtros = {
  dias: 60,
};

export function useFiltros() {
  const [filtros, setFiltros] = useState<Filtros>(INITIAL_FILTROS);

  const setFiltro = useCallback(
    <K extends keyof Filtros>(key: K, value: Filtros[K]) => {
      setFiltros((prev) => {
        if (value === undefined || value === "" || value === null) {
          const next = { ...prev };
          delete next[key];
          return next;
        }
        return { ...prev, [key]: value };
      });
    },
    []
  );

  const setFaixaIdade = useCallback(
    (min?: number, max?: number) => {
      setFiltros((prev) => {
        const next = { ...prev };
        if (min !== undefined) next.idade_min = min;
        else delete next.idade_min;
        if (max !== undefined) next.idade_max = max;
        else delete next.idade_max;
        return next;
      });
    },
    []
  );

  const setFaixaPreco = useCallback(
    (min?: number, max?: number) => {
      setFiltros((prev) => {
        const next = { ...prev };
        if (min !== undefined) next.preco_min = min;
        else delete next.preco_min;
        if (max !== undefined) next.preco_max = max;
        else delete next.preco_max;
        return next;
      });
    },
    []
  );

  const setFaixaQtd = useCallback(
    (min?: number, max?: number) => {
      setFiltros((prev) => {
        const next = { ...prev };
        if (min !== undefined) next.qtd_min = min;
        else delete next.qtd_min;
        if (max !== undefined) next.qtd_max = max;
        else delete next.qtd_max;
        return next;
      });
    },
    []
  );

  const limpar = useCallback(() => setFiltros(INITIAL_FILTROS), []);

  const tags: { key: keyof Filtros; label: string }[] = [];

  for (const [k, v] of Object.entries(filtros)) {
    if (v === undefined || k === "dias" || k === "idade_min" || k === "idade_max" || k === "preco_min" || k === "preco_max" || k === "qtd_min" || k === "qtd_max") continue;
    if (k === "leilao_id") {
      tags.push({ key: k as keyof Filtros, label: `Leilao #${v}` });
    } else if (k === "ordenar") {
      const labels: Record<string, string> = { preco_asc: "Preco ↑", preco_desc: "Preco ↓", data_desc: "Mais recente", qtd_desc: "Maior qtd" };
      tags.push({ key: k as keyof Filtros, label: labels[v as string] ?? String(v) });
    } else {
      tags.push({ key: k as keyof Filtros, label: String(v) });
    }
  }

  if (filtros.idade_min !== undefined || filtros.idade_max !== undefined) {
    tags.push({ key: "idade_min", label: `${filtros.idade_min ?? "?"}–${filtros.idade_max ?? "?"}m` });
  }
  if (filtros.preco_min !== undefined || filtros.preco_max !== undefined) {
    const min = filtros.preco_min ? `R$${filtros.preco_min.toLocaleString()}` : "?";
    const max = filtros.preco_max ? `R$${filtros.preco_max.toLocaleString()}` : "?";
    tags.push({ key: "preco_min", label: `${min}–${max}` });
  }
  if (filtros.qtd_min !== undefined || filtros.qtd_max !== undefined) {
    tags.push({ key: "qtd_min", label: `${filtros.qtd_min ?? "?"}–${filtros.qtd_max ?? "?"}cab` });
  }

  return { filtros, setFiltro, setFaixaIdade, setFaixaPreco, setFaixaQtd, limpar, tags };
}
