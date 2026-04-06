"""LLM output consistency tests for issue generation.

Run with: GEMINI_API_KEY=... uv run pytest -m prompt_eval -v
"""

import pytest

from src.models import PipelineData
from tests.prompt_eval.evaluators import check_required_keywords, check_unwanted_keywords
from tests.prompt_eval.scenarios.issue_generator import SCENARIOS


@pytest.mark.prompt_eval
@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
class TestIssueConsistency:
    @pytest.mark.asyncio
    async def test_output_consistency(self, provider, scenario):
        data = PipelineData(
            input=scenario.focus,
            context={"messages": scenario.messages},
        )

        outputs = []
        for _ in range(scenario.runs):
            result = await provider.run(data)
            outputs.append(result.input)

        for i, output in enumerate(outputs):
            violations = check_unwanted_keywords(output, scenario.unwanted_keywords)
            assert not violations, (
                f"Run {i + 1}/{scenario.runs} for '{scenario.name}' "
                f"contained unwanted keywords: {violations}\n\nOutput:\n{output}"
            )

            missing = check_required_keywords(output, scenario.required_keywords)
            assert not missing, (
                f"Run {i + 1}/{scenario.runs} for '{scenario.name}' "
                f"missing required keywords: {missing}\n\nOutput:\n{output}"
            )
