"""LionNotes CLI entrypoint."""

from __future__ import annotations

import contextlib
import re
import sys
from pathlib import Path

import typer

from lionnotes import __version__
from lionnotes.cache import (
    CacheError,
    activate_subject,
    archive_subject,
    get_tier,
    list_tiers,
    set_tier,
)
from lionnotes.capture import capture_speed
from lionnotes.config import (
    Config,
    ConfigNotFoundError,
    find_config,
    load_config,
    save_config,
)
from lionnotes.index import IndexBuildError, build_index
from lionnotes.maps import (
    MapError,
    read_gsmoc,
    read_smoc,
    rebuild_smoc,
    update_smoc,
)
from lionnotes.obsidian import (
    ObsidianCLI,
    ObsidianCLIError,
    ObsidianNotFoundError,
    ObsidianNotRunningError,
)
from lionnotes.review import (
    ReviewError,
    get_unmapped_speeds,
    triage_inbox,
)
from lionnotes.strategy import (
    StrategyError,
    add_priority,
    complete_priority,
    list_priorities,
)
from lionnotes.subjects import (
    SubjectError,
    create_subject,
    list_subjects,
    normalize_subject_name,
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
    vp = Path(vault_path).expanduser().resolve()
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
        config = Config(vault_path=str(vp), vault_name=vname)
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
        vp = Path(vault_path).expanduser().resolve()
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

        mq_path = vp / "_strategy" / "maintenance-queue.md"
        if mq_path.is_file():
            mq_content = mq_path.read_text(encoding="utf-8")
            mq_entries = _count_entries(mq_content)
            if mq_entries > 0:
                _warn("Maintenance queue", f"{mq_entries} pending items")
            else:
                _check("Maintenance queue", True, "empty")
        else:
            _check("Maintenance queue", True, "no queue file")
    else:
        _warn("Maintenance checks", "skipped (no vault path)")

    typer.echo("\nDone.")


# -- helpers for config/obsidian resolution ---------------------------------


def _resolve_config(vault_path: str | None = None) -> Config:
    """Find and load the LionNotes config."""
    err_msg = "Error: No .lionnotes.toml found. Run 'lionnotes init' first."
    if vault_path:
        config_file = Path(vault_path).expanduser().resolve() / ".lionnotes.toml"
        if not config_file.is_file():
            typer.echo(err_msg, err=True)
            raise typer.Exit(1)
        return load_config(config_file)
    try:
        return load_config(find_config())
    except ConfigNotFoundError:
        typer.echo(err_msg, err=True)
        raise typer.Exit(1) from None


def _resolve_obsidian(config: Config) -> ObsidianCLI:
    """Create an ObsidianCLI instance from config.

    Uses the persisted vault_name when available, falling back to
    the directory name of vault_path.
    """
    name = config.vault_name or Path(config.vault_path).name
    return ObsidianCLI(vault=name)


# -- capture ----------------------------------------------------------------


@app.command()
def capture(
    content: str | None = typer.Argument(None, help="The thought to capture."),
    subject: str | None = typer.Option(
        None, "--subject", "-s", help="Target subject (omit for pan-subject inbox)."
    ),
    hint: str | None = typer.Option(
        None, "--hint", "-h", help="Context hint (1-3 words)."
    ),
    thought_type: str | None = typer.Option(
        None, "--type", "-t", help="Thought type (observation, question, idea, etc.)."
    ),
):
    """Capture a speed thought."""
    # Read from stdin if no content argument
    if content is None:
        if sys.stdin.isatty():
            typer.echo("Error: Provide content as an argument or via stdin.", err=True)
            raise typer.Exit(1)
        content = sys.stdin.read().strip()
        if not content:
            typer.echo("Error: No content provided.", err=True)
            raise typer.Exit(1)

    config = _resolve_config()
    obsidian = _resolve_obsidian(config)

    try:
        # Normalize subject for display (capture_speed also normalizes)
        display_subject = normalize_subject_name(subject) if subject else None
        entry = capture_speed(
            content,
            obsidian,
            config,
            subject=subject,
            hint=hint,
            thought_type=thought_type,
        )
        target = display_subject or "inbox"
        typer.echo(f"Captured to {target}: {entry}")
    except (SubjectError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None


# -- subjects ---------------------------------------------------------------

subjects_app = typer.Typer(
    name="subjects",
    help="Manage subjects.",
    no_args_is_help=True,
)
app.add_typer(subjects_app)


@subjects_app.command("list")
def subjects_list(
    all_subjects: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Include archived subjects.",
    ),
):
    """List all subjects in the vault."""
    config = _resolve_config()
    obsidian = _resolve_obsidian(config)

    subjects = list_subjects(obsidian)
    if not subjects:
        typer.echo(
            "No subjects found. Create one with 'lionnotes subjects create NAME'."
        )
        return

    # Build tier lookup once to avoid redundant subprocess calls
    tier_map = {s: get_tier(s, obsidian) for s in subjects}

    # Filter out archived subjects unless --all is passed
    if not all_subjects:
        subjects = [s for s in subjects if tier_map[s] != "archive"]
        if not subjects:
            typer.echo("No active subjects. Use --all to include archived.")
            return

    typer.echo(f"Subjects ({len(subjects)}):")
    for s in subjects:
        tier = tier_map[s]
        if tier == "common-store":
            typer.echo(f"  - {s} [common]")
        elif tier == "archive":
            typer.echo(f"  - {s} [archived]")
        else:
            typer.echo(f"  - {s}")


@subjects_app.command("create")
def subjects_create(
    name: str = typer.Argument(..., help="Name for the new subject."),
):
    """Create a new subject with folder structure."""
    config = _resolve_config()
    obsidian = _resolve_obsidian(config)

    try:
        normalized = create_subject(name, obsidian, config)
        typer.echo(f"Created subject: {normalized}")
        typer.echo(f"  + {normalized}/SMOC")
        typer.echo(f"  + {normalized}/purpose")
        typer.echo(f"  + {normalized}/speeds")
        typer.echo(f"  + {normalized}/glossary")
    except SubjectError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None


# -- search -----------------------------------------------------------------


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query."),
    subject: str | None = typer.Option(
        None, "--subject", "-s", help="Scope search to a subject folder."
    ),
    context: bool = typer.Option(False, "--context", help="Show surrounding content."),
    speeds_only: bool = typer.Option(
        False, "--speeds-only", help="Only search speed notes."
    ),
    include_archived: bool = typer.Option(
        False,
        "--include-archived",
        help="Include results from archived subjects.",
    ),
):
    """Search the vault using Obsidian's index."""
    config = _resolve_config()
    obsidian = _resolve_obsidian(config)

    # Build the search query
    search_query = query
    if speeds_only:
        search_query = f"type: speeds {query}"

    try:
        if context:
            results = obsidian.search_context(search_query)
        else:
            results = obsidian.search(search_query)

        if not results or not results.strip():
            typer.echo("No results found.")
            return

        lines = results.strip().splitlines()

        # Filter out archived subjects unless --include-archived
        if not include_archived:
            if subject:
                # Subject-scoped: only check that one subject's tier
                try:
                    subj_name = normalize_subject_name(subject)
                except SubjectError:
                    subj_name = subject.strip().lower().replace(" ", "-")
                if get_tier(subj_name, obsidian) == "archive":
                    typer.echo(
                        f"Subject '{subject}' is archived."
                        " Use --include-archived to search it."
                    )
                    return
            else:
                tiers = list_tiers(obsidian)
                archived = set(tiers.get("archive", []))
                if archived:
                    filtered = []
                    for line in lines:
                        segments = line.strip().replace("\\", "/").split("/")
                        if not any(seg in archived for seg in segments):
                            filtered.append(line)
                    lines = filtered

        # Filter by subject if specified (path-segment match)
        if subject:
            try:
                normalized_subj = normalize_subject_name(subject)
            except SubjectError:
                normalized = subject.strip().lower().replace(" ", "-")
                while "--" in normalized:
                    normalized = normalized.replace("--", "-")
                normalized_subj = normalized
            filtered_lines = []
            for line in lines:
                segments = line.strip().replace("\\", "/").split("/")
                if normalized_subj in segments:
                    filtered_lines.append(line)
            if not filtered_lines:
                typer.echo(f"No results found in subject '{subject}'.")
                return
            typer.echo("\n".join(filtered_lines))
        else:
            if not lines:
                typer.echo("No results found.")
                return
            typer.echo("\n".join(lines))
    except ObsidianCLIError as exc:
        typer.echo(f"Search error: {exc}", err=True)
        raise typer.Exit(1) from None


# -- poi --------------------------------------------------------------------


def _slugify(text: str) -> str:
    """Sanitize text for use in filenames — only [a-z0-9-] allowed."""
    slug = text.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    # Collapse multiple dashes
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "untitled"


def _escape_yaml(value: str) -> str:
    """Escape a string for safe embedding in YAML frontmatter."""
    # Replace characters that could break YAML double-quoted strings
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _max_entry_number(smoc, prefix: str) -> int:
    """Extract the max number from SMOC entries matching prefix."""
    max_num = 0
    for entry in smoc.all_entries:
        link = entry.link
        if link and "/" not in link and link.startswith(f"{prefix}-"):
            parts = link.split("-")
            if len(parts) >= 2:
                with contextlib.suppress(ValueError):
                    max_num = max(max_num, int(parts[1]))
    return max_num


def _next_poi_number(subject: str, obsidian: ObsidianCLI) -> int:
    """Determine the next POI number for a subject."""
    return _max_entry_number(read_smoc(subject, obsidian), "POI") + 1


def _next_ref_number(subject: str, obsidian: ObsidianCLI) -> int:
    """Determine the next REF number for a subject."""
    return _max_entry_number(read_smoc(subject, obsidian), "REF") + 1


@app.command()
def poi(
    subject: str = typer.Argument(..., help="Target subject."),
    title: str = typer.Argument(..., help="POI title."),
):
    """Create a numbered Point of Interest note and link it from the SMOC."""
    config = _resolve_config()
    obsidian = _resolve_obsidian(config)

    try:
        normalized = normalize_subject_name(subject)
        poi_num = _next_poi_number(normalized, obsidian)
        poi_num_str = f"{poi_num:02d}"

        safe_title = _slugify(title)

        note_name = f"{normalized}/POI-{poi_num_str}-{safe_title}"
        content = render(
            "poi",
            subject=normalized,
            poi_number=poi_num,
            title=_escape_yaml(title),
        )
        obsidian.create(note_name, content=content)

        # Auto-link from SMOC
        smoc_entry = f"- [[POI-{poi_num_str}-{safe_title}]]"
        update_smoc(normalized, smoc_entry, obsidian)

        typer.echo(f"Created {note_name}")
        typer.echo(f"  Linked in {normalized}/SMOC")
    except (SubjectError, MapError, ObsidianCLIError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None


# -- ref --------------------------------------------------------------------


@app.command()
def ref(
    subject: str = typer.Argument(..., help="Target subject."),
    title: str = typer.Argument(..., help="Reference title."),
    url: str = typer.Option("", "--url", help="Source URL."),
    author: str = typer.Option("", "--author", help="Author name."),
    year: str = typer.Option("", "--year", help="Publication year."),
    notes: str | None = typer.Option(
        None,
        "--notes",
        help="Initial notes to add.",
    ),
):
    """Create a numbered Reference note and link it from the SMOC."""
    config = _resolve_config()
    obsidian = _resolve_obsidian(config)

    try:
        normalized = normalize_subject_name(subject)
        ref_num = _next_ref_number(normalized, obsidian)
        ref_num_str = f"{ref_num:02d}"

        safe_title = _slugify(title)

        note_name = f"{normalized}/REF-{ref_num_str}-{safe_title}"
        content = render(
            "reference",
            subject=normalized,
            ref_number=ref_num,
            title=_escape_yaml(title),
            author=_escape_yaml(author or "Unknown"),
            year=_escape_yaml(year or "n.d."),
            url=_escape_yaml(url),
        )
        if notes:
            content = content.replace(
                "<!-- Annotations and key takeaways -->",
                notes,
            )
        obsidian.create(note_name, content=content)

        # Auto-link from SMOC References section
        smoc_entry = f"- [[REF-{ref_num_str}-{safe_title}]]"
        update_smoc(normalized, smoc_entry, obsidian, section="references")

        typer.echo(f"Created {note_name}")
        typer.echo(f"  Linked in {normalized}/SMOC")
    except (SubjectError, MapError, ObsidianCLIError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None


# -- map --------------------------------------------------------------------


@app.command("map")
def map_cmd(
    subject: str | None = typer.Argument(
        None,
        help="Subject to view SMOC for (omit for GSMOC).",
    ),
    rebuild: bool = typer.Option(
        False,
        "--rebuild",
        help="Rebuild SMOC from vault contents.",
    ),
):
    """View a subject's SMOC or the Grand SMOC."""
    config = _resolve_config()
    obsidian = _resolve_obsidian(config)

    try:
        if subject:
            normalized = normalize_subject_name(subject)
            if rebuild:
                rebuild_smoc(normalized, obsidian)
                typer.echo(f"Rebuilt SMOC for {normalized}.")
            smoc = read_smoc(normalized, obsidian)
            typer.echo(smoc.raw.strip())
        else:
            gsmoc = read_gsmoc(obsidian)
            typer.echo(gsmoc.raw.strip())
    except (SubjectError, ObsidianCLIError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None


# -- review -----------------------------------------------------------------


@app.command()
def review(
    subject: str | None = typer.Option(
        None,
        "--subject",
        "-s",
        help="Subject to review unmapped speeds for.",
    ),
    pan: bool = typer.Option(
        False,
        "--pan",
        help="Show inbox entries for triage.",
    ),
):
    """Review unmapped speed thoughts for triage."""
    config = _resolve_config()
    obsidian = _resolve_obsidian(config)

    try:
        if pan:
            entries = triage_inbox(obsidian)
            if not entries:
                typer.echo("Inbox is empty.")
                return
            typer.echo(f"Inbox entries ({len(entries)}):")
            for e in entries:
                ctx = f" (context: {e.context})" if e.context else ""
                tag = f" {e.thought_type}" if e.thought_type else ""
                typer.echo(f"  S{e.number}:{ctx} {e.content}{tag}")
        elif subject:
            normalized = normalize_subject_name(subject)
            entries = get_unmapped_speeds(normalized, obsidian)
            if not entries:
                typer.echo(f"No unmapped speeds in {normalized}.")
                return
            typer.echo(f"Unmapped speeds in {normalized} ({len(entries)}):")
            for e in entries:
                ctx = f" (context: {e.context})" if e.context else ""
                tag = f" {e.thought_type}" if e.thought_type else ""
                typer.echo(f"  S{e.number}:{ctx} {e.content}{tag}")
        else:
            typer.echo(
                "Specify --subject/-s for a subject or --pan for inbox.",
                err=True,
            )
            raise typer.Exit(1)
    except (SubjectError, ReviewError, ObsidianCLIError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None


# -- subjects pp ------------------------------------------------------------


@subjects_app.command("pp")
def subjects_pp(
    name: str = typer.Argument(..., help="Subject name."),
):
    """View a subject's Purpose & Principles."""
    config = _resolve_config()
    obsidian = _resolve_obsidian(config)

    try:
        normalized = normalize_subject_name(name)
        content = obsidian.read(f"{normalized}/purpose")
        typer.echo(content.strip())
    except ObsidianCLIError as exc:
        if exc.is_not_found:
            typer.echo(
                f"Error: Purpose & Principles not found for '{name}'.",
                err=True,
            )
        else:
            typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None
    except SubjectError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None


# -- strategy ---------------------------------------------------------------

strategy_app = typer.Typer(
    name="strategy",
    help="Manage active priorities.",
    no_args_is_help=True,
)
app.add_typer(strategy_app)


@strategy_app.command("list")
def strategy_list():
    """Display active priorities."""
    config = _resolve_config()
    obsidian = _resolve_obsidian(config)

    try:
        items = list_priorities(obsidian)
        if not items:
            typer.echo("No active priorities.")
            return
        typer.echo(f"Active priorities ({len(items)}):")
        for item in items:
            typer.echo(f"  {item.number}. [{item.subject}] {item.description}")
    except ObsidianCLIError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None


@strategy_app.command("add")
def strategy_add(
    subject: str = typer.Argument(..., help="Subject this priority relates to."),
    description: str = typer.Argument(..., help="Priority description."),
):
    """Add a new active priority."""
    config = _resolve_config()
    obsidian = _resolve_obsidian(config)

    try:
        item = add_priority(subject, description, obsidian)
        typer.echo(
            f"Added priority #{item.number}: [{item.subject}] {item.description}"
        )
    except (StrategyError, ObsidianCLIError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None


@strategy_app.command("done")
def strategy_done(
    item: int = typer.Argument(..., help="Priority number to complete."),
):
    """Mark a priority as done (removes it from the list)."""
    config = _resolve_config()
    obsidian = _resolve_obsidian(config)

    try:
        removed = complete_priority(item, obsidian)
        typer.echo(
            f"Completed priority #{removed.number}: "
            f"[{removed.subject}] {removed.description}"
        )
    except (StrategyError, ObsidianCLIError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None


# -- cache ------------------------------------------------------------------

cache_app = typer.Typer(
    name="cache",
    help="Manage subject tiers (carry-about / common-store / archive).",
    no_args_is_help=True,
)
app.add_typer(cache_app)


@cache_app.command("status")
def cache_status():
    """Show subjects grouped by tier."""
    config = _resolve_config()
    obsidian = _resolve_obsidian(config)

    try:
        tiers = list_tiers(obsidian)
        for tier_name in ("carry-about", "common-store", "archive"):
            subjects = tiers[tier_name]
            typer.echo(f"{tier_name} ({len(subjects)}):")
            if subjects:
                for s in subjects:
                    typer.echo(f"  - {s}")
            else:
                typer.echo("  (none)")
    except ObsidianCLIError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None


@cache_app.command("archive")
def cache_archive(
    subject: str = typer.Argument(..., help="Subject to archive."),
):
    """Move a subject to the archive tier."""
    config = _resolve_config()
    obsidian = _resolve_obsidian(config)

    try:
        archive_subject(subject, obsidian)
        normalized = normalize_subject_name(subject)
        typer.echo(f"Archived: {normalized}")
    except (CacheError, SubjectError, ObsidianCLIError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None


@cache_app.command("promote")
def cache_promote(
    subject: str = typer.Argument(..., help="Subject to promote to carry-about."),
):
    """Promote a subject to the carry-about tier."""
    config = _resolve_config()
    obsidian = _resolve_obsidian(config)

    try:
        activate_subject(subject, obsidian)
        normalized = normalize_subject_name(subject)
        typer.echo(f"Promoted: {normalized}")
    except (CacheError, SubjectError, ObsidianCLIError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None


@cache_app.command("set")
def cache_set(
    subject: str = typer.Argument(..., help="Subject name."),
    tier: str = typer.Argument(
        ..., help="Tier: carry-about, common-store, or archive."
    ),
):
    """Set a subject's tier directly."""
    config = _resolve_config()
    obsidian = _resolve_obsidian(config)

    try:
        set_tier(subject, tier, obsidian)
        normalized = normalize_subject_name(subject)
        typer.echo(f"Set {normalized} to {tier}")
    except (CacheError, SubjectError, ObsidianCLIError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None


# -- index ------------------------------------------------------------------


@app.command("index")
def index_cmd(
    subject: str = typer.Argument(..., help="Subject to build index for."),
):
    """Build or rebuild the keyword index for a subject."""
    config = _resolve_config()
    obsidian = _resolve_obsidian(config)

    try:
        normalized = normalize_subject_name(subject)
        build_index(normalized, obsidian)
        typer.echo(f"Built index for {normalized}")
        typer.echo(f"  + {normalized}/Index")
    except (IndexBuildError, SubjectError, ObsidianCLIError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None
