"""Cached context and new token consumption have distinct enforced caps."""
import importlib.util
from pathlib import Path
import pytest


@pytest.mark.parametrize("system", ["mam-luna-python-context-budget", "mam-luna-required-accord-context-budget"])
def test_context_budget_keeps_cached_input_separate_and_enforces_all_caps(system):
    path = Path(__file__).resolve().parents[1] / "systems" / system / "adapter.py"
    spec = importlib.util.spec_from_file_location("budget_adapter", path)
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    budget = {"max_total_tokens": 350000, "max_uncached_and_output_tokens": 100000, "max_output_tokens": 20000}
    usage = {"input_tokens": 260000, "cached_input_tokens": 250000, "output_tokens": 9000, "total_tokens": 269000}
    assert adapter.token_limit_reason(usage, budget) is None
    assert adapter.token_limit_reason({**usage, "cached_input_tokens": 160000}, budget) == "max_uncached_and_output_tokens"
    assert adapter.token_limit_reason({**usage, "output_tokens": 20000}, budget) == "max_output_tokens"
    assert adapter.token_limit_reason({**usage, "total_tokens": 350000}, budget) == "max_total_tokens"
