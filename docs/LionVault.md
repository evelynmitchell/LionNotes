# LionNotes as an Obsidian Vault

## Overview

Build the revised "How to Make a Complete Map of Every Thought You Think" as a
fully-linked Obsidian vault, using programmatic tooling (Python/shell scripts)
to generate the vault structure, frontmatter, wikilinks, and tags. The vault
will be both a readable digital book and a living demonstration of the
methodology it teaches.

Since we're in a headless environment (no Obsidian desktop app), we'll generate
the vault as plain Markdown files with Obsidian conventions. The official
Obsidian CLI (v1.12+) requires a running desktop instance, so our tooling will
be **file-based vault generation scripts** that produce a vault any user can
open in Obsidian.

---

## Architecture

```
LionNotes/
├── original/book.txt              # Source material (existing)
├── docs/                          # Project docs (existing)
├── scripts/                       # Vault generation tooling
│   ├── generate_vault.py          # Main vault generator
│   ├── parse_source.py            # Parse original book into sections
│   └── templates/                 # Frontmatter/note templates
├── vault/                         # Generated Obsidian vault
│   ├── .obsidian/                 # Vault config (themes, plugins)
│   │   ├── app.json
│   │   ├── appearance.json
│   │   └── core-plugins.json
│   ├── 00 - Front Matter/
│   │   ├── Index.md               # SMOC (Subject Map of Contents)
│   │   ├── About This Revision.md
│   │   └── How to Use This Vault.md
│   ├── 01 - Introduction/
│   │   ├── Introduction.md
│   │   └── Psychological Impact Warning.md
│   ├── 02 - Materials/
│   │   ├── Materials.md           # Revised: digital equivalents
│   │   └── Recommended Tools.md   # NEW (per PRD 4.2)
│   ├── 03 - General Principles/
│   │   ├── General Principles.md
│   │   ├── Late Binding.md        # Key concept, standalone note
│   │   └── Speed Habits.md
│   ├── 04 - Intra-Subject Architecture/
│   │   ├── Intra-Subject Architecture.md
│   │   ├── Caches.md
│   │   ├── Chronologs.md
│   │   └── Diagrams and Visual Thinking.md
│   ├── 05 - Extra-Subject Architecture/
│   │   ├── Extra-Subject Architecture.md
│   │   ├── Subject Map of Contents.md  # SMOC deep-dive
│   │   └── Backlinks and Graph Navigation.md  # NEW
│   ├── 06 - Theory of Notebooks/
│   │   ├── Theory of Notebooks.md
│   │   └── Digital Adaptation.md  # NEW
│   ├── 07 - The Question of Computers/
│   │   ├── The Question of Computers.md
│   │   ├── Markdown and Tags.md         # NEW (per PRD 4.1)
│   │   ├── ERDs and Knowledge Graphs.md # NEW (per PRD 4.1)
│   │   └── LLM Integration.md          # NEW (per PRD 4.1)
│   ├── 08 - Getting Started/
│   │   ├── Getting Started.md
│   │   └── Migration Path.md     # NEW (from Commentary)
│   ├── 09 - New Sections/
│   │   ├── Mindmaps and Knowledge Graphs.md  # NEW (per PRD 4.2)
│   │   ├── Privacy Considerations.md         # NEW (from Commentary)
│   │   ├── Data Portability.md               # NEW (from Commentary)
│   │   └── Collaboration.md                  # NEW (from Commentary)
│   ├── Concepts/                  # Atomic concept notes (Zettelkasten-style)
│   │   ├── SMOC.md
│   │   ├── Late Binding.md
│   │   ├── Speed Habits.md
│   │   ├── Cache.md
│   │   ├── Chronolog.md
│   │   ├── Out Card.md
│   │   ├── Category Bins.md
│   │   └── ...
│   ├── Templates/                 # Obsidian templates
│   │   ├── Chapter Template.md
│   │   ├── Concept Template.md
│   │   └── Commentary Template.md
│   └── Attachments/               # For diagrams, images
└── README.md                      # (if needed)
```

---

## Implementation Steps

### Phase 1: Source Parsing (`scripts/parse_source.py`)

Parse `original/book.txt` into structured sections:

1. Split by section dividers (`---...---` patterns around titles)
2. Extract chapter content between dividers
3. Identify key concepts (SMOC, Late Binding, Speed Habits, Caches, etc.)
4. Identify internal cross-references in the text
5. Output a structured JSON/dict representation of the book

### Phase 2: Vault Scaffolding (`scripts/generate_vault.py`)

Generate the Obsidian vault structure:

1. **Create `.obsidian/` config** with sensible defaults:
   - Enable backlinks, graph view, tags, outgoing links, templates
   - Set attachments folder
   - Configure template folder location

2. **Generate chapter notes** from parsed source:
   - YAML frontmatter: `title`, `tags`, `aliases`, `original_section`, `status`
   - Convert plain text to proper Markdown (headings, lists, emphasis)
   - Insert `[[wikilinks]]` for concept cross-references
   - Add `#tags` for categorization using hierarchical scheme:
     - `#chapter/introduction`, `#chapter/materials`, etc.
     - `#concept/core`, `#concept/digital-adaptation`
     - `#status/original`, `#status/revised`, `#status/new`

3. **Generate concept notes** (atomic notes for key ideas):
   - Each major concept gets its own note in `Concepts/`
   - Backlinks naturally form from chapter references
   - Include: definition, original context, digital adaptation notes

4. **Generate new section stubs** required by the PRD:
   - Markdown and Tags guide
   - ERDs and Knowledge Graphs
   - LLM Integration
   - Mindmaps and Knowledge Graphs
   - Recommended Tools

5. **Generate the Index (SMOC)** as a digitized Subject Map of Contents:
   - Links to all chapters and key concepts
   - Serves as the vault's home page
   - Demonstrates the SMOC concept itself (meta!)

6. **Color system adaptation** (from Commentary):
   - Map the 4-color pen system to Obsidian callout types:
     - `> [!note]` (blue) → factual content
     - `> [!tip]` (green) → actionable advice
     - `> [!warning]` (orange) → cautions/caveats
     - `> [!abstract]` (purple) → meta/structural notes

### Phase 3: Templates

Create Obsidian templates in `vault/Templates/`:

- **Chapter Template**: frontmatter skeleton + section structure
- **Concept Template**: definition, context, digital adaptation, related
- **Commentary Template**: for revision notes and editorial additions

### Phase 4: Digital Adaptations

Write the new content sections identified in the PRD and Commentary:

1. **Recommended Tools** (`02 - Materials/Recommended Tools.md`)
   - Obsidian, Logseq, Dendron, Notion
   - Graph databases (Neo4j, Memgraph)
   - LLM tools for note augmentation

2. **Markdown and Tags** (`07/.../Markdown and Tags.md`)
   - Practical guide to Markdown syntax for thought mapping
   - Tag taxonomy design for personal knowledge

3. **ERDs and Knowledge Graphs** (`07/.../ERDs and Knowledge Graphs.md`)
   - How to visualize thought networks
   - Obsidian graph view as a modern SMOC
   - Export to graph databases

4. **LLM Integration** (`07/.../LLM Integration.md`)
   - Using LLMs to process/query personal knowledge bases
   - MCP servers for Obsidian (linking to ecosystem)
   - Automated concept extraction and linking

5. **Mindmaps and Knowledge Graphs** (`09/.../Mindmaps and Knowledge Graphs.md`)
   - Relationship between mind maps and Kimbro's maps
   - Knowledge graph representations

6. **Late Binding digital adaptation** (expand `Concepts/Late Binding.md`)
   - Obsidian's alias and redirect capabilities
   - When to auto-update vs. preserve the late-binding principle

### Phase 5: Validation & Polish

1. **Link validation**: Script to check all `[[wikilinks]]` resolve to actual files
2. **Tag consistency**: Verify tag taxonomy is consistently applied
3. **Graph connectivity**: Ensure no orphan notes exist
4. **Accessibility**: Ensure alt-text on images, clear heading hierarchy (WCAG)
5. **License compliance**: Ensure all content remains compatible with the repository's CC0 1.0 Universal (public domain dedication) license

---

## Tag Taxonomy

```
#chapter/                    # Chapter tags
  introduction, materials, general-principles,
  intra-subject, extra-subject, theory,
  computers, getting-started

#concept/                    # Concept classification
  core                       # Original key concepts
  digital-adaptation         # New digital equivalents
  methodology                # Process/method concepts

#status/                     # Content status
  original                   # Directly from source
  revised                    # Updated from source
  new                        # New content for revision
  stub                       # Placeholder needing content

#type/                       # Note type
  chapter                    # Full chapter notes
  concept                    # Atomic concept notes
  guide                      # How-to/practical guides
  commentary                 # Editorial notes
```

---

## Frontmatter Schema

```yaml
---
title: "Note Title"
aliases:
  - "Alternative Name"
tags:
  - chapter/introduction
  - status/revised
original_section: "INTRODUCTION"    # Maps to source
date_created: 2026-03-07
date_modified: 2026-03-07
---
```

---

## Technology Choices

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Vault generation | Python scripts | Flexible, good string/file handling |
| File format | Plain Markdown + YAML frontmatter | Native Obsidian format, fully portable |
| Vault config | `.obsidian/` JSON files | Standard Obsidian config |
| Source parsing | Python regex + structure detection | Book has consistent divider patterns |
| Link validation | Python script | Check `[[...]]` patterns against filenames |
| No runtime dependency on Obsidian | By design | Works headless, any user opens result in Obsidian |

---

## What We Are NOT Doing

- **Not using the official Obsidian CLI** — it requires a running desktop app
  instance; we're generating files that *any* Obsidian installation can open
- **Not using MCP servers** — those also need a running Obsidian instance
- **Not building an Obsidian plugin** — the vault itself is the deliverable
- **Not auto-rewriting the entire book** — original text is preserved and
  attributed; new sections are clearly marked as additions
