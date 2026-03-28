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

  const limpar = useCallback(() => setFiltros(INITIAL_FILTROS), []);

  const tags = Object.entries(filtros)
    .filter(([k, v]) => v !== undefined && k !== "dias" && k !== "idade_min" && k !== "idade_max")
    .map(([k, v]) => ({ key: k as keyof Filtros, label: String(v) }));

  if (filtros.idade_min !== undefined || filtros.idade_max !== undefined) {
    const label = `${filtros.idade_min ?? "?"}–${filtros.idade_max ?? "?"}m`;
    tags.push({ key: "idade_min", label });
  }

  return { filtros, setFiltro, setFaixaIdade, limpar, tags };
}
