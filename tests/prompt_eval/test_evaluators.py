"""Unit tests for keyword evaluators — pure functions, no LLM needed."""

from tests.prompt_eval.evaluators import check_required_keywords, check_unwanted_keywords


class TestCheckUnwantedKeywords:
    def test_returns_empty_when_no_keywords_found(self):
        assert check_unwanted_keywords("some output text", ["missing"]) == []

    def test_returns_found_keywords(self):
        result = check_unwanted_keywords(
            "We need backwards compatibility here", ["backwards compatibility"]
        )
        assert result == ["backwards compatibility"]

    def test_case_insensitive(self):
        result = check_unwanted_keywords("BACKWARDS COMPATIBILITY", ["backwards compatibility"])
        assert result == ["backwards compatibility"]

    def test_empty_keyword_list(self):
        assert check_unwanted_keywords("any text", []) == []

    def test_multiple_keywords_partial_match(self):
        text = "This mentions backwards compatibility but not the other thing"
        result = check_unwanted_keywords(text, ["backwards compatibility", "forward migration"])
        assert result == ["backwards compatibility"]

    def test_empty_text(self):
        assert check_unwanted_keywords("", ["something"]) == []

    def test_regex_pattern(self):
        text = "We need backward compatibility for this"
        result = check_unwanted_keywords(text, [r"backwards?\s+compat"])
        assert result == [r"backwards?\s+compat"]

    def test_regex_no_match(self):
        text = "This is a simple feature"
        assert check_unwanted_keywords(text, [r"backwards?\s+compat"]) == []

    def test_regex_alternation(self):
        text = "This is a breaking change"
        result = check_unwanted_keywords(text, [r"breaking\s+(change|update)"])
        assert result == [r"breaking\s+(change|update)"]

    def test_plain_string_still_works(self):
        result = check_unwanted_keywords("hello world", ["hello"])
        assert result == ["hello"]


class TestCheckRequiredKeywords:
    def test_returns_empty_when_all_found(self):
        assert check_required_keywords("Task and Context sections", ["Task", "Context"]) == []

    def test_returns_missing_keywords(self):
        result = check_required_keywords("Only has Task section", ["Task", "Context"])
        assert result == ["Context"]

    def test_case_insensitive(self):
        assert check_required_keywords("TASK section", ["task"]) == []

    def test_empty_keyword_list(self):
        assert check_required_keywords("any text", []) == []

    def test_empty_text(self):
        result = check_required_keywords("", ["something"])
        assert result == ["something"]

    def test_all_missing(self):
        result = check_required_keywords("unrelated text", ["Task", "Context"])
        assert result == ["Task", "Context"]

    def test_regex_pattern(self):
        text = "### Task\nDo the thing\n### Acceptance Criteria\n- done"
        assert check_required_keywords(text, [r"###\s+Task", r"###\s+Acceptance Criteria"]) == []

    def test_regex_missing(self):
        text = "### Task\nDo the thing"
        result = check_required_keywords(text, [r"###\s+Task", r"###\s+Acceptance Criteria"])
        assert result == [r"###\s+Acceptance Criteria"]

    def test_plain_string_still_works(self):
        assert check_required_keywords("hello world", ["hello"]) == []
