import os

import pytest

from tests.prompt_eval.providers import TestableIssueTransform, gemini_call

PROVIDERS = {
    "gemini": gemini_call,
}


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
