"""LionNotes CLI entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from lionnotes import __version__
from lionnotes.capture import CaptureError, capture_speed
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
from lionnotes.subjects import SubjectError, create_subject, list_subjects
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

# Sub-command group for subjects
subjects_app = typer.Typer(
    name="subjects",
    help="Manage subjects.",
    no_args_is_help=True,
)
app.add_typer(subjects_app, name="subjects")


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


# -- helpers ----------------------------------------------------------------


def _get_obsidian_and_config(
    vault_path: str | None = None,
) -> tuple[ObsidianCLI, Config]:
    """Resolve config and create an ObsidianCLI instance.

    Raises typer.Exit(1) on failure.
    """
    if vault_path:
        vp = Path(vault_path).resolve()
        config_file = vp / ".lionnotes.toml"
        if not config_file.is_file():
            typer.echo(
                f"Error: No .lionnotes.toml in {vp}. Run 'lionnotes init' first.",
                err=True,
            )
            raise typer.Exit(1)
        config = load_config(config_file)
    else:
        try:
            config_file = find_config()
            config = load_config(config_file)
        except ConfigNotFoundError:
            typer.echo(
                "Error: No .lionnotes.toml found. "
                "Run 'lionnotes init --vault-path <path>' first.",
                err=True,
            )
            raise typer.Exit(1)  # noqa: B904

    vp = Path(config.vault_path)
    vname = config.vault_name or vp.name
    obsidian = ObsidianCLI(vault=vname)

    # Verify Obsidian CLI is available
    try:
        obsidian.version()
    except ObsidianNotFoundError:
        typer.echo(
            "Error: Obsidian CLI not found. "
            "Install Obsidian v1.12+ and enable the CLI.",
            err=True,
        )
        raise typer.Exit(1)  # noqa: B904
    except ObsidianNotRunningError:
        typer.echo(
            "Error: Cannot connect to Obsidian. Is it running?",
            err=True,
        )
        raise typer.Exit(1)  # noqa: B904

    return obsidian, config


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

    config_path = vp / ".lionnotes.toml"
    if config_path.is_file():
        skipped.append(".lionnotes.toml")
    else:
        config = Config(vault_path=str(vp), vault_name=vname)
        save_config(config, config_path)
        created.append(".lionnotes.toml")

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
            _check(
                "Config",
                False,
                f"No .lionnotes.toml in {vp}",
            )
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

    typer.echo("\nMaintenance:")
    if obsidian_ok:
        try:
            inbox = obsidian.read("_inbox/unsorted")
            entry_count = _count_entries(inbox)
            if entry_count > 0:
                _warn(
                    "Inbox",
                    f"{entry_count} unsorted entries — consider triage",
                )
            else:
                _check("Inbox", True, "empty")
        except ObsidianCLIError:
            _check("Inbox", True, "no inbox file")

        try:
            mq = obsidian.read("_strategy/maintenance-queue")
            mq_entries = _count_entries(mq)
            if mq_entries > 0:
                _warn(
                    "Maintenance queue",
                    f"{mq_entries} pending items",
                )
            else:
                _check("Maintenance queue", True, "empty")
        except ObsidianCLIError:
            _check("Maintenance queue", True, "no queue file")
    elif vp:
        inbox_path = vp / "_inbox" / "unsorted.md"
        if inbox_path.is_file():
            content = inbox_path.read_text(encoding="utf-8")
            entry_count = _count_entries(content)
            if entry_count > 0:
                _warn(
                    "Inbox",
                    f"{entry_count} unsorted entries — consider triage",
                )
            else:
                _check("Inbox", True, "empty")
        else:
            _check("Inbox", True, "no inbox file")

        mq_path = vp / "_strategy" / "maintenance-queue.md"
        if mq_path.is_file():
            mq_content = mq_path.read_text(encoding="utf-8")
            mq_entries = _count_entries(mq_content)
            if mq_entries > 0:
                _warn(
                    "Maintenance queue",
                    f"{mq_entries} pending items",
                )
            else:
                _check("Maintenance queue", True, "empty")
        else:
            _check("Maintenance queue", True, "no queue file")
    else:
        _warn("Maintenance checks", "skipped (no vault path)")

    typer.echo("\nDone.")


# -- capture ----------------------------------------------------------------


@app.command()
def capture(
    content: str = typer.Argument(
        None,
        help="The thought to capture. Reads from stdin if omitted.",
    ),
    subject: str | None = typer.Option(None, "--subject", "-s", help="Target subject."),
    hint: str | None = typer.Option(
        None, "--hint", "-h", help="Context hint (1-3 words)."
    ),
    thought_type: str | None = typer.Option(
        None, "--type", "-t", help="Thought type (e.g. observation, question)."
    ),
    vault_path: str | None = typer.Option(
        None,
        "--vault-path",
        "-p",
        help="Vault path (default: auto-detect).",
    ),
):
    """Capture a speed thought."""
    # Read from stdin if no content argument
    if content is None:
        if sys.stdin.isatty():
            typer.echo(
                "Error: No content provided. Pass as argument or pipe via stdin.",
                err=True,
            )
            raise typer.Exit(1)
        content = sys.stdin.read()

    obsidian, config = _get_obsidian_and_config(vault_path)

    try:
        entry = capture_speed(
            content,
            obsidian,
            config,
            subject=subject,
            hint=hint,
            thought_type=thought_type,
        )
    except CaptureError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    target = subject or "inbox"
    typer.echo(f"Captured to {target}:")
    typer.echo(f"  {entry}")


# -- subjects ---------------------------------------------------------------


@subjects_app.command("create")
def subjects_create(
    name: str = typer.Argument(..., help="Subject name."),
    vault_path: str | None = typer.Option(
        None,
        "--vault-path",
        "-p",
        help="Vault path (default: auto-detect).",
    ),
):
    """Create a new subject."""
    obsidian, config = _get_obsidian_and_config(vault_path)

    try:
        normalized = create_subject(name, obsidian, config)
    except SubjectError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    typer.echo(f"Created subject '{normalized}' with:")
    typer.echo(f"  + {normalized}/SMOC.md")
    typer.echo(f"  + {normalized}/purpose.md")
    typer.echo(f"  + {normalized}/speeds.md")
    typer.echo(f"  + {normalized}/glossary.md")
    typer.echo(f"  + {normalized}/cheatsheet.md")


@subjects_app.command("list")
def subjects_list(
    vault_path: str | None = typer.Option(
        None,
        "--vault-path",
        "-p",
        help="Vault path (default: auto-detect).",
    ),
):
    """List all subjects in the vault."""
    obsidian, config = _get_obsidian_and_config(vault_path)
    subjects = list_subjects(obsidian, config)

    if not subjects:
        typer.echo("No subjects found.")
        return

    for s in subjects:
        flags = []
        if s.has_speeds:
            flags.append("speeds")
        if s.has_purpose:
            flags.append("P&P")
        suffix = f"  ({', '.join(flags)})" if flags else ""
        typer.echo(f"  {s.name}{suffix}")


# -- search -----------------------------------------------------------------


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query."),
    subject: str | None = typer.Option(
        None, "--subject", "-s", help="Scope to a subject folder."
    ),
    vault_path: str | None = typer.Option(
        None,
        "--vault-path",
        "-p",
        help="Vault path (default: auto-detect).",
    ),
):
    """Search the vault using Obsidian's index."""
    obsidian, config = _get_obsidian_and_config(vault_path)

    # Scope query to subject folder if specified
    search_query = query
    if subject:
        search_query = f"path:{subject} {query}"

    try:
        results = obsidian.search(search_query)
    except ObsidianCLIError as exc:
        typer.echo(f"Search failed: {exc}", err=True)
        raise typer.Exit(1) from exc

    output = results.strip()
    if not output:
        typer.echo("No results found.")
    else:
        typer.echo(output)
