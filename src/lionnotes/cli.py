"""LionNotes CLI entrypoint."""

import typer

from lionnotes import __version__


def _version_callback(value: bool):
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
