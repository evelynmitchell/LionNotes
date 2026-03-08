"""LionNotes: Thought mapping tooling for Obsidian."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("lionnotes")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"
