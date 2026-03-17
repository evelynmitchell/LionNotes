"""Speed thought capture for LionNotes."""

from __future__ import annotations

from lionnotes.config import Config, next_speed_number, save_config
from lionnotes.obsidian import ObsidianCLI
from lionnotes.vault import (
    normalize_subject_name,
    subject_exists,
    validate_subject_name,
)

# Valid thought types (Kimbro's Psi classification)
THOUGHT_TYPES: frozenset[str] = frozenset(
    {
        "observation",
        "question",
        "goal",
        "problem",
        "action",
        "principle",
        "warning",
        "starting-point",
        "connection",
        "idea",
    }
)


class CaptureError(Exception):
    """Error during speed thought capture."""


def format_speed_entry(
    number: int,
    content: str,
    hint: str | None = None,
    thought_type: str | None = None,
) -> str:
    """Format a speed thought entry line.

    Format: ``- S[N]: (context: hint) content #thought/type``
    """
    parts = [f"- S{number}:"]

    if hint:
        parts.append(f"(context: {hint})")

    parts.append(content)

    if thought_type:
        parts.append(f"#thought/{thought_type}")

    return " ".join(parts)


def capture_speed(
    content: str,
    obsidian: ObsidianCLI,
    config: Config,
    subject: str | None = None,
    hint: str | None = None,
    thought_type: str | None = None,
) -> str:
    """Capture a speed thought.

    If *subject* is given, appends to ``{subject}/speeds.md``.
    If *subject* is None, appends to ``_inbox/unsorted.md``.

    Returns the formatted entry that was appended.

    Raises:
        CaptureError: If the subject doesn't exist or content is empty.
    """
    content = content.strip()
    if not content:
        raise CaptureError("Cannot capture an empty thought.")

    # Validate thought type if provided
    if thought_type and thought_type not in THOUGHT_TYPES:
        raise CaptureError(
            f"Unknown thought type '{thought_type}'. "
            f"Valid types: {', '.join(sorted(THOUGHT_TYPES))}"
        )

    if subject:
        # Validate and normalize
        error = validate_subject_name(subject)
        if error:
            raise CaptureError(error)
        subject = normalize_subject_name(subject)

        # Capture to subject
        if not subject_exists(subject, obsidian):
            raise CaptureError(
                f"Subject '{subject}' does not exist. "
                f"Create it first with: lionnotes subjects create {subject}"
            )

        number = next_speed_number(config, subject)
        entry = format_speed_entry(
            number, content, hint=hint, thought_type=thought_type
        )
        obsidian.append(f"{subject}/speeds", entry)
        save_config(config)
    else:
        # Capture to inbox (no numbering)
        parts = ["- "]
        if hint:
            parts.append(f"[{hint}?] ")
        parts.append(content)
        if thought_type:
            parts.append(f" #thought/{thought_type}")
        entry = "".join(parts)
        obsidian.append("_inbox/unsorted", entry)

    return entry
