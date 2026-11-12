"""Per-model prices in USD per 1M tokens (input, output). Update when vendors change prices.

Cost is always computed from the model that *answered* (`response.model`), since a server-side
fallback may route a request to a cheaper model. An unknown model costs $0 and logs a warning,
so a silent zero on the metrics page never goes unnoticed.
"""

import logging

log = logging.getLogger(__name__)
_warned: set[str] = set()

PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    # Anthropic (first-party API rates)
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
    # OpenAI — verify against the vendor price list before publishing numbers.
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5": (1.25, 10.00),
}

# Transcription, USD per audio minute.
TRANSCRIPTION_PRICE_PER_MIN: dict[str, float] = {
    "gpt-4o-transcribe": 0.006,
    "gpt-4o-mini-transcribe": 0.003,
}


def llm_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = PRICES_PER_MTOK.get(model)
    if prices is None:
        if model not in _warned:
            _warned.add(model)
            log.warning("no price for model %r: its cost is reported as $0", model)
        return 0.0
    price_in, price_out = prices
    return round((input_tokens * price_in + output_tokens * price_out) / 1_000_000, 6)
