"""Unit tests for lionnotes.index module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lionnotes.index import (
    IndexBuildError,
    _extract_keywords,
    _format_index,
    _strip_frontmatter,
    build_index,
)
from lionnotes.obsidian import ObsidianCLIError

SAMPLE_POI_CONTENT = """\
---
type: poi
subject: "python"
poi_number: 1
title: "Decorators"
created: "2026-01-01"
synthesized_from: []
status: draft
---
# POI 1: Decorators

## Context
Explored after reading [[REF-01-pep-318]].

## Content
Decorators are #python/advanced feature using #metaprogramming.
See also [[POI-02-closures]].

## Connections
- [[REF-01-pep-318]]

## Open Questions
<!-- None yet -->
"""

SAMPLE_SPEEDS_CONTENT = """\
---
type: speeds
subject: "python"
created: "2026-01-01"
last_entry: null
entry_count: 2
---
# python — Speed Thoughts

- S1: (context: learning) decorators are cool #thought/observation
- S2: (context: learning) need to check [[POI-01-decorators]] #thought/question
"""

SAMPLE_SMOC_CONTENT = """\
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
- [[POI-01-decorators]]
- [[POI-02-closures]]

### Peripheral

### References
- [[REF-01-pep-318]]

## Speed Thoughts
- Current speed page: [[speeds]]

## See Also
"""


class TestStripFrontmatter:
    def test_strips_frontmatter(self):
        content = "---\nfoo: bar\n---\nBody text"
        assert _strip_frontmatter(content) == "Body text"

    def test_no_frontmatter(self):
        content = "Just body text"
        assert _strip_frontmatter(content) == "Just body text"

    def test_unclosed_frontmatter(self):
        content = "---\nfoo: bar\nBody text"
        assert _strip_frontmatter(content) == content

    def test_dash_in_yaml_value(self):
        content = '---\ntitle: "a---b"\n---\nBody'
        assert _strip_frontmatter(content) == "Body"

    def test_empty_frontmatter(self):
        content = "---\n---\nBody"
        assert _strip_frontmatter(content) == "Body"


class TestExtractKeywords:
    def test_extracts_wikilinks(self):
        content = "See [[foo]] and [[bar]]."
        kw = _extract_keywords(content)
        assert "foo" in kw
        assert "bar" in kw

    def test_extracts_tags(self):
        content = "This is #python and #metaprogramming."
        kw = _extract_keywords(content)
        assert "#python" in kw
        assert "#metaprogramming" in kw

    def test_extracts_nested_tags(self):
        content = "Using #thought/observation here."
        kw = _extract_keywords(content)
        assert "#thought/observation" in kw

    def test_lowercases_keywords(self):
        content = "See [[MyNote]] and #Python."
        kw = _extract_keywords(content)
        assert "mynote" in kw
        assert "#python" in kw

    def test_skips_frontmatter(self):
        content = '---\nsubject: "python"\n---\nBody with [[real-link]]'
        kw = _extract_keywords(content)
        assert "real-link" in kw
        # frontmatter values should not be extracted
        assert "python" not in kw

    def test_skips_html_comments(self):
        content = "<!-- [[hidden]] #hidden -->\n[[visible]]"
        kw = _extract_keywords(content)
        assert "visible" in kw
        assert "hidden" not in kw
        assert "#hidden" not in kw

    def test_wikilink_with_alias(self):
        content = "See [[note|display text]]."
        kw = _extract_keywords(content)
        assert "note" in kw

    def test_empty_content(self):
        assert _extract_keywords("") == set()

    def test_no_keywords(self):
        content = "Just plain text with no links or tags."
        assert _extract_keywords(content) == set()

    def test_from_poi_content(self):
        kw = _extract_keywords(SAMPLE_POI_CONTENT)
        assert "ref-01-pep-318" in kw
        assert "poi-02-closures" in kw
        assert "#python/advanced" in kw
        assert "#metaprogramming" in kw


class TestFormatIndex:
    def test_basic_format(self):
        keyword_map = {
            "decorators": ["POI-01-decorators"],
            "#python": ["POI-01-decorators", "speeds"],
        }
        result = _format_index(keyword_map, "python")

        assert "# python — Index" in result
        assert "## Keywords" in result
        assert "- **#python**: [[POI-01-decorators]], [[speeds]]" in result
        assert "- **decorators**: [[POI-01-decorators]]" in result

    def test_sorted_keywords(self):
        keyword_map = {
            "zebra": ["POI-01"],
            "alpha": ["POI-02"],
        }
        result = _format_index(keyword_map, "test")
        lines = result.strip().splitlines()
        keyword_lines = [ln for ln in lines if ln.startswith("- **")]
        assert keyword_lines[0].startswith("- **alpha**")
        assert keyword_lines[1].startswith("- **zebra**")

    def test_sorted_note_links(self):
        keyword_map = {
            "topic": ["POI-03", "POI-01", "REF-01"],
        }
        result = _format_index(keyword_map, "test")
        assert "[[POI-01]], [[POI-03]], [[REF-01]]" in result

    def test_empty_keyword_map(self):
        result = _format_index({}, "empty-subject")
        assert "# empty-subject — Index" in result
        assert "## Keywords" in result

    def test_contains_frontmatter(self):
        result = _format_index({"a": ["POI-01"]}, "python")
        assert "type: index" in result
        assert 'subject: "python"' in result


class TestBuildIndex:
    def test_builds_index_new(self):
        obs = MagicMock()
        obs.read.side_effect = self._make_read_side_effect(index_exists=False)

        content = build_index("python", obs)

        assert "# python — Index" in content
        assert "## Keywords" in content
        # Should have created the note
        obs.create.assert_any_call("python/Index", content=content)

    def test_builds_index_existing(self):
        obs = MagicMock()
        obs.read.side_effect = self._make_read_side_effect(index_exists=True)

        with patch("lionnotes.index._write_note") as mock_write:
            build_index("python", obs)

        mock_write.assert_called_once()
        assert mock_write.call_args[0][0] == "python/Index"

    def test_extracts_keywords_from_notes(self):
        obs = MagicMock()
        obs.read.side_effect = self._make_read_side_effect(index_exists=False)

        content = build_index("python", obs)

        # Keywords from POI-01-decorators
        assert "ref-01-pep-318" in content
        assert "#metaprogramming" in content

    def test_smoc_read_failure_raises(self):
        obs = MagicMock()
        obs.read.side_effect = ObsidianCLIError(["read"], 1, "not found")

        with pytest.raises(IndexBuildError, match="Cannot read SMOC"):
            build_index("nonexistent", obs)

    def test_skips_unreadable_notes(self):
        obs = MagicMock()

        def read_side_effect(path):
            if path == "python/SMOC":
                return SAMPLE_SMOC_CONTENT
            if path == "python/Index":
                raise ObsidianCLIError(["read"], 1, "not found")
            # All other notes fail
            raise ObsidianCLIError(["read"], 1, "not found")

        obs.read.side_effect = read_side_effect

        content = build_index("python", obs)

        # Should still produce an index, just with no keywords
        assert "# python — Index" in content

    def test_reraises_non_not_found_errors(self):
        obs = MagicMock()

        def read_side_effect(path):
            if path == "python/SMOC":
                return SAMPLE_SMOC_CONTENT
            if path == "python/Index":
                raise ObsidianCLIError(["read"], 1, "not found")
            # Simulate a permission error (not a not-found)
            raise ObsidianCLIError(["read"], 1, "permission denied")

        obs.read.side_effect = read_side_effect

        with pytest.raises(ObsidianCLIError, match="permission denied"):
            build_index("python", obs)

    def test_includes_speeds_page(self):
        obs = MagicMock()
        obs.read.side_effect = self._make_read_side_effect(index_exists=False)

        content = build_index("python", obs)

        # speeds page has [[POI-01-decorators]] link
        assert "poi-01-decorators" in content

    @staticmethod
    def _make_read_side_effect(index_exists: bool = False):
        """Create a read side_effect that returns appropriate content."""

        def read_side_effect(path):
            if path == "python/SMOC":
                return SAMPLE_SMOC_CONTENT
            if path == "python/POI-01-decorators":
                return SAMPLE_POI_CONTENT
            if path == "python/POI-02-closures":
                return "## Closures\nRelated to [[POI-01-decorators]]."
            if path == "python/REF-01-pep-318":
                return "## PEP 318\n#python/pep reference."
            if path == "python/speeds":
                return SAMPLE_SPEEDS_CONTENT
            if path == "python/purpose":
                return "## Purpose\nLearn Python."
            if path == "python/Index":
                if index_exists:
                    return "existing index content"
                raise ObsidianCLIError(["read"], 1, "not found")
            raise ObsidianCLIError(["read"], 1, "not found")

        return read_side_effect
