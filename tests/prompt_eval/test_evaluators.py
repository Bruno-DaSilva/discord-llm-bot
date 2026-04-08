"""Unit tests for keyword evaluators — pure functions, no LLM needed."""

from tests.prompt_eval.evaluators import (
    check_required_any_keywords,
    check_required_keywords,
    check_unwanted_keywords,
    required_and,
    required_or,
    unwanted,
)


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


class TestUnwantedFactory:
    def test_default_name(self):
        check = unwanted("replay", "demo")
        assert check.name == "unwanted_keywords"

    def test_custom_name(self):
        check = unwanted("backwards.?compat", name="no_backwards_compat")
        assert check.name == "no_backwards_compat"

    def test_evaluate_returns_violations(self):
        check = unwanted("replay", "demo")
        assert check.evaluate("send the replay file") == ["replay"]

    def test_evaluate_returns_empty_on_pass(self):
        check = unwanted("replay", "demo")
        assert check.evaluate("fighters disappear at map edge") == []

    def test_evaluate_multiple_violations(self):
        check = unwanted("replay", "demo")
        assert check.evaluate("send the replay demo") == ["replay", "demo"]


class TestRequiredFactory:
    def test_default_name(self):
        check = required_and(r"###\s+Task")
        assert check.name == "required_keywords"

    def test_custom_name(self):
        check = required_and(r"###\s+Task", name="section_headers")
        assert check.name == "section_headers"

    def test_evaluate_returns_empty_when_present(self):
        check = required_and(r"###\s+Task", r"###\s+Context")
        assert check.evaluate("### Task\ndo it\n### Context\nstuff") == []

    def test_evaluate_returns_missing(self):
        check = required_and(r"###\s+Task", r"###\s+Context")
        assert check.evaluate("### Task\ndo it") == [r"###\s+Context"]


class TestCheckRequiredAnyKeywords:
    def test_returns_empty_when_any_found(self):
        assert check_required_any_keywords("Task section here", ["Task", "Missing"]) == []

    def test_returns_empty_when_all_found(self):
        assert check_required_any_keywords("Task and Context", ["Task", "Context"]) == []

    def test_returns_all_when_none_found(self):
        result = check_required_any_keywords("unrelated text", ["Task", "Context"])
        assert result == ["Task", "Context"]

    def test_empty_patterns(self):
        assert check_required_any_keywords("any text", []) == []

    def test_empty_text(self):
        result = check_required_any_keywords("", ["something"])
        assert result == ["something"]

    def test_case_insensitive(self):
        assert check_required_any_keywords("TASK section", ["task"]) == []

    def test_regex_pattern(self):
        assert check_required_any_keywords("backward compat", [r"backwards?\s*compat", "missing"]) == []


class TestRequiredAndFactory:
    def test_default_name(self):
        check = required_and("a", "b")
        assert check.name == "required_keywords"

    def test_passes_when_all_present(self):
        check = required_and("Task", "Context")
        assert check.evaluate("Task and Context") == []

    def test_fails_when_one_missing(self):
        check = required_and("Task", "Context")
        assert check.evaluate("Task only") == ["Context"]


class TestRequiredOrFactory:
    def test_default_name(self):
        check = required_or("a", "b")
        assert check.name == "required_any_keywords"

    def test_custom_name(self):
        check = required_or("a", name="my_check")
        assert check.name == "my_check"

    def test_passes_when_any_present(self):
        check = required_or("Task", "Context")
        assert check.evaluate("Task only") == []

    def test_passes_when_all_present(self):
        check = required_or("Task", "Context")
        assert check.evaluate("Task and Context") == []

    def test_fails_when_none_present(self):
        check = required_or("Task", "Context")
        assert check.evaluate("unrelated") == ["Task", "Context"]
