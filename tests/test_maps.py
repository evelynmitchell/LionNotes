"""Tests for lionnotes.maps module."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lionnotes.maps import (
    MapError,
    read_gsmoc,
    read_smoc,
    rebuild_smoc,
    update_gsmoc,
    update_smoc,
)
from lionnotes.obsidian import ObsidianCLIError


def _get_created_content(obs):
    """Extract content from the last obs.create() call."""
    args = obs.create.call_args
    return args.kwargs.get(
        "content",
        args.args[1] if len(args.args) > 1 else "",
    )


# -- Sample SMOC content ----------------------------------------------------

SAMPLE_SMOC = """\
---
type: smoc
subject: "python"
version: 1
created: "2026-01-01"
updated: "2026-01-01"
---
# python — Subject Map of Contents

## Purpose & Principles
- [[purpose]]

## Map

### Core
<!-- The most important POIs -->
- [[POI-01-decorators]]
- [[POI-02-generators]]

### Peripheral
<!-- Related but less central -->
- [[POI-03-type-hints]]

### References
<!-- External sources annotated -->
- [[REF-01-pep484]]

## Speed Thoughts
- Current speed page: [[speeds]]

## See Also
<!-- Cross-subject links -->
"""

SAMPLE_SMOC_WITH_ANNOTATIONS = """\
---
type: smoc
subject: "python"
version: 1
created: "2026-01-01"
updated: "2026-01-01"
---
# python — Subject Map of Contents

## Purpose & Principles
- [[purpose]]

## Map

### Core
<!-- The most important POIs -->
- [[POI-01-decorators]] — foundational pattern
- [[POI-02-generators]] — lazy evaluation

### Peripheral
<!-- Related but less central -->

### References
<!-- External sources annotated -->

## Speed Thoughts
- Current speed page: [[speeds]]
"""

SAMPLE_GSMOC = """\
---
type: gsmoc
version: 1
created: "2026-01-01"
updated: "2026-01-01"
---
# Grand Subject Map of Contents

> "The GSMOC is a mirror of the mind." — Lion Kimbro

## Active Subjects
<!-- Subjects currently being developed. Ordered by conceptual proximity. -->
- [[python/SMOC|python]]

## Dormant Subjects
<!-- Subjects with content but not currently active. -->

## Emerging
<!-- Speed thoughts accumulating that may become subjects. -->

## Cross-Subject Connections
<!-- Links between subjects that don't belong to either. -->
"""

EMPTY_SMOC = """\
---
type: smoc
subject: "new-topic"
version: 1
created: "2026-01-01"
updated: "2026-01-01"
---
# new-topic — Subject Map of Contents

## Purpose & Principles
- [[purpose]]

## Map

### Core
<!-- The most important POIs -->

### Peripheral
<!-- Related but less central -->

### References
<!-- External sources annotated -->

## Speed Thoughts
- Current speed page: [[speeds]]

## See Also
<!-- Cross-subject links -->
"""


# -- read_smoc tests --------------------------------------------------------


class TestReadSmoc:
    def test_parses_core_entries(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_SMOC

        smoc = read_smoc("python", obs)

        assert len(smoc.core) == 2
        assert smoc.core[0].link == "POI-01-decorators"
        assert smoc.core[1].link == "POI-02-generators"

    def test_parses_peripheral_entries(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_SMOC

        smoc = read_smoc("python", obs)

        assert len(smoc.peripheral) == 1
        assert smoc.peripheral[0].link == "POI-03-type-hints"

    def test_parses_references(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_SMOC

        smoc = read_smoc("python", obs)

        assert len(smoc.references) == 1
        assert smoc.references[0].link == "REF-01-pep484"

    def test_all_links(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_SMOC

        smoc = read_smoc("python", obs)

        assert smoc.all_links == {
            "POI-01-decorators",
            "POI-02-generators",
            "POI-03-type-hints",
            "REF-01-pep484",
        }

    def test_empty_smoc(self):
        obs = MagicMock()
        obs.read.return_value = EMPTY_SMOC

        smoc = read_smoc("new-topic", obs)

        assert smoc.core == []
        assert smoc.peripheral == []
        assert smoc.references == []

    def test_preserves_raw(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_SMOC

        smoc = read_smoc("python", obs)

        assert smoc.raw == SAMPLE_SMOC

    def test_reads_correct_file(self):
        obs = MagicMock()
        obs.read.return_value = EMPTY_SMOC

        read_smoc("my-subject", obs)

        obs.read.assert_called_once_with("my-subject/SMOC")

    def test_preserves_annotations(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_SMOC_WITH_ANNOTATIONS

        smoc = read_smoc("python", obs)

        assert len(smoc.core) == 2
        assert "foundational pattern" in smoc.core[0].line
        assert smoc.core[0].link == "POI-01-decorators"


# -- update_smoc tests ------------------------------------------------------


class TestUpdateSmoc:
    def test_adds_poi_to_core(self):
        obs = MagicMock()
        obs.read.return_value = EMPTY_SMOC

        update_smoc("new-topic", "- [[POI-01-my-idea]]", obs)

        # Should have renamed old and created new
        obs.rename.assert_called()
        obs.create.assert_called()
        created_content = _get_created_content(obs)
        assert "[[POI-01-my-idea]]" in created_content

    def test_idempotent(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_SMOC

        # POI-01-decorators is already in the SMOC
        update_smoc("python", "- [[POI-01-decorators]]", obs)

        # Should not write anything
        obs.rename.assert_not_called()
        obs.create.assert_not_called()

    def test_adds_to_references_section(self):
        obs = MagicMock()
        obs.read.return_value = EMPTY_SMOC

        update_smoc(
            "new-topic",
            "- [[REF-01-source]]",
            obs,
            section="references",
        )

        obs.create.assert_called()
        created_content = _get_created_content(obs)
        assert "[[REF-01-source]]" in created_content

    def test_unknown_section_raises(self):
        obs = MagicMock()
        obs.read.return_value = EMPTY_SMOC

        with pytest.raises(MapError, match="Unknown SMOC section"):
            update_smoc("new-topic", "- [[POI-01-x]]", obs, section="invalid")


# -- read_gsmoc tests -------------------------------------------------------


class TestReadGsmoc:
    def test_parses_active_subjects(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_GSMOC

        gsmoc = read_gsmoc(obs)

        assert len(gsmoc.active) == 1
        assert gsmoc.active[0].link == "python/SMOC"

    def test_empty_sections(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_GSMOC

        gsmoc = read_gsmoc(obs)

        assert gsmoc.dormant == []
        assert gsmoc.emerging == []

    def test_reads_gsmoc_file(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_GSMOC

        read_gsmoc(obs)

        obs.read.assert_called_once_with("GSMOC")


# -- update_gsmoc tests -----------------------------------------------------


class TestUpdateGsmoc:
    def test_adds_subject(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_GSMOC

        update_gsmoc("- [[rust/SMOC|rust]]", obs)

        obs.create.assert_called()
        created_content = _get_created_content(obs)
        assert "[[rust/SMOC|rust]]" in created_content

    def test_idempotent(self):
        obs = MagicMock()
        obs.read.return_value = SAMPLE_GSMOC

        # python is already in the GSMOC
        update_gsmoc("- [[python/SMOC|python]]", obs)

        obs.rename.assert_not_called()
        obs.create.assert_not_called()


# -- rebuild_smoc tests ------------------------------------------------------


class TestRebuildSmoc:
    def _make_obs(self, smoc_content, poi_search="", ref_search=""):
        obs = MagicMock()

        def read_side_effect(path):
            if "SMOC" in path:
                return smoc_content
            raise ObsidianCLIError(["read"], 1, "not found")

        obs.read.side_effect = read_side_effect

        def search_side_effect(query, limit=20):
            if "type: poi" in query:
                return poi_search
            if "type: reference" in query:
                return ref_search
            return ""

        obs.search.side_effect = search_side_effect
        return obs

    def test_adds_new_poi(self):
        obs = self._make_obs(
            SAMPLE_SMOC,
            poi_search="python/POI-01-decorators\npython/POI-02-generators\npython/POI-04-asyncio\n",
        )
        # After rebuild, the read returns updated content
        updated = SAMPLE_SMOC.replace(
            "- [[POI-02-generators]]",
            "- [[POI-02-generators]]\n- [[POI-04-asyncio]]",
        )

        call_count = 0
        original_read = obs.read.side_effect

        def read_with_update(path):
            nonlocal call_count
            call_count += 1
            if "SMOC" in path and call_count > 2:
                return updated
            return original_read(path)

        obs.read.side_effect = read_with_update

        rebuild_smoc("python", obs)

        # Should have written the SMOC (rename + create)
        obs.create.assert_called()
        created_content = _get_created_content(obs)
        assert "[[POI-04-asyncio]]" in created_content

    def test_flags_missing_files(self):
        # SMOC references POI-01-decorators but search doesn't find it
        obs = self._make_obs(
            SAMPLE_SMOC,
            poi_search="python/POI-02-generators\n",
            ref_search="python/REF-01-pep484\n",
        )

        call_count = 0
        original_read = obs.read.side_effect

        def read_with_update(path):
            nonlocal call_count
            call_count += 1
            if "SMOC" in path and call_count > 2:
                # Return content with missing marker
                return SAMPLE_SMOC.replace(
                    "- [[POI-01-decorators]]",
                    "- [[POI-01-decorators]] [missing]",
                ).replace(
                    "- [[POI-03-type-hints]]",
                    "- [[POI-03-type-hints]] [missing]",
                )
            return original_read(path)

        obs.read.side_effect = read_with_update

        rebuild_smoc("python", obs)

        created_content = _get_created_content(obs)
        assert "[missing]" in created_content

    def test_preserves_manual_annotations(self):
        obs = self._make_obs(
            SAMPLE_SMOC_WITH_ANNOTATIONS,
            poi_search="python/POI-01-decorators\npython/POI-02-generators\n",
        )

        call_count = 0
        original_read = obs.read.side_effect

        def read_with_update(path):
            nonlocal call_count
            call_count += 1
            if "SMOC" in path and call_count > 2:
                return SAMPLE_SMOC_WITH_ANNOTATIONS
            return original_read(path)

        obs.read.side_effect = read_with_update

        rebuild_smoc("python", obs)

        created_content = _get_created_content(obs)
        # Annotations should be preserved
        assert "foundational pattern" in created_content
        assert "lazy evaluation" in created_content

    def test_handles_search_errors(self):
        """Rebuild should handle search errors gracefully."""
        obs = MagicMock()
        obs.read.return_value = EMPTY_SMOC
        obs.search.side_effect = ObsidianCLIError(["search"], 1, "error")

        # After rebuild, returns the same SMOC (no changes)
        result = rebuild_smoc("new-topic", obs)

        # Should still succeed, just no additions
        assert result is not None
