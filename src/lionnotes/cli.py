"""LionNotes CLI entrypoint."""

from __future__ import annotations

from pathlib import Path

import typer

from lionnotes import __version__
from lionnotes.config import (
    Config,
    ConfigNotFoundError,
    find_config,
    load_config,
    save_config,
)
from lionnotes.obsidian import (
    ObsidianCLI,
    ObsidianCLIError,
    ObsidianNotFoundError,
    ObsidianNotRunningError,
)
from lionnotes.templates import render


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


# -- init -------------------------------------------------------------------

# Files created by `init` — mapping of vault-relative path to template name
_INIT_FILES: list[tuple[str, str]] = [
    ("GSMOC", "gsmoc"),
    ("_inbox/unsorted", "inbox"),
    ("_strategy/active-priorities", "strategy"),
    ("_strategy/maintenance-queue", "maintenance-queue"),
    ("Subject Registry", "subject-registry"),
    ("Global Aliases", "global-aliases"),
]


def _write_file_direct(vault_path: Path, name: str, content: str) -> None:
    """Write a markdown file directly to disk (offline fallback)."""
    # name uses Obsidian note-name convention (no .md extension, may have /)
    file_path = vault_path / f"{name}.md"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def _file_exists_direct(vault_path: Path, name: str) -> bool:
    """Check if a note file exists on disk."""
    return (vault_path / f"{name}.md").is_file()


@app.command()
def init(
    vault_path: str = typer.Option(
        ...,
        "--vault-path",
        "-p",
        help="Filesystem path to the Obsidian vault.",
    ),
    vault_name: str | None = typer.Option(
        None,
        "--vault-name",
        "-n",
        help="Obsidian vault name (for CLI). Auto-detected from path if omitted.",
    ),
):
    """Initialize a new LionNotes vault (or adopt an existing one)."""
    vp = Path(vault_path).resolve()
    if not vp.is_dir():
        typer.echo(f"Error: {vault_path} is not a directory.", err=True)
        raise typer.Exit(1)

    # Determine vault name for Obsidian CLI (default: directory name)
    vname = vault_name or vp.name

    # Try Obsidian CLI, fall back to direct file writes
    obsidian: ObsidianCLI | None = None
    use_obsidian = True
    try:
        obs = ObsidianCLI(vault=vname)
        obs.version()
        obsidian = obs
    except (ObsidianNotRunningError, ObsidianNotFoundError):
        use_obsidian = False
        typer.echo("Obsidian not available — using direct file writes.")

    created = []
    skipped = []

    for note_name, template_name in _INIT_FILES:
        # Check existence
        exists = False
        if use_obsidian and obsidian is not None:
            try:
                obsidian.read(note_name)
                exists = True
            except ObsidianCLIError:
                exists = False
        else:
            exists = _file_exists_direct(vp, note_name)

        if exists:
            skipped.append(note_name)
            continue

        content = render(template_name)

        if use_obsidian and obsidian is not None:
            obsidian.create(note_name, content=content)
        else:
            _write_file_direct(vp, note_name, content)

        created.append(note_name)

    # Write config
    config_path = vp / ".lionnotes.toml"
    if config_path.is_file():
        skipped.append(".lionnotes.toml")
    else:
        config = Config(vault_path=str(vp))
        save_config(config, config_path)
        created.append(".lionnotes.toml")

    # Report
    if created:
        typer.echo("Created:")
        for name in created:
            typer.echo(f"  + {name}")
    if skipped:
        typer.echo("Already exists (skipped):")
        for name in skipped:
            typer.echo(f"  - {name}")
    typer.echo(f"\nLionNotes initialized in {vp}")


# -- doctor -----------------------------------------------------------------


def _check(label: str, passed: bool, detail: str = "") -> bool:
    """Print a pass/fail check line and return the result."""
    icon = "PASS" if passed else "FAIL"
    msg = f"  [{icon}] {label}"
    if detail:
        msg += f" — {detail}"
    typer.echo(msg)
    return passed


def _count_entries(text: str) -> int:
    """Count lines starting with '- ' (list entries)."""
    return sum(1 for line in text.splitlines() if line.strip().startswith("- "))


def _warn(label: str, detail: str = "") -> None:
    """Print a warning check line."""
    msg = f"  [WARN] {label}"
    if detail:
        msg += f" — {detail}"
    typer.echo(msg)


@app.command()
def doctor(
    vault_path: str | None = typer.Option(
        None,
        "--vault-path",
        "-p",
        help="Vault path (default: auto-detect from .lionnotes.toml).",
    ),
):
    """Validate the LionNotes environment and flag maintenance needs."""
    typer.echo("LionNotes Doctor\n")

    # 1. Find config
    typer.echo("Environment:")
    config: Config | None = None
    vp: Path | None = None
    if vault_path:
        vp = Path(vault_path).resolve()
        config_file = vp / ".lionnotes.toml"
        if config_file.is_file():
            config = load_config(config_file)
            _check("Config", True, str(config_file))
        else:
            _check("Config", False, f"No .lionnotes.toml in {vp}")
            typer.echo("\nRun 'lionnotes init --vault-path <path>' first.")
            raise typer.Exit(1)
    else:
        try:
            config_file = find_config()
            config = load_config(config_file)
            vp = Path(config.vault_path)
            _check("Config", True, str(config_file))
        except ConfigNotFoundError as exc:
            _check("Config", False, "Not found")
            typer.echo("\nRun 'lionnotes init --vault-path <path>' first.")
            raise typer.Exit(1) from exc

    # 2. Check Obsidian CLI
    vname = vp.name if vp else None
    obsidian = ObsidianCLI(vault=vname)
    obsidian_ok = False
    try:
        ver = obsidian.version()
        _check("Obsidian CLI", True, f"v{ver}")
        if obsidian.check_version((1, 12)):
            _check("CLI version >= 1.12", True)
            obsidian_ok = True
        else:
            _check("CLI version >= 1.12", False, f"got v{ver}")
    except ObsidianNotFoundError:
        _check("Obsidian CLI", False, "Not in PATH")
    except ObsidianNotRunningError:
        _check("Obsidian CLI", False, "Not running")

    # 3. Check vault structure
    typer.echo("\nVault structure:")
    for note_name, _ in _INIT_FILES:
        if obsidian_ok:
            try:
                obsidian.read(note_name)
                _check(note_name, True)
            except ObsidianCLIError:
                _check(note_name, False, "missing")
        else:
            exists = _file_exists_direct(vp, note_name) if vp else False
            _check(note_name, exists, "" if exists else "missing")

    # 4. Soft triggers
    typer.echo("\nMaintenance:")
    if obsidian_ok:
        # Check inbox
        try:
            inbox = obsidian.read("_inbox/unsorted")
            entry_count = _count_entries(inbox)
            if entry_count > 0:
                _warn("Inbox", f"{entry_count} unsorted entries — consider triage")
            else:
                _check("Inbox", True, "empty")
        except ObsidianCLIError:
            _check("Inbox", True, "no inbox file")

        # Check maintenance queue
        try:
            mq = obsidian.read("_strategy/maintenance-queue")
            mq_entries = _count_entries(mq)
            if mq_entries > 0:
                _warn("Maintenance queue", f"{mq_entries} pending items")
            else:
                _check("Maintenance queue", True, "empty")
        except ObsidianCLIError:
            _check("Maintenance queue", True, "no queue file")
    elif vp:
        # Offline checks via direct file reads
        inbox_path = vp / "_inbox" / "unsorted.md"
        if inbox_path.is_file():
            content = inbox_path.read_text(encoding="utf-8")
            entry_count = _count_entries(content)
            if entry_count > 0:
                _warn("Inbox", f"{entry_count} unsorted entries — consider triage")
            else:
                _check("Inbox", True, "empty")
        else:
            _check("Inbox", True, "no inbox file")
    else:
        _warn("Maintenance checks", "skipped (no vault path)")

    typer.echo("\nDone.")
