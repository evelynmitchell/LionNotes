# Kimbro Memory Architecture: Model Memory via Obsidian CLI

## Overview

This document defines the **behavioral protocol** for operating a memory system built on Lion Kimbro's notebook architecture, implemented as an Obsidian vault. The protocol applies equally to both human and LLM operators — they are co-equal peers sharing one vault.

**Operators interact through LionNotes tooling:** humans via the CLI (`lionnotes` commands), LLMs via the MCP server (which exposes the core capture, retrieval, and organization operations). Both interfaces delegate to the Obsidian CLI for all vault I/O. Some operations (e.g., `subjects merge/split`, `doctor`, `cache`) are CLI-only; see `implementation-plan.md` for the full tooling specification.

The key insight from Kimbro: **structure and integration matter more than the raw content of thoughts.** Once you have the structure, the content becomes almost obvious. This is exactly what a memory system needs — not just information, but organized, contextual recall.

---

## Part 1: Concept Mapping — Kimbro to Obsidian

### 1.1 Core Primitives

| Kimbro Concept | Vault Location | LionNotes CLI | MCP Tool |
|---|---|---|---|
| **Subject** | `{subject}/` folder | `lionnotes subjects list` / `create` | `list_subjects` |
| **Speed Thought** | `{subject}/speeds.md` (append-only) | `lionnotes capture -s SUBJECT` | `capture_speed` |
| **POI (Point of Interest)** | `{subject}/POI-N-title.md` | `lionnotes poi` | `create_poi` |
| **SMOC (Subject Map of Contents)** | `{subject}/SMOC.md` | `lionnotes map SUBJECT` | `read_smoc` |
| **GSMOC (Grand Subject Map of Contents)** | `GSMOC.md` | `lionnotes map` | `read_gsmoc` |
| **Pan-Subject Speed List** | `_inbox/unsorted.md` | `lionnotes capture` (no `-s`) | `capture_speed` (no subject) |
| **Out Card** | Auto-managed by Obsidian | `lionnotes subjects merge` | — |
| **References** | `{subject}/REF-N-title.md` | `lionnotes ref` | `add_reference` |
| **Abbreviations/Shorthand (A/S)** | `{subject}/glossary.md` | `lionnotes alias` | — |
| **Cheat Sheet** | `{subject}/cheatsheet.md` | — | — |
| **Purpose & Principles (P&P)** | `{subject}/purpose.md` | `lionnotes subjects pp` | `get_subject_pp` |
| **Archive** | `{subject}/_archive/` | `lionnotes cache archive` | — |
| **Strategy (Stickies)** | `_strategy/active-priorities.md` | `lionnotes strategy` | `get_strategy` / `set_strategy` |

### 1.2 The Four-Color System → Properties and Tags

Kimbro's four-color pen system encoded meaning through color. In Obsidian, we use frontmatter properties and tags:

| Color (Original) | Meaning | Obsidian Equivalent |
|---|---|---|
| **Black** | Primary content | Default text |
| **Blue** | Structure (page IDs, sequence marks) | `type:` property, wikilinks |
| **Red** | Alerts, archival marks, corrections | `status: stale`, `priority: high` properties |
| **Green** | Annotations, future notes, commentary | Callouts or `> [!note]` blocks, inline tags |

### 1.3 Kimbro's "Psi" Thought Types → Tags

Kimbro classified thoughts by type. These become standardized tags:

```
#thought/principle
#thought/observation
#thought/warning
#thought/action
#thought/goal
#thought/problem
#thought/starting-point
#thought/question
#thought/connection
```

---

## Part 2: Vault Structure

```
vault/
├── GSMOC.md                    # Grand Subject Map of Contents (the mirror of the mind)
├── _inbox/
│   └── unsorted.md             # Pan-subject speed list (temporary capture)
├── _templates/
│   ├── speed-page.md           # Template for new speed pages
│   ├── poi.md                  # Template for Points of Interest
│   ├── smoc.md                 # Template for Subject Maps
│   ├── reference.md            # Template for reference annotations
│   └── subject-bootstrap.md    # Template for initializing a new subject
├── _strategy/
│   ├── active-priorities.md    # Kimbro's "stickies" — what's hot right now
│   └── maintenance-queue.md    # Subjects needing reorganization
├── subject-name/
│   ├── SMOC.md                 # Subject Map of Contents
│   ├── purpose.md              # P&P: Purpose & Principles
│   ├── glossary.md             # A/S: Abbreviations & Shorthand
│   ├── speeds.md               # Speed thoughts (append-only log)
│   ├── cheatsheet.md           # Quick-reference summary
│   ├── POI-01-topic-name.md    # Point of Interest #1
│   ├── POI-02-topic-name.md    # Point of Interest #2
│   ├── REF-01-source-name.md   # Reference annotation #1
│   └── _archive/               # Archived pages (red "old" mark)
│       └── ...
├── another-subject/
│   └── ...
└── .lionnotes.toml             # LionNotes config (vault path, per-subject speed counters)
```

---

## Part 3: The Operator Protocol

This is the behavioral specification for anyone — human or LLM — using this vault as a memory system. It defines **when** and **how** operators read, write, and reorganize.

> **Note:** Examples below show both raw Obsidian CLI commands and their LionNotes equivalents. An LLM using the MCP server would call the corresponding MCP tools (e.g., `read_gsmoc`, `get_strategy`). A human would use `lionnotes` CLI commands. The behavioral rules are the same regardless of interface.
>
> **Path convention:** The Obsidian CLI `file=` parameter uses note names without the `.md` extension (e.g., `file="GSMOC"` refers to `GSMOC.md` on disk). This is standard Obsidian behavior — wikilinks like `[[GSMOC]]` also omit the extension.

### 3.1 Session Startup — Orientation

On every new session, the operator:

1. **Reads `GSMOC.md`** — gets the lay of the land. What subjects exist? What's the current structure?
2. **Reads `_strategy/active-priorities.md`** — what's currently important? (Kimbro's "stickies")
3. **Optionally scans recent daily notes** — what happened recently?
4. **Checks for soft triggers** — if `_inbox/unsorted.md` has many entries, triage is needed. If any subject has 30+ un-synthesized speeds, synthesis is due.

```bash
# Raw Obsidian CLI
obsidian read file="GSMOC"
obsidian read file="_strategy/active-priorities"
obsidian daily:read

# LionNotes CLI equivalents
lionnotes map           # reads GSMOC
lionnotes strategy list # reads active priorities
lionnotes doctor        # checks environment + flags soft triggers
```

This is the equivalent of Kimbro opening his carry-about binder and seeing his GSMOC with stickies on it.

### 3.2 Capture — Recording Thoughts

During a session, the model encounters new information, insights, or user-provided knowledge. Capture rules:

**Rule 1: Capture to the most specific place possible.**
If the model knows the subject, append directly to that subject's speed list. Avoid the inbox when possible. (Kimbro: "Avoid pan-subj speeds, save when you absolutely need them.")

```bash
# Preferred: direct to subject
obsidian append file="python/speeds" content="- S47: Generator expressions are lazy-evaluated, unlike list comprehensions #thought/observation"
# LionNotes: lionnotes capture -s python "Generator expressions are lazy-evaluated..." -t observation
# MCP: capture_speed(subject="python", content="...", type="observation")

# Fallback: inbox when subject is unclear
obsidian append file="_inbox/unsorted" content="- [python?] Generator memory behavior worth investigating #thought/question"
# LionNotes: lionnotes capture "Generator memory behavior worth investigating" -t question
# MCP: capture_speed(content="...", type="question")  — no subject = goes to inbox
```

**Rule 2: Record the context, not just the thought.**
Kimbro: "WHEN A NEW THOUGHT APPEARS, IT DOESN'T DO SO IN A VACUUM. IT DOES SO IN A CONTEXT." The hint/context is more important than the content itself.

```bash
obsidian append file="python/speeds" content="- S48: (context: debugging user's OOM error) Large list comprehensions in tight loops cause memory spikes — prefer generators #thought/principle"
```

**Rule 3: Use the Psi classification.**
Tag every speed thought with its type. This enables structured retrieval later.

### 3.3 Retrieval — Finding What You Know

Before responding to a question or starting a task, the model searches its memory:

```bash
# Search across the vault
obsidian search query="generators memory" limit=10

# Check a specific subject's map
obsidian read file="python/SMOC"

# Follow backlinks to find related thoughts
obsidian backlinks file="python/POI-03-memory-management"
```

**Retrieval strategy follows Kimbro's map hierarchy:**
1. Start at GSMOC → find the right subject
2. Go to that subject's SMOC → find the right POI or speed range
3. Read the specific note

This is **navigational retrieval**, not just keyword search. The model follows the map structure, which is far more reliable than hoping a search query matches.

### 3.4 Synthesis — Consolidating Speed Thoughts into POIs

This is the most important maintenance operation. When a subject accumulates many speed thoughts, patterns emerge. The model should consolidate them into structured POIs.

**Trigger:** A subject's speed list exceeds ~30 un-synthesized entries, OR the model notices a cluster of related speed thoughts.

**Process:**
1. Read the subject's speeds
2. Identify clusters of related thoughts
3. Create a new POI synthesizing the cluster
4. Update the SMOC to include the new POI
5. Mark synthesized speed entries by appending `[→ POI-N]` (e.g., `[→ POI-12]`)

```bash
# Raw Obsidian CLI
obsidian read file="python/speeds"
# Operator identifies S31-S38 all relate to async patterns
obsidian create name="python/POI-12-async-patterns" template="poi" silent
obsidian append file="python/SMOC" content="- [[POI-12-async-patterns]] — async/await patterns, gathered from S31-S38"

# LionNotes equivalents
lionnotes review -s python     # shows unmapped speeds, offers synthesis
lionnotes poi python "Async Patterns"  # creates POI-12 in python/ folder, auto-links from SMOC
```

**Kimbro's principle applies here: structure > content.** The POI's title and its position in the SMOC matter more than the details inside it. A well-mapped POI can be found; an unindexed one is lost.

### 3.5 Reorganization — Late Binding

Kimbro's Late Binding principle: **do reorganization work at the latest possible moment**, only when retrieval actually demands it.

**Do NOT:**
- Preemptively reorganize subjects
- Fix all out-of-date links proactively
- Restructure the GSMOC on a schedule

**DO:**
- Fix a broken link when you follow it and it doesn't resolve
- Split a subject when retrieval within it becomes slow or confused ("Divide when Big")
- Update the SMOC when you're already reading it and notice it's stale
- Archive notes only when they actively get in the way

```bash
# Only when a subject gets big and confusing:
obsidian create name="async-python/SMOC" template="smoc" silent
obsidian move file="python/POI-12-async-patterns" to="async-python/"
obsidian append file="GSMOC" content="- [[async-python/SMOC]] — split from python, covers async/await patterns"

# LionNotes equivalent (handles moves, SMOC updates, and GSMOC in one operation):
lionnotes subjects split python
```

### 3.6 Strategy — The Stickies

Kimbro used physical stickies on his GSMOC to mark currently important areas. The digital equivalent:

`_strategy/active-priorities.md` is a note the model reads on startup and updates as priorities shift. It answers: **What should I be paying attention to right now?**

```markdown
---
updated: 2026-03-07
---
# Active Priorities

- [[python/SMOC]] — User is actively working on Python project, keep this subject warm
- [[deployment/speeds]] — Recent speed thoughts suggest an emerging pattern, watch for synthesis opportunity
- [[GSMOC]] — Three new subjects added recently, GSMOC may need a reorganization pass
```

This is **not** a to-do list. It's an attention-direction mechanism. Kimbro's stickies were about focus, not completion.

---

## Part 4: Information Flow

Kimbro describes a clear flow of information through the system. For the model:

```
                    ┌─────────────┐
                    │  User Input │
                    │  & Context  │
                    └──────┬──────┘
                           │
                           ▼
                  ┌────────────────┐
                  │  _inbox/       │  Pan-subject capture
                  │  unsorted.md   │  (temporary, minimize use)
                  └───────┬────────┘
                          │ transcribe to subject
                          ▼
               ┌──────────────────────┐
               │  subject/speeds.md   │  Subject speed list
               │  (append-only log)   │  (primary capture target)
               └──────────┬───────────┘
                          │ synthesize when pattern emerges
                          ▼
               ┌──────────────────────┐
               │  subject/POI-N.md    │  Point of Interest
               │  (structured essay)  │  (synthesized knowledge)
               └──────────┬───────────┘
                          │ index in
                          ▼
               ┌──────────────────────┐
               │  subject/SMOC.md     │  Subject Map of Contents
               │  (navigational map)  │  (retrieval structure)
               └──────────┬───────────┘
                          │ index in
                          ▼
               ┌──────────────────────┐
               │  GSMOC.md            │  Grand Subject Map
               │  (mirror of mind)    │  (top-level orientation)
               └──────────────────────┘
```

Information moves **upward** from raw capture to structured knowledge. Retrieval moves **downward** from maps to specifics. This bidirectional flow is what makes it a *system* rather than a pile of notes.

---

## Part 5: Templates

### 5.1 Speed Page Template

```markdown
---
type: speeds
subject: "{{subject}}"
created: "{{date}}"
last_entry: null
entry_count: 0
---
# {{subject}} — Speed Thoughts

<!-- Append new speed thoughts below. Format: - S[N]: (context: ...) content #thought/type -->
```

### 5.2 POI Template

```markdown
---
type: poi
subject: "{{subject}}"
poi_number: null
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
```

### 5.3 SMOC Template

```markdown
---
type: smoc
subject: "{{subject}}"
version: 1
created: "{{date}}"
updated: "{{date}}"
---
# {{subject}} — Subject Map of Contents

## Purpose & Principles
<!-- Link to P&P note -->

## Map
<!-- Spatial/conceptual layout of this subject's knowledge. Group related POIs. Indicate importance by detail level. -->

### Core
<!-- The most important POIs -->

### Peripheral
<!-- Related but less central -->

### References
<!-- External sources annotated -->

## Speed Thoughts
- Current speed page: [[speeds]]
- Entry count: ...
- Last synthesized through: S...

## See Also
<!-- Cross-subject links -->
```

### 5.4 GSMOC Template

```markdown
---
type: gsmoc
version: 1
created: "{{date}}"
updated: "{{date}}"
---
# Grand Subject Map of Contents

> "The GSMOC is a mirror of the mind." — Lion Kimbro

## Active Subjects
<!-- Subjects currently being developed. Ordered by conceptual proximity, not alphabetically. -->

## Dormant Subjects
<!-- Subjects with content but not currently active. -->

## Emerging
<!-- Speed thoughts accumulating that may become subjects. -->

## Cross-Subject Connections
<!-- Links between subjects that don't belong to either. -->
```

---

## Part 6: Implementation Phases

### Phase 1: Foundation (MVP)

**Goal:** A working vault that an agent can read from and write to via the CLI.

- [ ] Create the vault directory structure
- [ ] Write all templates
- [ ] Create initial GSMOC with 2-3 seed subjects
- [ ] Write a `CLAUDE.md` (or agent system prompt) that teaches the Kimbro protocol
- [ ] Demonstrate the capture → speed → POI → SMOC → GSMOC pipeline with a worked example
- [ ] Test: agent can orient itself via GSMOC on cold start

### Phase 2: Agent Behaviors

**Goal:** Define and test the agent's behavioral rules.

- [ ] Implement capture rules (direct-to-subject vs. inbox fallback)
- [ ] Implement retrieval strategy (GSMOC → SMOC → POI navigation)
- [ ] Implement synthesis trigger (speed count threshold, cluster detection)
- [ ] Implement late-binding reorganization (only when retrieval fails)
- [ ] Implement strategy/priorities reading on startup
- [ ] Test: agent correctly navigates to relevant memory across multiple sessions

### Phase 3: Advanced Features

**Goal:** Leverage Obsidian and LLM capabilities beyond what paper could do.

- [ ] **Cross-subject synthesis:** Agent detects speed thoughts in different subjects that relate to each other, creates cross-reference POIs
- [ ] **Staleness detection:** Properties track when notes were last accessed; agent can identify and prune stale knowledge
- [ ] **Graph-based retrieval:** Use `obsidian backlinks` to traverse the knowledge graph, not just keyword search
- [ ] **Divide when Big:** Agent recognizes when a subject has grown too large and proposes a split
- [ ] **Versioning:** When a POI is substantially revised, archive the old version and create a new one (Kimbro's map version numbering: M1, M2, M3...)
- [ ] **Multi-agent memory:** Multiple agents sharing one vault, each with their own speed lists but shared POIs and GSMOC

### Phase 4: Evaluation

**Goal:** Measure whether structured memory actually improves model performance.

- [ ] Compare retrieval accuracy: Kimbro-structured vault vs. flat RAG over same content
- [ ] Measure "cold start" orientation time: how quickly can the agent find relevant prior knowledge?
- [ ] Test long-term coherence: does the agent maintain consistent understanding across many sessions?
- [ ] Evaluate synthesis quality: are the POIs actually useful, or just redundant summaries?

---

## Part 7: Key Design Decisions

### Why not just use RAG?

RAG (embedding + vector search) treats all information as equal-weight chunks. Kimbro's system adds:

1. **Hierarchy** — GSMOC → SMOC → POI gives navigational structure
2. **Strategy** — active priorities direct attention before search happens
3. **Synthesis** — raw speed thoughts are consolidated into structured knowledge
4. **Late binding** — organization is demand-driven, not preemptive
5. **Context preservation** — the "hint" records *why* a thought mattered, not just *what* it was

RAG answers "what's similar to this query?" Kimbro's system answers "what do I know about this, and how does it connect to everything else I know?"

### Why Obsidian specifically?

1. **CLI access** — the official CLI means agents can interact without fragile file-system hacking
2. **Link preservation** — `obsidian move` updates all wikilinks automatically (out cards that maintain themselves)
3. **Properties** — frontmatter provides structured metadata for the type/color system
4. **Graph** — the built-in graph view is literally Kimbro's GSMOC rendered visually
5. **Plugin ecosystem** — Dataview, Templater, etc. can extend the system
6. **Human-readable** — it's just Markdown files. A human can read, edit, and contribute to the same vault

### What about the "freezing" warning?

Kimbro warns that complete thought mapping has an "immobilizing" effect. For models, this is actually a feature: we *want* the model to slow down, record context, and think structurally rather than generating off the top of its weights. The "immobilization" that hurts humans (carrying binders everywhere, constant recording) is trivial for a model — it can append to a speed list in milliseconds.

The one Kimbro warning that *does* transfer: **resistance to new thinking.** If the model's POIs become too rigid, it may anchor to outdated structures. The late-binding principle and versioned maps are the antidote.

---

## Appendix: Example Session

```
[Agent cold start]
> obsidian read file="GSMOC"
  → Sees subjects: python, deployment, architecture, user-preferences
  → Notes "python" is most recently updated

> obsidian read file="_strategy/active-priorities"
  → "python" is marked as active priority — user working on Python project

[User asks: "How should I handle async database connections?"]

> obsidian read file="python/SMOC"
  → SMOC lists POI-12-async-patterns as relevant
  → Also sees speeds S44-S48 mention database connections

> obsidian read file="python/POI-12-async-patterns"
  → Gets structured knowledge about async/await patterns

> obsidian read file="python/speeds" (reads S44-S48 range)
  → Gets recent speed thoughts about database connections

[Agent responds with informed answer, then captures new knowledge]

> obsidian append file="python/speeds" content="- S49: (context: user async DB question) Connection pooling with asyncpg preferred over raw connections for async DB access #thought/principle"

[If this is the 5th speed thought about databases...]
[Agent notes cluster, flags for future synthesis into a POI]

> obsidian append file="_strategy/active-priorities" content="- [[python/speeds]] — database-related speeds clustering (S44-S49), synthesis candidate"
```

---

## Related Documents

- **`implementation-plan.md`** — the LionNotes CLI + MCP server specification that implements this protocol as tooling.
- **`corner-cases-review.md`** — edge cases and gaps identified during review.

## Next Steps

1. Implement the LionNotes tooling per `implementation-plan.md`
2. Embed the operator protocol (Part 3) into the vault's `CLAUDE.md` for LLM agents
3. Run a proof-of-concept session demonstrating the full pipeline with both human and LLM operators
