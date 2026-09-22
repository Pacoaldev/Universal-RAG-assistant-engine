"""
Interfaz de línea de comandos (CLI) moderna con renderizado Rich.
"""

from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from src.core.assistant import UniversalAssistant

console = Console()


def display_banner(assistant: UniversalAssistant) -> None:
    """Muestra el banner de bienvenida con diseño enriquecido."""
    info_table = Table.grid(padding=(0, 2))
    info_table.add_row("[bold cyan]Organización:[/]", f"[white]{assistant.organization}[/]")
    info_table.add_row("[bold cyan]Motor LLM:[/]", f"[green]{assistant.llm.__class__.__name__}[/]")
    info_table.add_row(
        "[bold cyan]Almacén RAG:[/]", f"[yellow]{assistant.storage.__class__.__name__}[/]"
    )
    info_table.add_row("[bold cyan]Comandos:[/]", "[dim]'salir', 'help', 'info', 'docs'[/]")

    panel = Panel(
        info_table,
        title=f"🤖 [bold green]{assistant.name}[/]",
        subtitle="[dim]Universal RAG Engine v1.0.0[/dim]",
        border_style="bright_blue",
        padding=(1, 2),
    )
    console.print(panel)
    console.print()


def run_interactive_cli(assistant: Optional[UniversalAssistant] = None) -> None:
    """Ejecuta el bucle interactivo de conversación en terminal."""
    bot = assistant or UniversalAssistant()
    display_banner(bot)

    while True:
        try:
            query = Prompt.ask("[bold blue]Tú[/bold blue]").strip()

            if not query:
                continue

            if query.lower() in ("salir", "exit", "quit", "q"):
                console.print(f"\n[green]¡Hasta pronto! Gracias por usar {bot.name}.[/green] 👋\n")
                break

            if query.lower() in ("help", "ayuda"):
                console.print(
                    "\n[bold yellow]Comandos disponibles:[/bold yellow]\n"
                    "- [bold]salir / exit[/bold]: Cierra el asistente.\n"
                    "- [bold]info[/bold]: Muestra detalles del backend activo.\n"
                    "- [bold]docs[/bold]: Muestra cuántos documentos hay indexados.\n"
                )
                continue

            if query.lower() == "info":
                console.print(
                    f"\n[cyan]Asistente:[/] {bot.name}\n"
                    f"[cyan]Organización:[/] {bot.organization}\n"
                    f"[cyan]Almacén:[/] {bot.storage.__class__.__name__}\n"
                    f"[cyan]LLM:[/] {bot.llm.__class__.__name__}\n"
                )
                continue

            if query.lower() == "docs":
                all_data = bot.storage.get_all()
                total = sum(len(v) for v in all_data.values())
                console.print(f"\n[cyan]Documentos cargados:[/] {total}")
                for k, v in all_data.items():
                    console.print(f"  • [bold]{k}:[/bold] {len(v)} documentos")
                console.print()
                continue

            with console.status(f"[cyan]{bot.name} está pensando...[/cyan]", spinner="dots"):
                response = bot.ask(query)

            # Imprimir respuesta formateada
            console.print()
            panel_title = (
                f"🐾 [bold green]{bot.name}[/bold green] "
                f"[dim]({response.processing_time_ms} ms | {response.sources_count} fuentes)[/dim]"
            )
            res_panel = Panel(
                Markdown(response.answer),
                title=panel_title,
                border_style="green",
                padding=(1, 2),
            )
            console.print(res_panel)
            console.print()

        except (KeyboardInterrupt, EOFError):
            console.print("\n\n[green]Sesión finalizada.[/green] 👋\n")
            break
        except Exception as e:
            console.print(f"[bold red]Error:[/] {e}")


def main():
    """Punto de entrada principal para el CLI."""
    run_interactive_cli()


if __name__ == "__main__":
    main()
