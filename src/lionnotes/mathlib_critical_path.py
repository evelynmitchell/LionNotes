"""Critical-path analysis for Lean / Mathlib module dependency graphs.

Reads a module dependency DAG and per-module compile times (from Perfetto
JSON traces or a simple CSV), then computes the critical path — the
longest chain of sequential dependencies that determines the minimum
wall-clock build time.

Usage as a library::

    from lionnotes.mathlib_critical_path import DependencyGraph

    g = DependencyGraph.from_imports_dir("Mathlib/")
    g.load_times_from_perfetto("trace.json")
    path, duration = g.critical_path()

Or via the CLI::

    lionnotes mathlib-critical-path --imports-dir Mathlib/ --trace trace.json
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO


@dataclass
class ModuleInfo:
    """Metadata for a single Lean module."""

    name: str
    compile_time: float = 0.0  # seconds
    # longest path *from* this node to any sink (including own time)
    longest_path: float = 0.0
    longest_path_successor: str | None = None


@dataclass
class DependencyGraph:
    """Weighted DAG of Lean module dependencies.

    ``edges[A]`` contains the set of modules that *A imports* (i.e. A
    depends on each module in edges[A]).  For critical-path computation
    we need the *reverse* graph so that we can propagate from leaves
    (modules with no dependents) upward.
    """

    modules: dict[str, ModuleInfo] = field(default_factory=dict)
    # forward edges: module -> set of modules it imports
    imports: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    # reverse edges: module -> set of modules that import it
    dependents: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    # -- Construction helpers --------------------------------------------------

    def add_module(self, name: str, compile_time: float = 0.0) -> None:
        if name not in self.modules:
            self.modules[name] = ModuleInfo(name=name, compile_time=compile_time)
        else:
            self.modules[name].compile_time = compile_time

    def add_edge(self, importer: str, imported: str) -> None:
        """Record that *importer* depends on *imported*."""
        for m in (importer, imported):
            if m not in self.modules:
                self.add_module(m)
        self.imports[importer].add(imported)
        self.dependents[imported].add(importer)

    # -- I/O -------------------------------------------------------------------

    @classmethod
    def from_imports_dir(cls, root: str | Path) -> DependencyGraph:
        """Scan ``*.lean`` files under *root* and parse ``import`` statements."""
        g = cls()
        root = Path(root)
        for lean_file in sorted(root.rglob("*.lean")):
            mod_name = _path_to_module(lean_file, root)
            g.add_module(mod_name)
            with open(lean_file, encoding="utf-8") as fh:
                for line in fh:
                    m = _IMPORT_RE.match(line)
                    if m:
                        imported = m.group(1).strip()
                        g.add_edge(mod_name, imported)
                    # Stop scanning after the import block.
                    stripped = line.strip()
                    if (
                        stripped
                        and not stripped.startswith("import")
                        and not stripped.startswith("--")
                        and not stripped.startswith("#")
                    ):
                        break
        return g

    @classmethod
    def from_edges_csv(cls, file: str | Path | TextIO) -> DependencyGraph:
        """Load a two-column CSV ``importer,imported``."""
        g = cls()
        if isinstance(file, (str, Path)):
            fh = open(file, encoding="utf-8")  # noqa: SIM115
            should_close = True
        else:
            fh = file
            should_close = False
        try:
            reader = csv.reader(fh)
            for row in reader:
                if len(row) >= 2:
                    g.add_edge(row[0].strip(), row[1].strip())
        finally:
            if should_close:
                fh.close()
        return g

    def load_times_from_perfetto(self, trace_path: str | Path) -> None:
        """Read a Perfetto JSON trace and extract per-module durations.

        Expects the standard Trace Event Format with ``{"ph": "X", "name": ...}``
        complete-duration events.  Module names are extracted from the event
        ``name`` field (possibly stripping a ``"build "`` prefix).
        """
        with open(trace_path, encoding="utf-8") as fh:
            data = json.load(fh)

        events = data if isinstance(data, list) else data.get("traceEvents", [])
        for ev in events:
            if ev.get("ph") != "X":
                continue
            name: str = ev.get("name", "")
            # Lake traces typically prefix with "build " or similar.
            mod_name = re.sub(r"^(build|compile|elab)\s+", "", name).strip()
            dur_us = ev.get("dur", 0)
            dur_s = dur_us / 1_000_000
            if mod_name in self.modules:
                self.modules[mod_name].compile_time = dur_s
            else:
                # Try dotted -> slashed and vice-versa.
                if "/" in mod_name:
                    alt = mod_name.replace("/", ".")
                else:
                    alt = mod_name.replace(".", "/")
                if alt in self.modules:
                    self.modules[alt].compile_time = dur_s

    def load_times_from_csv(self, file: str | Path | TextIO) -> None:
        """Load ``module,seconds`` CSV."""
        if isinstance(file, (str, Path)):
            fh = open(file, encoding="utf-8")  # noqa: SIM115
            should_close = True
        else:
            fh = file
            should_close = False
        try:
            reader = csv.reader(fh)
            for row in reader:
                if len(row) >= 2:
                    name = row[0].strip()
                    try:
                        t = float(row[1].strip())
                    except ValueError:
                        continue
                    if name in self.modules:
                        self.modules[name].compile_time = t
        finally:
            if should_close:
                fh.close()

    # -- Analysis --------------------------------------------------------------

    def critical_path(self) -> tuple[list[str], float]:
        """Compute the critical path (longest weighted path) through the DAG.

        Uses reverse-topological-order dynamic programming.  Each module's
        *finish time* equals its own compile time plus the maximum finish
        time among the modules it imports (since they must finish first).

        Returns ``(path, total_seconds)`` where *path* is a list of module
        names from the root of the critical path down to the leaf.
        """
        # Kahn's algorithm for topological order (forward direction).
        in_degree: dict[str, int] = {m: 0 for m in self.modules}
        for m, deps in self.imports.items():
            for d in deps:
                if d in in_degree:
                    in_degree[m] = in_degree.get(m, 0)  # ensure exists
            in_degree[m] = len([d for d in deps if d in self.modules])

        queue: deque[str] = deque(m for m, deg in in_degree.items() if deg == 0)
        topo_order: list[str] = []
        while queue:
            node = queue.popleft()
            topo_order.append(node)
            for dep in self.dependents.get(node, set()):
                in_degree[dep] -= 1
                if in_degree[dep] == 0:
                    queue.append(dep)

        # DP in topological order: earliest finish time for each module.
        finish_time: dict[str, float] = {}
        predecessor: dict[str, str | None] = {}
        for m in topo_order:
            deps_in_graph = [d for d in self.imports.get(m, set()) if d in self.modules]
            if not deps_in_graph:
                finish_time[m] = self.modules[m].compile_time
                predecessor[m] = None
            else:
                best_dep = max(deps_in_graph, key=lambda d: finish_time.get(d, 0.0))
                finish_time[m] = (
                    finish_time.get(best_dep, 0.0)
                    + self.modules[m].compile_time
                )
                predecessor[m] = best_dep

        if not finish_time:
            return [], 0.0

        # The critical-path endpoint is the module with the largest finish time.
        end = max(finish_time, key=lambda m: finish_time[m])
        path: list[str] = []
        cur: str | None = end
        while cur is not None:
            path.append(cur)
            cur = predecessor.get(cur)
        path.reverse()

        return path, finish_time[end]

    def bottleneck_modules(self, top_n: int = 10) -> list[tuple[str, float, int]]:
        """Return modules sorted by impact: (name, compile_time, num_dependents).

        Modules that are both slow *and* have many transitive dependents
        are the best candidates for splitting or import pruning.
        """
        trans_deps = self._transitive_dependent_counts()
        results = [
            (name, info.compile_time, trans_deps.get(name, 0))
            for name, info in self.modules.items()
        ]
        # Score = compile_time * log2(1 + transitive_dependents)
        import math

        results.sort(
            key=lambda t: t[1] * math.log2(1 + t[2]),
            reverse=True,
        )
        return results[:top_n]

    def _transitive_dependent_counts(self) -> dict[str, int]:
        """Count transitive dependents for every module (BFS from each)."""
        counts: dict[str, int] = {}
        for m in self.modules:
            visited: set[str] = set()
            q: deque[str] = deque(self.dependents.get(m, set()))
            while q:
                n = q.popleft()
                if n in visited:
                    continue
                visited.add(n)
                q.extend(self.dependents.get(n, set()) - visited)
            counts[m] = len(visited)
        return counts

    def summary(self) -> str:
        """Return a human-readable summary of the critical path analysis."""
        path, duration = self.critical_path()
        lines = [
            f"Modules: {len(self.modules)}",
            f"Edges:   {sum(len(v) for v in self.imports.values())}",
            f"Critical path length: {len(path)} modules, {duration:.1f}s total",
            "",
            "Critical path (module -> compile time):",
        ]
        for m in path:
            t = self.modules[m].compile_time
            lines.append(f"  {m:60s} {t:8.2f}s")

        lines.append("")
        lines.append("Top bottleneck modules (slow + many dependents):")
        for name, ctime, ndeps in self.bottleneck_modules():
            lines.append(f"  {name:60s} {ctime:8.2f}s  ({ndeps} transitive dependents)")

        return "\n".join(lines)


# -- Helpers -------------------------------------------------------------------

_IMPORT_RE = re.compile(r"^\s*import\s+(.+)")


def _path_to_module(path: Path, root: Path) -> str:
    """Convert a file path to a dotted Lean module name."""
    rel = path.relative_to(root).with_suffix("")
    return ".".join(rel.parts)
