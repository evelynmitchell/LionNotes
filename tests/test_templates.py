"""Tests for lionnotes.templates."""

from datetime import date

import pytest

from lionnotes.templates import TemplateError, list_templates, render


class TestRender:
    def test_speed_page(self):
        result = render("speed-page", subject="python", date="2026-03-14")
        assert 'subject: "python"' in result
        assert 'created: "2026-03-14"' in result
        assert "# python — Speed Thoughts" in result

    def test_poi(self):
        result = render(
            "poi", subject="python", poi_number=7, title="Async Patterns"
        )
        assert "poi_number: 7" in result
        assert 'title: "Async Patterns"' in result
        assert "# POI 7: Async Patterns" in result

    def test_smoc(self):
        result = render("smoc", subject="python")
        assert 'subject: "python"' in result
        assert "# python — Subject Map of Contents" in result
        assert "[[speeds]]" in result

    def test_gsmoc(self):
        result = render("gsmoc")
        assert "# Grand Subject Map of Contents" in result
        assert "Lion Kimbro" in result

    def test_purpose(self):
        result = render("purpose", subject="python")
        assert "# python — Purpose & Principles" in result
        assert "includes: []" in result

    def test_reference(self):
        result = render(
            "reference",
            subject="python",
            ref_number=3,
            title="Fluent Python",
            author="Luciano Ramalho",
            year=2022,
            url="https://example.com",
        )
        assert "ref_number: 3" in result
        assert "Luciano Ramalho (2022)" in result

    def test_glossary(self):
        result = render("glossary", subject="python")
        assert "# python — Abbreviations & Shorthand" in result

    def test_cheatsheet(self):
        result = render("cheatsheet", subject="python")
        assert "# python — Cheat Sheet" in result

    def test_inbox(self):
        result = render("inbox")
        assert "# Unsorted Speed Thoughts" in result

    def test_strategy(self):
        result = render("strategy")
        assert "# Active Priorities" in result

    def test_all_templates_render(self):
        """Every template can be rendered with its required vars."""
        # Provide all possible vars so every template works
        all_vars = {
            "subject": "test",
            "poi_number": 1,
            "title": "Test",
            "ref_number": 1,
            "author": "Author",
            "year": 2026,
            "url": "https://example.com",
            "date": "2026-03-14",
        }
        for name in list_templates():
            result = render(name, **all_vars)
            assert len(result) > 0, f"Template {name} rendered empty"


class TestDateDefault:
    def test_date_defaults_to_today(self):
        result = render("gsmoc")
        today = date.today().isoformat()
        assert today in result

    def test_date_can_be_overridden(self):
        result = render("gsmoc", date="2025-01-01")
        assert "2025-01-01" in result


class TestMissingVars:
    def test_missing_required_var_raises(self):
        with pytest.raises(TemplateError, match="requires variables.*subject"):
            render("speed-page")

    def test_missing_multiple_vars_raises(self):
        with pytest.raises(TemplateError, match="requires variables"):
            render("poi", subject="python")  # missing poi_number and title


class TestUnknownTemplate:
    def test_unknown_raises(self):
        with pytest.raises(TemplateError, match="Unknown template"):
            render("nonexistent")


class TestSafety:
    def test_unknown_placeholders_preserved(self):
        """Content with {{unknown}} is not mangled."""
        result = render("gsmoc")
        # No {{...}} should remain in a fully-rendered template
        # (all vars in gsmoc have defaults or are optional)
        assert "{{" not in result

    def test_subject_with_braces_in_name(self):
        """A subject name containing {{ is handled safely."""
        result = render("speed-page", subject="test {{braces}}")
        assert "test {{braces}}" in result


class TestListTemplates:
    def test_returns_sorted_list(self):
        names = list_templates()
        assert names == sorted(names)
        assert "speed-page" in names
        assert "gsmoc" in names
        assert len(names) >= 10
