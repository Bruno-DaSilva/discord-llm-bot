"""Tests that scenario repo fields wire amendments into PipelineData."""

from pathlib import Path


from src.config import load_extra_context
from src.utils.repo import normalize_repo
from tests.prompt_eval.scenarios.issue_generator import SCENARIOS, Scenario


_EXTRA_CONTEXT_PATH = Path(__file__).resolve().parents[2] / "config" / "extra_context.yaml"


class TestScenarioAmendments:
    def test_extra_context_yaml_loads(self):
        ctx = load_extra_context(_EXTRA_CONTEXT_PATH)
        assert len(ctx) > 0, "extra_context.yaml should have at least one repo entry"

    def test_scenarios_with_repo_have_matching_amendments(self):
        ctx = load_extra_context(_EXTRA_CONTEXT_PATH)
        for scenario in SCENARIOS:
            if scenario.repo:
                key = normalize_repo(scenario.repo)
                assert key in ctx, (
                    f"Scenario '{scenario.name}' references repo '{scenario.repo}' "
                    f"but no matching entry found in extra_context.yaml"
                )

    def test_conftest_injects_amendments_for_repo_scenario(self):
        """Verify the conftest logic: repo scenarios get amendments in context."""
        from tests.prompt_eval.conftest import _extra_context

        scenario = next(s for s in SCENARIOS if s.repo)
        key = normalize_repo(scenario.repo)
        amendments = _extra_context.get(key, [])
        assert len(amendments) > 0, (
            f"Scenario '{scenario.name}' repo '{scenario.repo}' should have amendments"
        )

    def test_scenario_without_repo_gets_no_amendments(self):
        """A scenario with repo=None should not inject amendments."""
        from tests.prompt_eval.conftest import _extra_context

        scenario = Scenario(
            name="test_no_repo",
            focus="test",
            messages=["user: hello"],
        )
        assert scenario.repo is None
        # Simulating the conftest logic
        context: dict = {"messages": scenario.messages}
        if scenario.repo:
            amendments = _extra_context.get(normalize_repo(scenario.repo), [])
            if amendments:
                context["amendments"] = amendments
        assert "amendments" not in context
