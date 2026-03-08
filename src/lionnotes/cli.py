"""LionNotes CLI entrypoint."""

import typer

app = typer.Typer(
    name="lionnotes",
    help="Thought mapping tooling for Obsidian vaults.",
    no_args_is_help=True,
)


@app.command()
def version():
    """Print the LionNotes version."""
    from lionnotes import __version__

    typer.echo(f"lionnotes {__version__}")
