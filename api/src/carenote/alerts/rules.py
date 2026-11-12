"""Load and apply threshold rules from rules.yaml."""

from functools import cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from carenote.clinical.vitals import VitalKind

Flag = Literal["normal", "warning", "critical"]
FLAGS: tuple[str, ...] = ("normal", "warning", "critical")
RULES_PATH = Path(__file__).with_name("rules.yaml")


class Thresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    critical_below: float | None = None
    warning_below: float | None = None
    warning_above: float | None = None
    critical_above: float | None = None


class RuleSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    rules: dict[VitalKind, Thresholds]

    def flag(self, kind: VitalKind, value: float) -> Flag:
        t = self.rules.get(kind)
        if t is None:
            return "normal"
        if (t.critical_below is not None and value < t.critical_below) or (
            t.critical_above is not None and value > t.critical_above
        ):
            return "critical"
        if (t.warning_below is not None and value < t.warning_below) or (
            t.warning_above is not None and value > t.warning_above
        ):
            return "warning"
        return "normal"

    def interpretation(self, kind: VitalKind, value: float, flag: Flag | None = None) -> str | None:
        """HL7 v3 ObservationInterpretation code: N, H, L, HH or LL (None if no rule).

        `flag` is the flag stored with the observation when it was confirmed; it stays
        authoritative after the rules change. Only the direction (H/L) is read from the rules."""
        t = self.rules.get(kind)
        if t is None:
            return None
        flag = flag or self.flag(kind, value)
        if flag == "normal":
            return "N"
        high = (t.warning_above is not None and value > t.warning_above) or (
            t.critical_above is not None and value > t.critical_above
        )
        return ("H" if high else "L") * (2 if flag == "critical" else 1)


def load_rules(path: Path = RULES_PATH) -> RuleSet:
    return RuleSet.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


@cache
def default_rules() -> RuleSet:
    return load_rules()
