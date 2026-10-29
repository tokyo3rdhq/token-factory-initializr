"""Unit tests for the ollama pricing simplification and normalize_pricing for ollama."""

from __future__ import annotations

from data.process.normalize import normalize_pricing


# ---------------------------------------------------------------------------
# _extract_pricing (simplified) — direct test of the HTML parser fix
# ---------------------------------------------------------------------------

def test_parse_library_html_extracts_pricing_no_dollar_suffix():
    """After simplification, ollama pricing values should be bare numbers."""
    from data.providers.ollama import _extract_pricing

    html = """
    <div data-rate="base">$0.30</div><div>input</div>
    <div data-rate="base">$0.006</div><div>cached</div>
    <div data-rate="base">$1.20</div><div>output</div>
    """
    free_until, prices = _extract_pricing(html)
    assert free_until is None
    assert prices["input"] == "0.30"
    assert prices["cached"] == "0.006"
    assert prices["output"] == "1.20"


def test_parse_library_html_extracts_pricing_numeric_string():
    """Values that are already strings should pass through without error."""
    from data.providers.ollama import _extract_pricing

    html = """
    <div data-rate="base">$0.15</div><div>input</div>
    <div data-rate="base">$0.20</div><div>output</div>
    """
    free_until, prices = _extract_pricing(html)
    assert prices["input"] == "0.15"
    assert prices["output"] == "0.20"


# ---------------------------------------------------------------------------
# normalize_pricing — ollama branch mirrors HF behavior
# ---------------------------------------------------------------------------

def test_normalize_pricing_ollama_keeps_as_is():
    """Ollama pricing is kept as-is, no 1M multiplication."""
    pricing = {"input": "0.30", "cached": "0.006", "output": "1.20"}
    result = normalize_pricing(pricing, data_source="ollama")
    # float values are converted to rounded floats
    assert result["input"] == 0.3
    assert result["cached"] == 0.006
    assert result["output"] == 1.2


def test_normalize_pricing_ollama_multiple_expansions():
    """Ollama with more price variants also keeps as-is."""
    pricing = {"input": "0.30", "output": "1.20", "input2": "0.50"}
    result = normalize_pricing(pricing, data_source="ollama")
    assert result["input"] == 0.3
    assert result["output"] == 1.2
    assert result["input2"] == 0.5


def test_normalize_pricing_ollama_string_passthrough():
    """Non-numeric strings are preserved as-is."""
    pricing = {"input": "$0.30", "output": "$1.20"}
    result = normalize_pricing(pricing, data_source="ollama")
    assert result["input"] == "$0.30"
    assert result["output"] == "$1.20"


# ---------------------------------------------------------------------------
# Non-ollama providers still multiply by 1M
# ---------------------------------------------------------------------------

def test_normalize_pricing_via_payment_still_multiplies():
    """Other providers (e.g. nvidia, amd) still multiply by 1M."""
    pricing = {"input": "0.30"}
    result = normalize_pricing(pricing, data_source="nvidia")
    assert result["input"] == "300000"


def test_normalize_pricing_via_hf_keeps_as_is():
    """HF pricing keeps as-is, no 1M multiplication."""
    pricing = {"input": "0.30"}
    result = normalize_pricing(pricing, data_source="huggingface")
    assert result["input"] == 0.3