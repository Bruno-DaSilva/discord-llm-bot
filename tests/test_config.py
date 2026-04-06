from pathlib import Path

import pytest

from src.config import load_extra_context


@pytest.fixture
def tmp_yaml(tmp_path):
    """Helper that writes content to a temp YAML file and returns its path."""

    def _write(content: str) -> Path:
        p = tmp_path / "extra_context.yaml"
        p.write_text(content)
        return p

    return _write


class TestLoadPromptAmendments:
    def test_loads_valid_yaml(self, tmp_yaml):
        path = tmp_yaml(
            "owner/repo:\n"
            '  - "Focus on engine internals"\n'
            '  - "Use technical language"\n'
        )
        result = load_extra_context(path)
        assert result == {
            "owner/repo": ["Focus on engine internals", "Use technical language"]
        }

    def test_multiple_repos(self, tmp_yaml):
        path = tmp_yaml(
            "owner/repo-a:\n"
            '  - "amendment a"\n'
            "owner/repo-b:\n"
            '  - "amendment b"\n'
        )
        result = load_extra_context(path)
        assert len(result) == 2
        assert result["owner/repo-a"] == ["amendment a"]
        assert result["owner/repo-b"] == ["amendment b"]

    def test_returns_empty_dict_when_file_missing(self, tmp_path):
        result = load_extra_context(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_empty_file_returns_empty_dict(self, tmp_yaml):
        path = tmp_yaml("")
        result = load_extra_context(path)
        assert result == {}

    def test_raises_on_non_dict_root(self, tmp_yaml):
        path = tmp_yaml("- item1\n- item2\n")
        with pytest.raises(ValueError, match="root"):
            load_extra_context(path)

    def test_raises_on_non_list_value(self, tmp_yaml):
        path = tmp_yaml("owner/repo: not-a-list\n")
        with pytest.raises(ValueError, match="list"):
            load_extra_context(path)

    def test_raises_on_non_string_list_item(self, tmp_yaml):
        path = tmp_yaml("owner/repo:\n  - 123\n")
        with pytest.raises(ValueError, match="string"):
            load_extra_context(path)
