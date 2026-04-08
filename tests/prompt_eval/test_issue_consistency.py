"""LLM output consistency tests for issue generation.

Run with: GEMINI_API_KEY=... uv run pytest -m prompt_eval -v
"""

import pytest

from tests.prompt_eval.scenarios.issue_generator import SCENARIOS

_SCENARIO_CHECKS = [(s, c) for s in SCENARIOS for c in s.checks]


@pytest.mark.prompt_eval
@pytest.mark.parametrize(
    "scenario,check",
    _SCENARIO_CHECKS,
    ids=[f"{s.name}--{c.name}" for s, c in _SCENARIO_CHECKS],
)
class TestIssueConsistency:
    @pytest.mark.asyncio
    async def test_check(self, scenario_outputs, scenario, check):
        for i, output in enumerate(scenario_outputs):
            violations = check.evaluate(output)
            desc = f" ({check.description})" if check.description else ""
            assert not violations, (
                f"Run {i + 1}/{len(scenario_outputs)} for '{scenario.name}' "
                f"failed check '{check.name}'{desc}: {violations}\n\nOutput:\n{output}"
            )
