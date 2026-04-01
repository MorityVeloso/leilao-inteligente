"""CLI principal do Leilao Inteligente."""

import logging
import sys

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from leilao_inteligente.models.schemas import LeilaoInfo
from leilao_inteligente.pipeline.downloader import obter_info_video, extrair_data_leilao, extrair_local_leilao, listar_videos_canal
from leilao_inteligente.pipeline.processor import processar_video
from leilao_inteligente.storage.repository import (
    listar_leiloes,
    obter_leilao,
    obter_lotes,
    salvar_leilao,
    video_ja_processado,
)


app = typer.Typer(
    name="leilao",
    help="Sistema de IA para monitoramento de leiloes de gado.",
    no_args_is_help=True,
)
console = Console()


def _setup_logging(verbose: bool = False) -> None:
    """Configura logging com Rich."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_time=False, show_path=False)],
    )


@app.command()
def processar(
    url: str = typer.Argument(help="URL do video no YouTube"),
    batch: bool = typer.Option(False, "--batch", "-b", help="Usar Batch API (50%% desconto, ate 24h). Apenas videos gravados."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Modo verboso"),
) -> None:
    """Processa um video gravado de leilao e extrai dados dos lotes."""
    _setup_logging(verbose)

    modo = "[yellow]BATCH[/yellow] (50% desconto)" if batch else "online"
    console.print(f"\n[bold]Processando:[/bold] {url} ({modo})\n")

    try:
        # Obter info do video
        info = obter_info_video(url)
        console.print(f"  Titulo: {info.get('title')}")
        console.print(f"  Canal: {info.get('channel')}")

        # Processar
        lotes = processar_video(url, batch=batch)

        if not lotes:
            console.print("\n[yellow]Nenhum lote encontrado neste video.[/yellow]")
            return

        # Salvar no banco
        cidade, estado = extrair_local_leilao(info)
        leilao_info = LeilaoInfo(
            canal_youtube=str(info.get("channel", "Desconhecido")),
            url_video=url,
            titulo=str(info.get("title", "Sem titulo")),
            data_leilao=extrair_data_leilao(info),
            local_cidade=cidade,
            local_estado=estado,
        )
        leilao = salvar_leilao(leilao_info, lotes)

        # Exibir resultado
        _exibir_lotes(lotes, titulo=str(info.get("title", "")))
        console.print(f"\n[green]Salvo! ID do leilao: {leilao.id}[/green]")

    except Exception as e:
        console.print(f"\n[red]Erro: {e}[/red]")
        sys.exit(1)


@app.command()
def canal(
    url: str = typer.Argument(help="URL do canal no YouTube"),
    limite: int = typer.Option(50, "--limite", "-l", help="Numero maximo de videos"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Modo verboso"),
) -> None:
    """Processa todos os videos de um canal."""
    _setup_logging(verbose)

    console.print(f"\n[bold]Listando videos do canal...[/bold]\n")

    try:
        videos = listar_videos_canal(url, limite=limite)
        console.print(f"Encontrados {len(videos)} videos\n")

        for i, video in enumerate(videos, 1):
            video_url = str(video["url"])
            titulo = str(video.get("title", "?"))

            if video_ja_processado(video_url):
                console.print(f"  [{i}/{len(videos)}] [dim]Ja processado: {titulo}[/dim]")
                continue

            console.print(f"  [{i}/{len(videos)}] Processando: {titulo}")

            try:
                lotes = processar_video(video_url)
                if lotes:
                    info_video = obter_info_video(video_url)
                    leilao_info = LeilaoInfo(
                        canal_youtube=str(info_video.get("channel", "Desconhecido")),
                        url_video=video_url,
                        titulo=str(info_video.get("title", titulo)),
                    )
                    salvar_leilao(leilao_info, lotes)
                    console.print(f"    [green]{len(lotes)} lotes salvos[/green]")
                else:
                    console.print("    [yellow]Nenhum lote encontrado[/yellow]")
            except Exception as e:
                console.print(f"    [red]Erro: {e}[/red]")

        console.print("\n[green]Canal processado![/green]")

    except Exception as e:
        console.print(f"\n[red]Erro: {e}[/red]")
        sys.exit(1)


@app.command()
def listar(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Lista todos os leiloes processados."""
    _setup_logging(verbose)

    leiloes = listar_leiloes()

    if not leiloes:
        console.print("\n[yellow]Nenhum leilao processado ainda.[/yellow]")
        return

    table = Table(title="Leiloes Processados")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Titulo", style="white", max_width=50)
    table.add_column("Canal", style="blue")
    table.add_column("Local", style="green")
    table.add_column("Lotes", justify="right")
    table.add_column("Status", style="yellow")

    for leilao in leiloes:
        local = f"{leilao.local_cidade or '?'}-{leilao.local_estado or '?'}"
        table.add_row(
            str(leilao.id),
            leilao.titulo[:50],
            leilao.canal_youtube[:20],
            local,
            str(leilao.total_lotes or 0),
            leilao.status,
        )

    console.print()
    console.print(table)


@app.command()
def detalhe(
    leilao_id: int = typer.Argument(help="ID do leilao"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Exibe detalhes de um leilao e seus lotes."""
    _setup_logging(verbose)

    leilao = obter_leilao(leilao_id)
    if not leilao:
        console.print(f"\n[red]Leilao ID {leilao_id} nao encontrado.[/red]")
        sys.exit(1)

    console.print(f"\n[bold]{leilao.titulo}[/bold]")
    console.print(f"Canal: {leilao.canal_youtube}")
    console.print(f"Local: {leilao.local_cidade}-{leilao.local_estado}")
    console.print(f"URL: {leilao.url_video}")

    lotes = obter_lotes(leilao_id)
    if not lotes:
        console.print("\n[yellow]Nenhum lote registrado.[/yellow]")
        return

    table = Table(title=f"Lotes ({len(lotes)} total)")
    table.add_column("Lote", style="cyan")
    table.add_column("Qtd", justify="right")
    table.add_column("Raca", style="white")
    table.add_column("Sexo", style="blue")
    table.add_column("Idade", justify="right")
    table.add_column("Fazenda")
    table.add_column("P.Inicial", justify="right", style="yellow")
    table.add_column("P.Final", justify="right", style="green")
    table.add_column("R$/cab", justify="right", style="magenta")
    table.add_column("Status")
    table.add_column("Conf.", justify="right")

    for lote in lotes:
        idade = f"{lote.idade_meses}m" if lote.idade_meses else "-"
        p_inicial = f"R${lote.preco_inicial:,.2f}" if lote.preco_inicial else "-"
        p_final = f"R${lote.preco_final:,.2f}" if lote.preco_final else "-"
        por_cabeca = f"R${lote.preco_por_cabeca:,.2f}" if lote.preco_por_cabeca else "-"
        conf = f"{lote.confianca_media:.0%}" if lote.confianca_media else "-"
        fazenda = (lote.fazenda_vendedor or "-")[:20]
        status_style = {"arrematado": "green", "repescagem": "red", "incerto": "dim"}.get(lote.status, "")
        status_text = f"[{status_style}]{lote.status}[/{status_style}]" if status_style else lote.status

        table.add_row(
            str(lote.lote_numero),
            str(lote.quantidade),
            lote.raca,
            lote.sexo,
            idade,
            fazenda,
            p_inicial,
            p_final,
            por_cabeca,
            status_text,
            conf,
        )

    console.print()
    console.print(table)


def _exibir_lotes(lotes: list, titulo: str = "") -> None:
    """Exibe lotes consolidados em tabela Rich."""
    table = Table(title=f"Lotes extraidos: {titulo}" if titulo else "Lotes extraidos")
    table.add_column("Lote", style="cyan")
    table.add_column("Qtd", justify="right")
    table.add_column("Raca")
    table.add_column("Sexo")
    table.add_column("Idade")
    table.add_column("Fazenda")
    table.add_column("P.Inicial", justify="right", style="yellow")
    table.add_column("P.Final", justify="right", style="green")
    table.add_column("Status")
    table.add_column("Conf.", justify="right")

    for lote in lotes:
        idade = f"{lote.idade_meses}m" if lote.idade_meses else "-"
        table.add_row(
            str(lote.lote_numero),
            str(lote.quantidade),
            lote.raca,
            lote.sexo,
            idade,
            (lote.fazenda_vendedor or "-")[:20],
            f"R${lote.preco_inicial:,.2f}",
            f"R${lote.preco_final:,.2f}",
            lote.status,
            f"{lote.confianca_media:.0%}",
        )

    console.print()
    console.print(table)


if __name__ == "__main__":
    app()
