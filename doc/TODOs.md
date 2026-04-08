# TODOs

## Prompt eval: LLM-as-judge evaluator

`tests/prompt_eval/evaluators.py` currently has keyword-based checks only. Add an LLM-based evaluator (e.g., `llm_judge(text, criteria) -> bool`) for nuanced checks that keyword matching can't capture — tone, relevance, hallucination detection. Keyword evaluators are sufficient for the initial use case.
