"""LionNotes CLI entrypoint."""

import typer

from lionnotes import __version__


def _version_callback(value: bool | None):
    if value:
        typer.echo(f"lionnotes {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="lionnotes",
    help="Thought mapping tooling for Obsidian vaults.",
    no_args_is_help=True,
)


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-V",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
):
    """Thought mapping tooling for Obsidian vaults."""


@app.command()
def hello():
    """Placeholder command (will be replaced by real commands)."""
    typer.echo("LionNotes is alive.")


@app.command("mathlib-critical-path")
def mathlib_critical_path(
    imports_dir: str | None = typer.Option(
        None,
        help="Root directory of .lean files to scan for imports.",
    ),
    edges_csv: str | None = typer.Option(
        None,
        help="CSV file with importer,imported columns.",
    ),
    trace: str | None = typer.Option(
        None,
        help="Perfetto JSON trace file for per-module compile times.",
    ),
    times_csv: str | None = typer.Option(
        None,
        help="CSV file with module,seconds columns.",
    ),
    top_n: int = typer.Option(
        10,
        help="Number of bottleneck modules to show.",
    ),
):
    """Analyze Lean/Mathlib build dependency graph and find the critical path."""
    from lionnotes.mathlib_critical_path import DependencyGraph

    if imports_dir:
        g = DependencyGraph.from_imports_dir(imports_dir)
    elif edges_csv:
        g = DependencyGraph.from_edges_csv(edges_csv)
    else:
        typer.echo("Error: provide --imports-dir or --edges-csv", err=True)
        raise typer.Exit(1)

    if trace:
        g.load_times_from_perfetto(trace)
    elif times_csv:
        g.load_times_from_csv(times_csv)

    typer.echo(g.summary())
