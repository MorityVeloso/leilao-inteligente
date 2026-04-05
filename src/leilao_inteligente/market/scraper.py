"""Scraper de cotações do Notícias Agrícolas (Scot Consultoria + Datagro)."""

import logging
import re
from datetime import date, datetime

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.noticiasagricolas.com.br"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

# Mapeamento de estado: texto na tabela → UF
ESTADO_MAP = {
    "SP": "SP", "São Paulo": "SP", "Sao Paulo": "SP",
    "MG": "MG", "Minas Gerais": "MG",
    "GO": "GO", "Goiás": "GO", "Goias": "GO", "Goiânia": "GO", "Goiania": "GO",
    "MS": "MS", "Mato Grosso do Sul": "MS",
    "MT": "MT", "Mato Grosso": "MT",
    "BA": "BA", "Bahia": "BA",
    "PR": "PR", "Paraná": "PR", "Parana": "PR",
    "PA": "PA", "Pará": "PA", "Para": "PA",
    "RO": "RO", "Rondônia": "RO", "Rondonia": "RO",
    "TO": "TO", "Tocantins": "TO",
    "AC": "AC", "Acre": "AC",
    "MA": "MA", "Maranhão": "MA", "Maranhao": "MA",
    "RJ": "RJ", "Rio de Janeiro": "RJ",
    "RS": "RS", "Rio Grande do Sul": "RS",
    "SC": "SC", "Santa Catarina": "SC",
    "ES": "ES", "Espírito Santo": "ES",
    "RR": "RR", "Roraima": "RR",
}


def _extrair_uf(texto: str) -> str | None:
    """Extrai UF de um texto como 'GO Goiânia' ou 'Mato Grosso'."""
    texto = texto.strip()
    # Tentar match direto
    if texto[:2].upper() in ESTADO_MAP:
        return ESTADO_MAP[texto[:2].upper()]
    # Tentar match por nome
    for nome, uf in ESTADO_MAP.items():
        if nome.lower() in texto.lower():
            return uf
    return None


def _extrair_praca(texto: str) -> str | None:
    """Extrai praça/município do texto (parte após a UF)."""
    texto = texto.strip()
    # "GO Goiânia" → "Goiânia"
    # "MT Norte" → "Norte"
    parts = texto.split(None, 1)
    if len(parts) > 1 and len(parts[0]) <= 3:
        return parts[1].strip()
    return None


def _parse_valor(texto: str) -> float | None:
    """Converte texto de preço para float. Ex: '3.330,66' → 3330.66"""
    texto = texto.strip().replace("R$", "").replace(" ", "")
    if not texto or texto == "-" or texto == "--":
        return None
    # Formato brasileiro: 3.330,66
    texto = texto.replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return None


def _fetch_page(path: str) -> BeautifulSoup | None:
    """Busca e parseia uma página do NA."""
    url = f"{BASE_URL}{path}"
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
        if resp.status_code != 200:
            logger.warning("HTTP %d: %s", resp.status_code, url)
            return None
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        logger.error("Erro acessando %s: %s", url, e)
        return None


def scrape_boi_gordo_scot() -> list[dict]:
    """Scrape cotação boi gordo Scot Consultoria — R$/@ por praça, 17 estados."""
    soup = _fetch_page("/cotacoes/boi-gordo/boi-gordo-scot-consultoria")
    if not soup:
        return []

    resultados = []
    hoje = date.today()

    for table in soup.select("table.cot-fisicas"):
        rows = table.select("tbody tr")
        for row in rows:
            cols = [td.get_text(strip=True) for td in row.select("td")]
            if len(cols) < 2:
                continue

            uf = _extrair_uf(cols[0])
            if not uf:
                continue

            praca = _extrair_praca(cols[0])

            # Colunas: Praça | Boi Gordo a vista | Boi Gordo prazo 30d | Vaca Gorda
            boi_vista = _parse_valor(cols[1]) if len(cols) > 1 else None
            vaca = _parse_valor(cols[3]) if len(cols) > 3 else None

            if boi_vista:
                resultados.append({
                    "data": hoje, "estado": uf, "praca": praca,
                    "categoria": "boi_gordo", "raca": "nelore", "sexo": "macho",
                    "valor": boi_vista, "unidade": "BRL/@", "fonte": "scot",
                })
            if vaca:
                resultados.append({
                    "data": hoje, "estado": uf, "praca": praca,
                    "categoria": "vaca_gorda", "raca": "nelore", "sexo": "femea",
                    "valor": vaca, "unidade": "BRL/@", "fonte": "scot",
                })

    logger.info("Scot boi gordo: %d cotações", len(resultados))
    return resultados


def scrape_reposicao_scot(
    raca: str,
    sexo: str,
    categoria: str,
    path: str,
) -> list[dict]:
    """Scrape cotação de reposição Scot — R$/cab por estado."""
    soup = _fetch_page(path)
    if not soup:
        return []

    resultados = []
    hoje = date.today()

    for table in soup.select("table.cot-fisicas"):
        rows = table.select("tbody tr")
        for row in rows:
            cols = [td.get_text(strip=True) for td in row.select("td")]
            if len(cols) < 2:
                continue

            uf = _extrair_uf(cols[0])
            if not uf:
                continue

            # Colunas: Estado | R$/Cabeça | R$/Kg | Troca
            valor_cab = _parse_valor(cols[1]) if len(cols) > 1 else None

            if valor_cab:
                resultados.append({
                    "data": hoje, "estado": uf, "praca": None,
                    "categoria": categoria, "raca": raca, "sexo": sexo,
                    "valor": valor_cab, "unidade": "BRL/cab", "fonte": "scot",
                })

    logger.info("Scot %s %s %s: %d cotações", raca, sexo, categoria, len(resultados))
    return resultados


def scrape_indicadores_datagro() -> list[dict]:
    """Scrape indicadores Datagro — boi, vaca, novilha R$/@ por estado."""
    resultados = []
    hoje = date.today()

    configs = [
        ("/cotacoes/boi-gordo/indicador-do-boi", "boi_gordo", "macho"),
        ("/cotacoes/boi-gordo/indicador-da-vaca", "vaca_gorda", "femea"),
        ("/cotacoes/boi-gordo/indicador-da-novilha", "novilha_abate", "femea"),
    ]

    for path, categoria, sexo in configs:
        soup = _fetch_page(path)
        if not soup:
            continue

        for table in soup.select("table.cot-fisicas"):
            rows = table.select("tbody tr")
            for row in rows:
                cols = [td.get_text(strip=True) for td in row.select("td")]
                if len(cols) < 2:
                    continue

                uf = _extrair_uf(cols[0])
                if not uf:
                    continue

                valor = _parse_valor(cols[1]) if len(cols) > 1 else None

                if valor:
                    resultados.append({
                        "data": hoje, "estado": uf, "praca": None,
                        "categoria": categoria, "raca": "nelore", "sexo": sexo,
                        "valor": valor, "unidade": "BRL/@", "fonte": "datagro",
                    })

    logger.info("Datagro indicadores: %d cotações", len(resultados))
    return resultados


# Todas as URLs de reposição Scot
REPOSICAO_URLS = [
    # Nelore Macho
    ("nelore", "macho", "bezerro_8m", "/cotacoes/boi-gordo/macho-nelore-desmama-8-meses"),
    ("nelore", "macho", "bezerro_12m", "/cotacoes/boi-gordo/macho-nelore-bezerro-12-meses"),
    ("nelore", "macho", "garrote", "/cotacoes/boi-gordo/macho-nelore-garrote-18-meses"),
    ("nelore", "macho", "boi_magro", "/cotacoes/boi-gordo/macho-nelore-boi-magro"),
    # Nelore Fêmea
    ("nelore", "femea", "bezerra_8m", "/cotacoes/boi-gordo/femea-nelore-desmama-8-meses"),
    ("nelore", "femea", "bezerra_12m", "/cotacoes/boi-gordo/bezerra-nelore-femea-12-meses"),
    ("nelore", "femea", "novilha", "/cotacoes/boi-gordo/femea-nelore-novilha-18-meses"),
    ("nelore", "femea", "vaca_boiadeira", "/cotacoes/boi-gordo/femea-nelore-vaca-boiadeira"),
    # Mestiço Macho
    ("mestico", "macho", "bezerro_8m", "/cotacoes/boi-gordo/macho-mestico-desmama-8-meses"),
    ("mestico", "macho", "bezerro_12m", "/cotacoes/boi-gordo/macho-mestico-bezerro-12-meses"),
    ("mestico", "macho", "garrote", "/cotacoes/boi-gordo/macho-mestico-garrote-18-meses"),
    ("mestico", "macho", "boi_magro", "/cotacoes/boi-gordo/macho-mestico-boi-magro"),
    # Mestiço Fêmea
    ("mestico", "femea", "bezerra_8m", "/cotacoes/boi-gordo/femea-mestica-desmama-8-meses"),
    ("mestico", "femea", "bezerra_12m", "/cotacoes/boi-gordo/femea-mestica-bezerra-12-meses"),
    ("mestico", "femea", "novilha", "/cotacoes/boi-gordo/femea-mestica-novilha-18-meses"),
    ("mestico", "femea", "vaca_boiadeira", "/cotacoes/boi-gordo/femea-mestica-reposico-vaca-boiadeira-300-kg-10"),
]


def scrape_toda_reposicao_scot() -> list[dict]:
    """Scrape todas as 16 categorias de reposição Scot."""
    resultados = []
    for raca, sexo, categoria, path in REPOSICAO_URLS:
        try:
            dados = scrape_reposicao_scot(raca, sexo, categoria, path)
            resultados.extend(dados)
        except Exception as e:
            logger.error("Erro scraping %s: %s", path, e)
    return resultados


def scrape_tudo() -> list[dict]:
    """Scrape todas as fontes do NA (boi gordo + reposição + indicadores)."""
    resultados = []

    # 1. Boi gordo Scot (R$/@ por praça)
    resultados.extend(scrape_boi_gordo_scot())

    # 2. Reposição Scot (16 categorias × 13-15 estados)
    resultados.extend(scrape_toda_reposicao_scot())

    # 3. Indicadores Datagro (boi, vaca, novilha por estado)
    resultados.extend(scrape_indicadores_datagro())

    logger.info("Total scraping NA: %d cotações", len(resultados))
    return resultados
