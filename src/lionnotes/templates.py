"""Note template definitions and rendering for LionNotes."""

from __future__ import annotations

import re
from datetime import date


class TemplateError(Exception):
    """Raised for template rendering errors."""


# -- Template definitions ---------------------------------------------------

TEMPLATES: dict[str, str] = {
    "speed-page": """\
---
type: speeds
subject: "{{subject}}"
created: "{{date}}"
last_entry: null
entry_count: 0
---
# {{subject}} — Speed Thoughts

<!-- Append new speeds below. Format: - S[N]: (context: ...) content #thought/type -->
""",
    "poi": """\
---
type: poi
subject: "{{subject}}"
poi_number: {{poi_number}}
title: "{{title}}"
created: "{{date}}"
synthesized_from: []
status: draft
---
# POI {{poi_number}}: {{title}}

## Context
<!-- What prompted this synthesis? What speed thoughts fed into it? -->

## Content
<!-- The actual structured knowledge -->

## Connections
<!-- Links to related POIs, references, or other subjects -->

## Open Questions
<!-- What this POI doesn't resolve -->
""",
    "smoc": """\
---
type: smoc
subject: "{{subject}}"
version: 1
created: "{{date}}"
updated: "{{date}}"
---
# {{subject}} — Subject Map of Contents

## Purpose & Principles
- [[purpose]]

## Map

### Core
<!-- The most important POIs -->

### Peripheral
<!-- Related but less central -->

### References
<!-- External sources annotated -->

## Speed Thoughts
- Current speed page: [[speeds]]

## See Also
<!-- Cross-subject links -->
""",
    "gsmoc": """\
---
type: gsmoc
version: 1
created: "{{date}}"
updated: "{{date}}"
---
# Grand Subject Map of Contents

> "The GSMOC is a mirror of the mind." — Lion Kimbro

## Active Subjects
<!-- Subjects currently being developed. Ordered by conceptual proximity. -->

## Dormant Subjects
<!-- Subjects with content but not currently active. -->

## Emerging
<!-- Speed thoughts accumulating that may become subjects. -->

## Cross-Subject Connections
<!-- Links between subjects that don't belong to either. -->
""",
    "purpose": """\
---
type: pp
subject: "{{subject}}"
version: 1
includes: []
excludes: []
---
# {{subject}} — Purpose & Principles

## Purpose
<!-- What this subject is about -->

## Includes
<!-- What belongs in this subject -->

## Excludes
<!-- What does NOT belong — and where it goes instead -->
""",
    "reference": """\
---
type: reference
ref_number: {{ref_number}}
subject: "{{subject}}"
title: "{{title}}"
author: "{{author}}"
year: {{year}}
url: "{{url}}"
expanded: false
---
# REF {{ref_number}}: {{title}}

## Citation
{{author}} ({{year}})

## Notes
<!-- Annotations and key takeaways -->

## Connections
<!-- Links to related POIs or other references -->
""",
    "glossary": """\
---
type: glossary
subject: "{{subject}}"
---
# {{subject}} — Abbreviations & Shorthand

<!-- Define abbreviations used in this subject's notes -->
""",
    "cheatsheet": """\
---
type: cheatsheet
subject: "{{subject}}"
---
# {{subject}} — Cheat Sheet

<!-- Quick-reference summary for this subject -->
""",
    "inbox": """\
---
type: inbox
created: "{{date}}"
---
# Unsorted Speed Thoughts

<!-- Pan-subject speed thoughts awaiting triage. -->
<!-- Format: - [subject?] content #thought/type -->
""",
    "strategy": """\
---
type: strategy
updated: "{{date}}"
---
# Active Priorities

<!-- What should I be paying attention to right now? -->
<!-- This is an attention-direction mechanism, not a to-do list. -->
""",
    "maintenance-queue": """\
---
type: maintenance
updated: "{{date}}"
---
# Maintenance Queue

<!-- Subjects needing reorganization. Only add when retrieval demands it. -->
""",
    "subject-registry": """\
---
type: registry
updated: "{{date}}"
---
# Subject Registry

<!-- Index of all subjects with metadata. Auto-maintained by LionNotes. -->
""",
    "global-aliases": """\
---
type: aliases
updated: "{{date}}"
---
# Global Aliases

<!-- Abbreviations and shorthands used across all subjects. -->
""",
}

# Which variables are required for each template (others are optional)
REQUIRED_VARS: dict[str, set[str]] = {
    "speed-page": {"subject"},
    "poi": {"subject", "poi_number", "title"},
    "smoc": {"subject"},
    "gsmoc": set(),
    "purpose": {"subject"},
    "reference": {"subject", "ref_number", "title", "author", "year", "url"},
    "glossary": {"subject"},
    "cheatsheet": {"subject"},
    "inbox": set(),
    "strategy": set(),
    "maintenance-queue": set(),
    "subject-registry": set(),
    "global-aliases": set(),
}

# Pattern that matches only known variable placeholders
_VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def render(template_name: str, **variables: str | int) -> str:
    """Render a template with the given variables.

    ``{{date}}`` defaults to today (YYYY-MM-DD) if not provided.
    Only known ``{{variable}}`` placeholders are replaced — literal
    ``{{`` in content is not affected.

    Raises:
        TemplateError: If template_name is unknown or required variables are missing.
    """
    if template_name not in TEMPLATES:
        raise TemplateError(f"Unknown template: {template_name!r}")

    required = REQUIRED_VARS.get(template_name, set())
    missing = required - set(variables.keys())
    if missing:
        raise TemplateError(
            f"Template {template_name!r} requires variables: "
            f"{', '.join(sorted(missing))}"
        )

    # Default {{date}} to today
    if "date" not in variables:
        variables["date"] = date.today().isoformat()

    template = TEMPLATES[template_name]

    def _replace(match: re.Match) -> str:
        var_name = match.group(1)
        if var_name in variables:
            return str(variables[var_name])
        # Leave unknown placeholders as-is
        return match.group(0)

    return _VAR_PATTERN.sub(_replace, template)


def list_templates() -> list[str]:
    """Return all available template names."""
    return sorted(TEMPLATES.keys())
