"""LLM paraphrasing of dataset cases, for wording the templates do not cover.

    uv run python -m evals.paraphrase      # needs CARENOTE_ANTHROPIC_API_KEY

Labels never come from the LLM: a paraphrase is kept only if it preserves every number, patient
name and room from the template text; otherwise the template text is kept. Output goes to
evals/data/cases_paraphrased.jsonl (not deterministic — commit the file to freeze a version).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel

from carenote.config import get_settings
from carenote.patients.synthetic import generate_patients

DATA = Path(__file__).parent / "data"
PROMPT = (Path(__file__).parent / "prompts" / "paraphrase_v1.md").read_text(encoding="utf-8")
NUMBER = re.compile(r"\d+(?:\.\d+)?")


class Paraphrase(BaseModel):
    text: str


class Paraphraser(Protocol):
    def __call__(self, text: str) -> str: ...


def preserves_facts(original: str, paraphrase: str) -> bool:
    if sorted(NUMBER.findall(original)) != sorted(NUMBER.findall(paraphrase)):
        return False
    names = {n for p in generate_patients() for n in (p.given_name, p.family_name, p.room)}
    for name in names:
        pattern = rf"\b{re.escape(name)}\b"
        if len(re.findall(pattern, original)) != len(re.findall(pattern, paraphrase)):
            return False
    words = re.compile(r"\b(?:no|not|denies|sorry|correction|wait)\b", re.IGNORECASE)
    return len(words.findall(original)) == len(words.findall(paraphrase))


def claude_paraphraser() -> Paraphraser:
    import anthropic

    settings = get_settings()
    if settings.anthropic_api_key is None:
        raise SystemExit("CARENOTE_ANTHROPIC_API_KEY is required for paraphrasing")
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key.get_secret_value())

    def paraphrase(text: str) -> str:
        response = client.messages.parse(
            model=settings.anthropic_model,
            max_tokens=2000,
            system=PROMPT,
            messages=[{"role": "user", "content": text}],
            output_format=Paraphrase,
            output_config={"effort": "low"},
        )
        return response.parsed_output.text if response.parsed_output else text

    return paraphrase


def paraphrase_cases(cases: list[dict[str, Any]], paraphrase: Paraphraser) -> list[dict[str, Any]]:
    out = []
    for case in cases:
        candidate = paraphrase(case["text"]).strip()
        kept = bool(candidate) and preserves_facts(case["text"], candidate)
        out.append(
            {
                **case,
                "template_text": case["text"],
                "text": candidate if kept else case["text"],
                "tags": [*case["tags"], "paraphrased" if kept else "paraphrase_rejected"],
            }
        )
    return out


def main() -> None:
    cases = [json.loads(line) for line in (DATA / "cases.jsonl").read_text().splitlines()]
    rows = paraphrase_cases(cases, claude_paraphraser())
    path = DATA / "cases_paraphrased.jsonl"
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    kept = sum("paraphrased" in r["tags"] for r in rows)
    print(f"Wrote {path} ({kept}/{len(rows)} paraphrases kept)")


if __name__ == "__main__":
    main()
