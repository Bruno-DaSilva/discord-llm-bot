import asyncio
import os
from pathlib import Path

import pytest

from src.config import load_extra_context
from src.models import PipelineData
from src.utils.repo import normalize_repo
from tests.prompt_eval.providers import TestableIssueTransform, gemini_call

_EXTRA_CONTEXT_PATH = Path(__file__).resolve().parents[2] / "config" / "extra_context.yaml"
_extra_context = load_extra_context(_EXTRA_CONTEXT_PATH)

PROVIDERS = {
    "gemini": gemini_call,
}

_output_cache: dict[str, list[str]] = {}
_results: dict[tuple[str, str], tuple[int, int]] = {}


def pytest_collection_modifyitems(config, items):
    """Skip prompt_eval-marked tests unless explicitly selected with -m prompt_eval."""
    markexpr = config.getoption("-m", default="")
    if "prompt_eval" in markexpr:
        return

    skip = pytest.mark.skip(reason="pass -m prompt_eval to run LLM evaluation tests")
    for item in items:
        if item.get_closest_marker("prompt_eval") is not None:
            item.add_marker(skip)


@pytest.fixture
def provider():
    provider_name = os.environ.get("LLM_PROVIDER", "gemini")
    call_fn = PROVIDERS.get(provider_name)
    if call_fn is None:
        pytest.skip(f"Unknown LLM_PROVIDER: {provider_name}")
    return TestableIssueTransform(call_fn=call_fn)


@pytest.fixture
async def scenario_outputs(provider, scenario):
    """Generate LLM outputs once per scenario, cache for all checks."""
    if scenario.name not in _output_cache:
        context: dict = {"messages": scenario.messages}
        if scenario.repo:
            amendments = _extra_context.get(normalize_repo(scenario.repo), [])
            if amendments:
                context["amendments"] = amendments
        data = PipelineData(
            input=scenario.focus,
            context=context,
        )
        results = await asyncio.gather(*(provider.run(data) for _ in range(scenario.runs)))
        _output_cache[scenario.name] = [r.input for r in results]
    return _output_cache[scenario.name]


@pytest.fixture
def prompt_eval_results():
    return _results


def pytest_terminal_summary(terminalreporter, config):
    if not _results:
        return

    terminalreporter.section("Prompt Eval Results")

    sc_w = max(len(sc) for sc, _ in _results)
    ch_w = max(len(ch) for _, ch in _results)

    header = (
        f"{'Scenario':<{sc_w}}  "
        f"{'Check':<{ch_w}}  "
        f"{'Pass':>5}  "
        f"{'Rate':>7}"
    )
    terminalreporter.line(header)
    terminalreporter.line("-" * len(header))

    for (scenario, check), (passed, total) in _results.items():
        rate = (passed / total * 100) if total else 0
        marker = " !" if passed < total else ""
        terminalreporter.line(
            f"{scenario:<{sc_w}}  "
            f"{check:<{ch_w}}  "
            f"{passed}/{total:>2}  "
            f"{rate:>6.1f}%{marker}"
        )
