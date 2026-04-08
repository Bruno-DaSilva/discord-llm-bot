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
    async def test_check(self, scenario_outputs, scenario, check, prompt_eval_results):
        failures = []
        total = len(scenario_outputs)

        for i, output in enumerate(scenario_outputs):
            violations = check.evaluate(output)
            if violations:
                failures.append((i + 1, violations, output))

        passed = total - len(failures)
        prompt_eval_results[(scenario.name, check.name)] = (passed, total)

        if failures:
            desc = f" ({check.description})" if check.description else ""
            detail = "\n\n".join(
                f"--- Run {run}/{total} violations: {v} ---\n{out}"
                for run, v, out in failures
            )
            pytest.fail(
                f"'{scenario.name}' check '{check.name}'{desc}: "
                f"{passed}/{total} passed ({passed / total * 100:.0f}%)\n\n{detail}"
            )
