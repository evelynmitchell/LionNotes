"""Tests for the Mathlib critical-path analysis module."""

from __future__ import annotations

import io
import json
import textwrap

import pytest

from lionnotes.mathlib_critical_path import DependencyGraph

# -- DependencyGraph unit tests ------------------------------------------------


def _diamond_graph() -> DependencyGraph:
    """Build a diamond: A -> B -> D, A -> C -> D (D is the leaf)."""
    g = DependencyGraph()
    for name, t in [("A", 1.0), ("B", 3.0), ("C", 2.0), ("D", 1.0)]:
        g.add_module(name, compile_time=t)
    g.add_edge("A", "B")
    g.add_edge("A", "C")
    g.add_edge("B", "D")
    g.add_edge("C", "D")
    return g


def test_critical_path_diamond():
    g = _diamond_graph()
    path, duration = g.critical_path()
    # Critical path: D(1) -> B(3) -> A(1) = 5s  (longer than D->C->A = 4s)
    assert path == ["D", "B", "A"]
    assert duration == pytest.approx(5.0)


def test_critical_path_single_module():
    g = DependencyGraph()
    g.add_module("X", compile_time=7.5)
    path, duration = g.critical_path()
    assert path == ["X"]
    assert duration == pytest.approx(7.5)


def test_critical_path_empty():
    g = DependencyGraph()
    path, duration = g.critical_path()
    assert path == []
    assert duration == 0.0


def test_critical_path_linear_chain():
    """A -> B -> C (C is a leaf)."""
    g = DependencyGraph()
    for name, t in [("A", 2.0), ("B", 3.0), ("C", 1.0)]:
        g.add_module(name, compile_time=t)
    g.add_edge("A", "B")
    g.add_edge("B", "C")
    path, duration = g.critical_path()
    assert path == ["C", "B", "A"]
    assert duration == pytest.approx(6.0)


# -- I/O helpers ---------------------------------------------------------------


def test_from_edges_csv():
    csv_data = textwrap.dedent("""\
        A,B
        A,C
        B,D
        C,D
    """)
    g = DependencyGraph.from_edges_csv(io.StringIO(csv_data))
    assert "A" in g.modules
    assert "D" in g.modules
    assert "B" in g.imports["A"]
    assert "D" in g.imports["B"]


def test_load_times_from_csv():
    g = DependencyGraph()
    g.add_module("Mathlib.Algebra.Group")
    g.add_module("Mathlib.Data.List")
    csv_data = "Mathlib.Algebra.Group,12.5\nMathlib.Data.List,3.2\n"
    g.load_times_from_csv(io.StringIO(csv_data))
    assert g.modules["Mathlib.Algebra.Group"].compile_time == pytest.approx(12.5)
    assert g.modules["Mathlib.Data.List"].compile_time == pytest.approx(3.2)


def test_load_times_from_perfetto(tmp_path):
    g = DependencyGraph()
    g.add_module("Mathlib.Tactic.Ring")
    trace = {
        "traceEvents": [
            {"ph": "X", "name": "build Mathlib.Tactic.Ring", "dur": 5_000_000},
            {"ph": "B", "name": "ignored", "dur": 100},  # not a complete event
        ]
    }
    trace_file = tmp_path / "trace.json"
    trace_file.write_text(json.dumps(trace))
    g.load_times_from_perfetto(trace_file)
    assert g.modules["Mathlib.Tactic.Ring"].compile_time == pytest.approx(5.0)


# -- Bottleneck analysis -------------------------------------------------------


def test_bottleneck_modules():
    g = _diamond_graph()
    bottlenecks = g.bottleneck_modules(top_n=2)
    assert len(bottlenecks) == 2
    # B has the highest compile time (3s) and 1 transitive dependent (A)
    names = [b[0] for b in bottlenecks]
    assert "B" in names


# -- Summary -------------------------------------------------------------------


def test_summary_contains_key_sections():
    g = _diamond_graph()
    s = g.summary()
    assert "Critical path length:" in s
    assert "Modules:" in s
    assert "bottleneck" in s.lower()


# -- CLI integration -----------------------------------------------------------


def test_cli_missing_input():
    from typer.testing import CliRunner

    from lionnotes.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["mathlib-critical-path"])
    assert result.exit_code == 1
    assert "Error" in result.output


def test_cli_with_edges_csv(tmp_path):
    from typer.testing import CliRunner

    from lionnotes.cli import app

    csv_file = tmp_path / "edges.csv"
    csv_file.write_text("A,B\nB,C\n")
    times_file = tmp_path / "times.csv"
    times_file.write_text("A,2.0\nB,3.0\nC,1.0\n")

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "mathlib-critical-path",
            "--edges-csv", str(csv_file),
            "--times-csv", str(times_file),
        ],
    )
    assert result.exit_code == 0
    assert "Critical path length:" in result.output
