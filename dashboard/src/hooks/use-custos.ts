import { useState, useCallback } from "react";

export interface Custos {
  frete: number;    // R$/cabeça
  comissao: number; // percentual
  outros: number;   // R$ fixo
}

const DEFAULTS: Custos = { frete: 150, comissao: 5, outros: 0 };
const STORAGE_KEY = "custos-arbitragem";

function load(): Custos {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch { /* ignore */ }
  return DEFAULTS;
}

export function useCustos() {
  const [custos, setCustos] = useState<Custos>(load);

  const setCusto = useCallback(<K extends keyof Custos>(key: K, value: number) => {
    setCustos((prev) => {
      const next = { ...prev, [key]: value };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const calcularLucro = useCallback(
    (precoCompra: number, precoVenda: number) => {
      const spread = precoVenda - precoCompra;
      const custoTotal = custos.frete + (precoCompra * custos.comissao / 100) + custos.outros;
      return spread - custoTotal;
    },
    [custos]
  );

  return { custos, setCusto, calcularLucro };
}
