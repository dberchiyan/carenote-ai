"""Claude writes the handover text from de-identified facts (rooms, never names)."""

import logging

import anthropic

from carenote.contracts.handover import HandoverFacts, HandoverText
from carenote.contracts.llm import Prompt
from carenote.handover.writer import RuleBasedHandoverWriter
from carenote.providers.pricing import llm_cost

log = logging.getLogger(__name__)


class AnthropicHandoverWriter:
    """Falls back to the rule-based text if the API fails or answers out of shape: a handover
    must always be available."""

    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        prompt: Prompt,
        model: str = "claude-sonnet-5-5",
        client: anthropic.Anthropic | None = None,
        timeout_s: float = 45,
    ) -> None:
        self.model = model
        self.prompt = prompt
        self.client = client or anthropic.Anthropic(
            api_key=api_key, max_retries=1, timeout=timeout_s
        )
        self.fallback = RuleBasedHandoverWriter()

    def write(self, facts: HandoverFacts) -> tuple[HandoverText, str]:
        try:
            response = self.client.beta.messages.parse(
                model=self.model,
                max_tokens=4000,
                system=self.prompt.system,
                messages=[
                    {"role": "user", "content": f"<facts>\n{facts.model_dump_json()}\n</facts>"}
                ],
                output_format=HandoverText,
            )
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            log.warning("handover writer fell back to rules: %s", type(exc).__name__)
            return self.fallback.write(facts)
        text = response.parsed_output
        rooms = [p.room for p in facts.patients]
        if text is None or sorted(r.room for r in text.patients) != sorted(rooms):
            log.warning("handover writer fell back to rules: rooms did not match")
            return self.fallback.write(facts)
        usage = response.usage
        log.info(
            "handover written by %s",
            response.model,
            extra={
                "step": "handover",
                "model": response.model,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "cost_usd": llm_cost(response.model, usage.input_tokens, usage.output_tokens),
            },
        )
        return text, response.model
