"""Versioned prompts. The version string is stored with every extraction."""

from functools import cache
from pathlib import Path

from carenote.contracts.llm import Prompt

EXTRACT_PROMPT_VERSION = "extract_v1"
_DIR = Path(__file__).parent


@cache
def load_prompt(version: str = EXTRACT_PROMPT_VERSION) -> Prompt:
    return Prompt(version=version, system=(_DIR / f"{version}.md").read_text(encoding="utf-8"))
