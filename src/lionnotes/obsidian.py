"""Wrapper around the official Obsidian CLI (v1.12+)."""

from __future__ import annotations

import subprocess

CLI_TIMEOUT_SECONDS = 30


class ObsidianCLIError(Exception):
    """The Obsidian CLI returned a non-zero exit code."""

    def __init__(self, args: list[str], returncode: int, stderr: str):
        self.cli_args = args
        self.returncode = returncode
        self.stderr = stderr
        msg = f"obsidian {' '.join(args)} failed (exit {returncode}): {stderr}"
        super().__init__(msg)

    @property
    def is_not_found(self) -> bool:
        """Return True if the error indicates a missing file/note."""
        lower = self.stderr.lower()
        return any(
            m in lower
            for m in ("not found", "does not exist", "no such", "doesn't exist")
        )


class ObsidianNotRunningError(Exception):
    """Cannot connect to a running Obsidian instance."""

    def __init__(self, detail: str = ""):
        msg = "Cannot connect to Obsidian. Is it running with CLI enabled?"
        if detail:
            msg += f" ({detail})"
        super().__init__(msg)


class ObsidianNotFoundError(Exception):
    """The obsidian binary is not in PATH."""

    def __init__(self):
        super().__init__(
            "The 'obsidian' command was not found. "
            "Install Obsidian v1.12+ and enable the CLI in Settings > General."
        )


class ObsidianCLI:
    """Wrapper around ``obsidian`` CLI (v1.12+).

    All vault I/O should go through this class so that the Obsidian search
    index, backlinks, and wikilink resolution stay consistent.
    """

    def __init__(self, vault: str | None = None):
        self.vault = vault

    # -- internal -----------------------------------------------------------

    @staticmethod
    def _quote(value: str) -> str:
        """Escape double quotes in a value for CLI key=value args."""
        return value.replace('"', '\\"')

    def _build_args(self, *args: str) -> list[str]:
        """Build the full argument list for a CLI invocation."""
        cmd: list[str] = ["obsidian"]
        if self.vault is not None:
            cmd.append(f"vault={self.vault}")
        cmd.extend(args)
        return cmd

    def _run(self, *args: str) -> str:
        """Execute an Obsidian CLI command and return stdout."""
        cmd = self._build_args(*args)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=CLI_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as exc:
            raise ObsidianNotFoundError() from exc
        except subprocess.TimeoutExpired as exc:
            raise ObsidianCLIError(cmd[1:], -1, "Command timed out") from exc

        stderr = result.stderr.strip()

        # Detect connection failures
        connection_markers = (
            "connection refused",
            "could not connect",
            "econnrefused",
            "not running",
            "no response",
        )
        lower_stderr = stderr.lower()
        if result.returncode != 0 and any(
            m in lower_stderr for m in connection_markers
        ):
            raise ObsidianNotRunningError(stderr)

        if result.returncode != 0:
            raise ObsidianCLIError(cmd[1:], result.returncode, stderr)

        return result.stdout

    # -- note operations ----------------------------------------------------

    def read(self, file: str) -> str:
        """Read a note's content."""
        return self._run("read", f'file="{self._quote(file)}"')

    def create(
        self,
        name: str,
        content: str = "",
        template: str | None = None,
        silent: bool = True,
    ) -> None:
        """Create a new note."""
        args = ["create", f'name="{self._quote(name)}"']
        if content:
            args.append(f'content="{self._quote(content)}"')
        if template:
            args.append(f'template="{self._quote(template)}"')
        if silent:
            args.append("silent")
        self._run(*args)

    def append(self, file: str, content: str) -> None:
        """Append content to an existing note."""
        self._run(
            "append",
            f'file="{self._quote(file)}"',
            f'content="{self._quote(content)}"',
        )

    def rename(self, file: str, new_name: str) -> None:
        """Rename a note (automatically updates wikilinks)."""
        self._run(
            "rename",
            f'file="{self._quote(file)}"',
            f'new_name="{self._quote(new_name)}"',
        )

    def delete(self, file: str) -> None:
        """Delete a note (moves to Obsidian trash)."""
        self._run("delete", f'file="{self._quote(file)}"')

    # -- search & discovery -------------------------------------------------

    def search(self, query: str, limit: int = 20) -> str:
        """Search the vault."""
        return self._run(
            "search",
            f'query="{self._quote(query)}"',
            f"limit={limit}",
        )

    def search_context(
        self,
        query: str,
        limit: int = 10,
    ) -> str:
        """Search the vault with surrounding context."""
        return self._run(
            "search:context",
            f'query="{self._quote(query)}"',
            f"limit={limit}",
        )

    def backlinks(self, file: str) -> str:
        """Get backlinks for a note."""
        return self._run("backlinks", f'file="{self._quote(file)}"')

    def tags(self, sort: str = "count") -> str:
        """List tags in the vault."""
        return self._run("tags", f"sort={sort}", "counts")

    # -- properties ---------------------------------------------------------

    def property_set(self, file: str, name: str, value: str) -> None:
        """Set a frontmatter property on a note."""
        self._run(
            "property:set",
            f'name="{self._quote(name)}"',
            f'value="{self._quote(value)}"',
            f'file="{self._quote(file)}"',
        )

    def property_get(self, file: str, name: str) -> str:
        """Get a frontmatter property from a note."""
        return self._run(
            "property:get",
            f'name="{self._quote(name)}"',
            f'file="{self._quote(file)}"',
        )

    # -- daily notes --------------------------------------------------------

    def daily_read(self) -> str:
        """Read today's daily note."""
        return self._run("daily:read")

    def daily_append(self, content: str) -> None:
        """Append to today's daily note."""
        self._run("daily:append", f'content="{self._quote(content)}"')

    # -- meta ---------------------------------------------------------------

    def version(self) -> str:
        """Return the Obsidian CLI version string."""
        return self._run("version").strip()

    def check_version(self, minimum: tuple[int, ...] = (1, 12)) -> bool:
        """Check if the CLI version meets the minimum requirement."""
        ver_str = self.version()
        # Parse version like "1.12.4" into tuple of ints
        try:
            parts = tuple(int(p) for p in ver_str.split(".")[: len(minimum)])
        except (ValueError, AttributeError):
            return False
        return parts >= minimum
