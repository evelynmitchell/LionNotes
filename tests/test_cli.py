"""Smoke tests for the LionNotes CLI."""

from typer.testing import CliRunner

import lionnotes
from lionnotes.cli import app

runner = CliRunner()


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert f"lionnotes {lionnotes.__version__}" in result.output


def test_no_args_shows_help():
    result = runner.invoke(app, [])
    assert "Thought mapping" in result.output
