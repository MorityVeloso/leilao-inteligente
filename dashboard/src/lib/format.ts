/**
 * Formatacao padronizada de nomes (leiloes, cidades, fazendas).
 *
 * Converte qualquer formato (MAIUSCULO, minusculo, misto) para
 * Title Case consistente, com abreviacoes padronizadas.
 */

/** Palavras que ficam minusculas em Title Case (preposicoes, artigos). */
const PALAVRAS_MENORES = new Set([
  "de", "do", "da", "dos", "das", "e", "em", "no", "na", "nos", "nas",
  "com", "por", "para", "ao", "aos",
]);

/** Abreviacoes que devem manter formato especifico. */
const ABREVIACOES: Record<string, string> = {
  "go": "GO", "mt": "MT", "ms": "MS", "mg": "MG", "sp": "SP",
  "rj": "RJ", "pr": "PR", "sc": "SC", "rs": "RS", "ba": "BA",
  "to": "TO", "pa": "PA", "ma": "MA", "pi": "PI", "ce": "CE",
  "rn": "RN", "pb": "PB", "pe": "PE", "al": "AL", "se": "SE",
  "es": "ES", "df": "DF", "ac": "AC", "am": "AM", "ap": "AP",
  "ro": "RO", "rr": "RR",
};

function titleCase(texto: string): string {
  return texto
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .map((palavra, i) => {
      const lower = palavra.toLowerCase();

      // UF (2 letras no final, ex: -GO)
      if (lower.includes("-") && lower.length >= 3) {
        const parts = lower.split("-");
        const last = parts[parts.length - 1];
        if (ABREVIACOES[last]) {
          parts[parts.length - 1] = ABREVIACOES[last];
          return parts.map((p, j) =>
            j < parts.length - 1
              ? (ABREVIACOES[p] || p.charAt(0).toUpperCase() + p.slice(1))
              : p
          ).join("-");
        }
      }

      // Abreviacao conhecida (UF solta)
      if (ABREVIACOES[lower]) return ABREVIACOES[lower];

      // Preposicao/artigo (exceto primeira palavra)
      if (i > 0 && PALAVRAS_MENORES.has(lower)) return lower;

      // Capitalizar primeira letra
      return lower.charAt(0).toUpperCase() + lower.slice(1);
    })
    .join(" ");
}

/** Formata nome de leilao para exibicao. */
export function formatLeilao(titulo: string): string {
  let t = titulo
    // Remover prefixos comuns
    .replace(/LEIL[ÃA]O\s*/gi, "")
    .replace(/\bLIVE\b.*$/i, "")
    // Abreviar
    .replace(/SINDICATO\s+RURAL/gi, "Sind. Rur.")
    .replace(/LEIL[OÕ]ES\s+RURAIS/gi, "Leilões Rurais")
    .replace(/GARANTIDO\s+LEIL[OÕ]ES/gi, "Garantido Leilões")
    // Remover data no final (ja mostramos separado)
    .replace(/\d{2}\/\d{2}\/\d{4}\s*/g, "")
    // Remover leiloeiro
    .replace(/\b(JENILSON|LEILOEIRO)\b.*/gi, "")
    .trim();

  // Se apos limpeza ficou so com sigla UF, nao formatar
  if (t.length <= 3) return t.toUpperCase();

  return titleCase(t);
}

/** Remove acentos para comparacao. */
function semAcento(s: string): string {
  return s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

/** Formata nome de leilao com cidade e data para dropdown. */
export function formatLeilaoCompleto(
  titulo: string,
  cidade?: string | null,
  estado?: string | null,
  data?: string | null,
): string {
  const nome = formatLeilao(titulo);
  const local = cidade && estado ? `${formatCidade(cidade)}-${estado.toUpperCase()}` : "";

  // Data: pegar so YYYY-MM-DD e formatar sem timezone
  let dataStr = "";
  if (data) {
    const d = data.slice(0, 10); // "2026-03-26"
    const [y, m, day] = d.split("-");
    dataStr = `${day}/${m}/${y}`;
  }

  const parts = [nome];
  // So adicionar local se a cidade nao aparece no nome (comparar sem acento)
  if (local && cidade && !semAcento(nome).includes(semAcento(cidade))) {
    parts.push(local);
  }
  if (dataStr) parts.push(dataStr);

  return parts.join(" - ");
}

/** Formata nome de cidade para exibicao (Title Case). */
export function formatCidade(nome: string): string {
  if (!nome) return "";
  return titleCase(nome);
}

/** Formata nome de fazenda para exibicao (Title Case, abreviado). */
export function formatFazenda(nome: string): string {
  if (!nome) return "";
  let f = nome
    .replace(/^FAZ\.\s*/i, "Faz. ")
    .replace(/^FAZENDA\s*/i, "Faz. ")
    .replace(/^SITIO\s*/i, "Sítio ")
    .replace(/^CHACARA\s*/i, "Chác. ")
    .replace(/^CHAC\.\s*/i, "Chác. ")
    .replace(/^AGROPECUARIA\s*/i, "Agrop. ")
    .replace(/^AGROP\.\s*/i, "Agrop. ");
  // Se já foi substituído por prefixo formatado, aplicar titleCase só no resto
  const prefixos = ["Faz. ", "Sítio ", "Chác. ", "Agrop. "];
  for (const p of prefixos) {
    if (f.startsWith(p)) {
      return p + titleCase(f.slice(p.length));
    }
  }
  return titleCase(f);
}

/** Formata nome de canal para exibicao (Title Case). */
export function formatCanal(nome: string): string {
  if (!nome) return "";
  return titleCase(nome);
}

/** Formata valor em BRL. */
export function formatBRL(value: number | null): string {
  if (value === null) return "—";
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}
