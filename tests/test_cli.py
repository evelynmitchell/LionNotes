"""Smoke tests for the LionNotes CLI."""

from typer.testing import CliRunner

from lionnotes.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "lionnotes 0.1.0" in result.output


def test_no_args_shows_help():
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Thought mapping" in result.output
