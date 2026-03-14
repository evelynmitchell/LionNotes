"""Tests for lionnotes.obsidian — Obsidian CLI wrapper."""

from unittest.mock import patch

import pytest

from lionnotes.obsidian import (
    ObsidianCLI,
    ObsidianCLIError,
    ObsidianNotFoundError,
    ObsidianNotRunningError,
)


def _make_completed_process(stdout="", stderr="", returncode=0):
    """Helper to build a subprocess.CompletedProcess."""
    import subprocess

    return subprocess.CompletedProcess(
        args=["obsidian"], stdout=stdout, stderr=stderr, returncode=returncode
    )


@pytest.fixture()
def cli():
    return ObsidianCLI()


@pytest.fixture()
def cli_with_vault():
    return ObsidianCLI(vault="TestVault")


class TestBuildArgs:
    def test_no_vault(self, cli: ObsidianCLI):
        assert cli._build_args("read", 'file="note"') == [
            "obsidian",
            "read",
            'file="note"',
        ]

    def test_with_vault(self, cli_with_vault: ObsidianCLI):
        assert cli_with_vault._build_args("read", 'file="note"') == [
            "obsidian",
            "vault=TestVault",
            "read",
            'file="note"',
        ]


class TestRun:
    @patch("lionnotes.obsidian.subprocess.run")
    def test_returns_stdout(self, mock_run, cli: ObsidianCLI):
        mock_run.return_value = _make_completed_process(stdout="note content\n")
        result = cli._run("read", 'file="test"')
        assert result == "note content\n"

    @patch("lionnotes.obsidian.subprocess.run")
    def test_raises_on_nonzero_exit(self, mock_run, cli: ObsidianCLI):
        mock_run.return_value = _make_completed_process(
            returncode=1, stderr="File not found"
        )
        with pytest.raises(ObsidianCLIError, match="File not found"):
            cli._run("read", 'file="missing"')

    @patch("lionnotes.obsidian.subprocess.run")
    def test_raises_not_running_on_connection_error(self, mock_run, cli: ObsidianCLI):
        mock_run.return_value = _make_completed_process(
            returncode=1, stderr="ECONNREFUSED: connect failed"
        )
        with pytest.raises(ObsidianNotRunningError, match="Is it running"):
            cli._run("read", 'file="test"')

    @patch("lionnotes.obsidian.subprocess.run")
    def test_raises_not_found_when_binary_missing(self, mock_run, cli: ObsidianCLI):
        mock_run.side_effect = FileNotFoundError()
        with pytest.raises(ObsidianNotFoundError, match="not found"):
            cli._run("version")

    @patch("lionnotes.obsidian.subprocess.run")
    def test_uses_utf8_encoding(self, mock_run, cli: ObsidianCLI):
        mock_run.return_value = _make_completed_process(stdout="emoji: 🦁\n")
        cli._run("read", 'file="test"')
        _, kwargs = mock_run.call_args
        assert kwargs["encoding"] == "utf-8"

    @patch("lionnotes.obsidian.subprocess.run")
    def test_has_timeout(self, mock_run, cli: ObsidianCLI):
        mock_run.return_value = _make_completed_process()
        cli._run("version")
        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 30

    @patch("lionnotes.obsidian.subprocess.run")
    def test_timeout_raises_cli_error(self, mock_run, cli: ObsidianCLI):
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="obsidian", timeout=30)
        with pytest.raises(ObsidianCLIError, match="timed out"):
            cli._run("read", 'file="slow"')


class TestNoteOperations:
    @patch("lionnotes.obsidian.subprocess.run")
    def test_read(self, mock_run, cli: ObsidianCLI):
        mock_run.return_value = _make_completed_process(stdout="# Hello\n")
        result = cli.read("my-note")
        cmd = mock_run.call_args[0][0]
        assert cmd == ["obsidian", "read", 'file="my-note"']
        assert result == "# Hello\n"

    @patch("lionnotes.obsidian.subprocess.run")
    def test_create_minimal(self, mock_run, cli: ObsidianCLI):
        mock_run.return_value = _make_completed_process()
        cli.create("new-note")
        cmd = mock_run.call_args[0][0]
        assert cmd == ["obsidian", "create", 'name="new-note"', "silent"]

    @patch("lionnotes.obsidian.subprocess.run")
    def test_create_with_content_and_template(self, mock_run, cli: ObsidianCLI):
        mock_run.return_value = _make_completed_process()
        cli.create("new-note", content="# Title", template="poi", silent=False)
        cmd = mock_run.call_args[0][0]
        assert 'content="# Title"' in cmd
        assert 'template="poi"' in cmd
        assert "silent" not in cmd

    @patch("lionnotes.obsidian.subprocess.run")
    def test_append(self, mock_run, cli: ObsidianCLI):
        mock_run.return_value = _make_completed_process()
        cli.append("note", "new line")
        cmd = mock_run.call_args[0][0]
        assert cmd == ["obsidian", "append", 'file="note"', 'content="new line"']

    @patch("lionnotes.obsidian.subprocess.run")
    def test_rename(self, mock_run, cli: ObsidianCLI):
        mock_run.return_value = _make_completed_process()
        cli.rename("old-name", "new-name")
        cmd = mock_run.call_args[0][0]
        assert 'file="old-name"' in cmd
        assert 'new_name="new-name"' in cmd


class TestSearch:
    @patch("lionnotes.obsidian.subprocess.run")
    def test_search(self, mock_run, cli: ObsidianCLI):
        mock_run.return_value = _make_completed_process(stdout="result1\nresult2\n")
        result = cli.search("generators", limit=5)
        cmd = mock_run.call_args[0][0]
        assert 'query="generators"' in cmd
        assert "limit=5" in cmd
        assert result == "result1\nresult2\n"

    @patch("lionnotes.obsidian.subprocess.run")
    def test_backlinks(self, mock_run, cli: ObsidianCLI):
        mock_run.return_value = _make_completed_process(stdout="note-a\nnote-b\n")
        result = cli.backlinks("my-note")
        cmd = mock_run.call_args[0][0]
        assert 'file="my-note"' in cmd
        assert result == "note-a\nnote-b\n"

    @patch("lionnotes.obsidian.subprocess.run")
    def test_tags(self, mock_run, cli: ObsidianCLI):
        mock_run.return_value = _make_completed_process()
        cli.tags(sort="name")
        cmd = mock_run.call_args[0][0]
        assert "sort=name" in cmd
        assert "counts" in cmd


class TestProperties:
    @patch("lionnotes.obsidian.subprocess.run")
    def test_property_set(self, mock_run, cli: ObsidianCLI):
        mock_run.return_value = _make_completed_process()
        cli.property_set("my-note", "status", "done")
        cmd = mock_run.call_args[0][0]
        assert 'name="status"' in cmd
        assert 'value="done"' in cmd
        assert 'file="my-note"' in cmd

    @patch("lionnotes.obsidian.subprocess.run")
    def test_property_get(self, mock_run, cli: ObsidianCLI):
        mock_run.return_value = _make_completed_process(stdout="draft")
        result = cli.property_get("my-note", "status")
        assert result == "draft"


class TestDailyNotes:
    @patch("lionnotes.obsidian.subprocess.run")
    def test_daily_read(self, mock_run, cli: ObsidianCLI):
        mock_run.return_value = _make_completed_process(stdout="today's notes\n")
        result = cli.daily_read()
        cmd = mock_run.call_args[0][0]
        assert "daily:read" in cmd
        assert result == "today's notes\n"

    @patch("lionnotes.obsidian.subprocess.run")
    def test_daily_append(self, mock_run, cli: ObsidianCLI):
        mock_run.return_value = _make_completed_process()
        cli.daily_append("- [ ] New task")
        cmd = mock_run.call_args[0][0]
        assert "daily:append" in cmd
        assert 'content="- [ ] New task"' in cmd


class TestVersion:
    @patch("lionnotes.obsidian.subprocess.run")
    def test_version(self, mock_run, cli: ObsidianCLI):
        mock_run.return_value = _make_completed_process(stdout="1.12.4\n")
        assert cli.version() == "1.12.4"

    @patch("lionnotes.obsidian.subprocess.run")
    def test_check_version_passes(self, mock_run, cli: ObsidianCLI):
        mock_run.return_value = _make_completed_process(stdout="1.12.4\n")
        assert cli.check_version((1, 12)) is True

    @patch("lionnotes.obsidian.subprocess.run")
    def test_check_version_fails(self, mock_run, cli: ObsidianCLI):
        mock_run.return_value = _make_completed_process(stdout="1.11.0\n")
        assert cli.check_version((1, 12)) is False

    @patch("lionnotes.obsidian.subprocess.run")
    def test_check_version_higher(self, mock_run, cli: ObsidianCLI):
        mock_run.return_value = _make_completed_process(stdout="2.0.0\n")
        assert cli.check_version((1, 12)) is True

    @patch("lionnotes.obsidian.subprocess.run")
    def test_check_version_unparseable(self, mock_run, cli: ObsidianCLI):
        mock_run.return_value = _make_completed_process(stdout="unknown\n")
        assert cli.check_version((1, 12)) is False
