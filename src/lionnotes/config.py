"""LionNotes configuration management (.lionnotes.toml)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import tomli_w

CONFIG_FILENAME = ".lionnotes.toml"


class ConfigNotFoundError(Exception):
    """Raised when .lionnotes.toml cannot be found."""


@dataclass
class Config:
    """LionNotes vault configuration."""

    vault_path: str
    timezone: str | None = None
    speed_counters: dict[str, int] = field(default_factory=dict)

    @property
    def config_path(self) -> Path:
        return Path(self.vault_path) / CONFIG_FILENAME


def find_config(start: Path | None = None) -> Path:
    """Walk up from *start* (default: cwd) looking for .lionnotes.toml.

    Returns the path to the config file.
    Raises ConfigNotFoundError if not found before reaching filesystem root.
    """
    current = (start or Path.cwd()).resolve()
    while True:
        candidate = current / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
        parent = current.parent
        if parent == current:
            raise ConfigNotFoundError(
                f"No {CONFIG_FILENAME} found in "
                f"{start or Path.cwd()} or any parent directory. "
                "Run 'lionnotes init --vault-path <path>' first."
            )
        current = parent


def load_config(path: Path) -> Config:
    """Load a Config from a .lionnotes.toml file."""
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return Config(
        vault_path=data["vault_path"],
        timezone=data.get("timezone"),
        speed_counters=data.get("speed_counters", {}),
    )


def save_config(config: Config, path: Path | None = None) -> None:
    """Write a Config to .lionnotes.toml."""
    target = path or config.config_path
    data: dict = {"vault_path": config.vault_path}
    if config.timezone is not None:
        data["timezone"] = config.timezone
    if config.speed_counters:
        data["speed_counters"] = config.speed_counters
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "wb") as f:
        tomli_w.dump(data, f)


def next_speed_number(config: Config, subject: str) -> int:
    """Increment and return the next speed number for a subject.

    Caller is responsible for saving the config afterward.
    """
    current = config.speed_counters.get(subject, 0)
    next_num = current + 1
    config.speed_counters[subject] = next_num
    return next_num
