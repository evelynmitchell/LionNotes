"""Tests for lionnotes.config."""

from pathlib import Path

import pytest

from lionnotes.config import (
    Config,
    ConfigNotFoundError,
    find_config,
    load_config,
    next_speed_number,
    save_config,
)


@pytest.fixture()
def vault_dir(tmp_path: Path) -> Path:
    """Create a temporary vault directory."""
    return tmp_path / "vault"


@pytest.fixture()
def config(vault_dir: Path) -> Config:
    """Create a minimal Config."""
    return Config(vault_path=str(vault_dir))


class TestSaveAndLoad:
    def test_round_trip_minimal(self, vault_dir: Path, config: Config):
        vault_dir.mkdir()
        save_config(config)
        loaded = load_config(config.config_path)
        assert loaded.vault_path == str(vault_dir)
        assert loaded.timezone is None
        assert loaded.speed_counters == {}

    def test_round_trip_full(self, vault_dir: Path):
        vault_dir.mkdir()
        config = Config(
            vault_path=str(vault_dir),
            vault_name="MyVault",
            timezone="America/New_York",
            speed_counters={"python": 47, "c++": 12},
        )
        save_config(config)
        loaded = load_config(config.config_path)
        assert loaded.vault_path == str(vault_dir)
        assert loaded.vault_name == "MyVault"
        assert loaded.timezone == "America/New_York"
        assert loaded.speed_counters == {"python": 47, "c++": 12}

    def test_save_creates_parent_dirs(self, vault_dir: Path, config: Config):
        # vault_dir doesn't exist yet — save_config should create it
        save_config(config)
        assert config.config_path.is_file()

    def test_load_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.toml")


class TestFindConfig:
    def test_finds_in_current_dir(self, vault_dir: Path, config: Config):
        vault_dir.mkdir()
        save_config(config)
        found = find_config(start=vault_dir)
        assert found == config.config_path

    def test_finds_in_parent_dir(self, vault_dir: Path, config: Config):
        vault_dir.mkdir()
        save_config(config)
        nested = vault_dir / "subject" / "deep"
        nested.mkdir(parents=True)
        found = find_config(start=nested)
        assert found == config.config_path

    def test_raises_when_not_found(self, tmp_path: Path):
        isolated = tmp_path / "no_config_here"
        isolated.mkdir()
        with pytest.raises(ConfigNotFoundError, match="No .lionnotes.toml found"):
            find_config(start=isolated)


class TestNextSpeedNumber:
    def test_first_speed_returns_1(self, config: Config):
        assert next_speed_number(config, "python") == 1
        assert config.speed_counters["python"] == 1

    def test_increments(self, config: Config):
        config.speed_counters["python"] = 47
        assert next_speed_number(config, "python") == 48
        assert next_speed_number(config, "python") == 49

    def test_independent_subjects(self, config: Config):
        next_speed_number(config, "python")
        next_speed_number(config, "rust")
        assert config.speed_counters["python"] == 1
        assert config.speed_counters["rust"] == 1

    def test_special_chars_in_subject_name(self, vault_dir: Path):
        """Subject names with special chars survive TOML round-trip."""
        vault_dir.mkdir()
        config = Config(vault_path=str(vault_dir))
        next_speed_number(config, "c++")
        next_speed_number(config, "node.js")
        save_config(config)
        loaded = load_config(config.config_path)
        assert loaded.speed_counters["c++"] == 1
        assert loaded.speed_counters["node.js"] == 1
