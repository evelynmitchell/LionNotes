"""Speed thought capture for LionNotes."""

from __future__ import annotations

from lionnotes.config import Config, next_speed_number, save_config
from lionnotes.obsidian import ObsidianCLI, ObsidianCLIError
from lionnotes.subjects import SubjectError, normalize_subject_name


def _format_speed_entry(
    number: int,
    content: str,
    hint: str | None = None,
    thought_type: str | None = None,
) -> str:
    """Format a single speed entry line.

    Format: ``- S[N]: (context: hint) content #thought/type``
    """
    parts = [f"- S{number}:"]

    if hint:
        parts.append(f"(context: {hint})")

    parts.append(content)

    if thought_type:
        # Normalize: strip leading # and thought/ prefix if user included them
        tt = thought_type.lstrip("#").strip()
        if tt.startswith("thought/"):
            tt = tt[len("thought/") :]
        parts.append(f"#thought/{tt}")

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

    If *subject* is given, appends to ``{subject}/speeds``.
    If *subject* is None (pan-subject), appends to ``_inbox/unsorted``.

    Returns the formatted entry that was appended.
    Raises SubjectError if the subject doesn't exist.
    """
    content = content.strip()
    if not content:
        raise ValueError("Capture content cannot be empty.")

    # Normalize subject name to ensure consistent counter keys and paths
    if subject:
        subject = normalize_subject_name(subject)

    if subject:
        # Verify subject exists by checking SMOC, then speeds file
        try:
            obsidian.read(f"{subject}/SMOC")
        except ObsidianCLIError as exc:
            if exc.is_not_found:
                raise SubjectError(
                    f"Subject '{subject}' does not exist. "
                    "Create it first with 'lionnotes subjects create'."
                ) from exc
            raise

        try:
            obsidian.read(f"{subject}/speeds")
        except ObsidianCLIError as exc:
            if exc.is_not_found:
                raise SubjectError(
                    f"Subject '{subject}' exists but is missing its "
                    "speeds file. Re-create it or run 'lionnotes doctor'."
                ) from exc
            raise

        number = next_speed_number(config, subject)
        entry = _format_speed_entry(number, content, hint, thought_type)
        obsidian.append(f"{subject}/speeds", f"\n{entry}")
        save_config(config)
    else:
        # Pan-subject: use _inbox counter
        number = next_speed_number(config, "_inbox")
        entry = _format_speed_entry(number, content, hint, thought_type)
        obsidian.append("_inbox/unsorted", f"\n{entry}")
        save_config(config)

    return entry
