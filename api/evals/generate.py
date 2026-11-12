"""Deterministic synthetic dictation dataset.

    uv run python -m evals.generate                 # 120 text cases -> evals/data/cases.jsonl
    uv run python -m evals.generate --audio         # also synthesize audio (TTS) + background noise

Expected values come from the templates, never from an LLM, so the dataset is ground truth by
construction. The same --seed always produces byte-identical output.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, cast

from carenote.clinical.vitals import VITALS, VitalKind
from carenote.clinical.vocabulary import MEDICATIONS
from carenote.patients.synthetic import DEFAULT_SEED, SyntheticPatient, generate_patients
from evals.numbers import number_to_words

DATA_DIR = Path(__file__).parent / "data"
CASE_COUNT = 120
NOISE_SHARE = 0.3

Style = Literal["plain", "abbrev", "words"]
Difficulty = Literal["easy", "medium", "hard"]

# Primary tag -> number of cases. "mixed" combines abbreviations with a self-correction.
TAG_PLAN: tuple[tuple[str, int], ...] = (
    ("plain", 20),
    ("abbreviations", 20),
    ("numbers_as_words", 18),
    ("self_correction", 15),
    ("missing_values", 15),
    ("two_patients", 12),
    ("implausible_value", 12),
    ("mixed", 8),
)


# "Measurement" kinds as spoken: blood pressure is one measurement with two values.
Measure = Literal[
    "bp", "heart_rate", "respiratory_rate", "temperature", "spo2", "weight", "blood_glucose"
]
MEASURES: tuple[Measure, ...] = (
    "bp",
    "heart_rate",
    "respiratory_rate",
    "temperature",
    "spo2",
    "weight",
    "blood_glucose",
)
MEASURE_WEIGHTS = (5, 4, 3, 3, 3, 1, 1)

# (normal range, abnormal ranges); decimals = digits after the point.
RANGES: dict[str, tuple[tuple[float, float], tuple[tuple[float, float], ...], int]] = {
    "systolic_bp": ((105, 135), ((150, 185), (82, 88)), 0),
    "diastolic_bp": ((62, 85), ((92, 112),), 0),
    "heart_rate": ((58, 95), ((105, 135), (40, 46)), 0),
    "respiratory_rate": ((12, 20), ((23, 30),), 0),
    "temperature": ((36.2, 37.4), ((38.1, 39.6), (34.5, 35.2)), 1),
    "spo2": ((95, 99), ((86, 92),), 0),
    "weight": ((48, 110), ((48, 110),), 1),
    "blood_glucose": ((80, 140), ((210, 320), (52, 62)), 0),
}
IMPLAUSIBLE: dict[Measure, tuple[float, ...]] = {
    "heart_rate": (380, 310, 12),
    "spo2": (104, 112),
    "temperature": (47.5, 3.8),
    "respiratory_rate": (95, 2),
    "bp": (420,),  # systolic
}

VOICES = ("Samantha", "Daniel", "Karen")


@dataclass
class ExpectedVital:
    kind: VitalKind
    value: float
    unit: str


@dataclass
class ExpectedMedication:
    name: str
    dose: str | None
    route: str | None


@dataclass
class Case:
    id: str
    text: str
    ward: str
    expected_patient_id: str | None
    expected_patient_candidates: list[str]
    expected_vitals: list[ExpectedVital]
    expected_symptoms: list[str]
    expected_medications: list[ExpectedMedication]
    expected_uncertain_kinds: list[VitalKind]
    difficulty: Difficulty
    tags: list[str]
    voice: str
    audio_file: str | None = None
    notes: list[str] = field(default_factory=list)


# --- Rendering helpers ---------------------------------------------------------------------


def fmt(value: float, decimals: int) -> str:
    return f"{value:.{decimals}f}" if decimals else str(int(value))


class Renderer:
    def __init__(self, rng: random.Random, style: Style) -> None:
        self.rng = rng
        self.style = style

    def num(self, value: float, decimals: int = 0) -> str:
        text = fmt(value, decimals)
        if self.style == "words":
            return number_to_words(text, colloquial=self.rng.random() < 0.4)
        return text

    def pick(self, *options: str) -> str:
        return self.rng.choice(options)

    def measure(self, measure: Measure, values: dict[str, float]) -> str:
        """Render one measurement, e.g. 'BP 150/90' or 'pulse eighty-eight'."""
        n = self.num
        s = self.style
        if measure == "bp":
            sys_, dia = n(values["systolic_bp"]), n(values["diastolic_bp"])
            if s == "abbrev":
                return f"BP {sys_}/{dia}"
            return f"{self.pick('blood pressure', 'BP is', 'blood pressure is')} {sys_} over {dia}"
        v = values[measure]
        decimals = RANGES[measure][2]
        if measure == "temperature" and v < 10:
            decimals = 1
        value = n(v, decimals)
        if measure == "heart_rate":
            if s == "abbrev":
                return self.pick(f"HR {value}", f"P {value}", f"pulse {value} bpm")
            return self.pick(f"pulse {value}", f"heart rate {value}", f"pulse is {value}")
        if measure == "respiratory_rate":
            if s == "abbrev":
                return f"RR {value}"
            return self.pick(
                f"respiratory rate {value}", f"breathing {value} per minute", f"resps {value}"
            )
        if measure == "temperature":
            if s == "abbrev":
                return self.pick(f"T {value}", f"temp {value}")
            return self.pick(
                f"temperature {value} degrees", f"temp {value}", f"temperature {value}"
            )
        if measure == "spo2":
            if s == "abbrev":
                return self.pick(f"SpO2 {value}%", f"sats {value}% RA", f"sats {value}% on RA")
            return self.pick(
                f"oxygen saturation {value} percent",
                f"sats {value} percent on room air",
                f"saturating at {value} percent",
            )
        if measure == "weight":
            if s == "abbrev":
                return f"wt {value} kg"
            return self.pick(f"weight {value} kilos", f"weighs {value} kilograms")
        if s == "abbrev":
            return self.pick(f"BG {value}", f"BM {value}", f"glucose {value} mg/dL")
        return self.pick(f"blood sugar {value}", f"blood glucose {value}", f"sugar is {value}")

    def correction(self, measure: Measure, wrong: dict[str, float], right: dict[str, float]) -> str:
        """Self-correction: say a wrong value, then correct it."""
        marker = self.pick("no, sorry,", "sorry, I mean", "no wait,", "correction,")
        n = self.num
        if measure == "bp":
            head = "BP" if self.style == "abbrev" else "blood pressure"
            return (
                f"{head} {n(wrong['systolic_bp'])}... {marker} "
                f"{n(right['systolic_bp'])} over {n(right['diastolic_bp'])}"
            )
        decimals = RANGES[measure][2]
        return f"{self.measure(measure, wrong)}, {marker} {n(right[measure], decimals)}"


MISSING_PHRASES: dict[Measure, tuple[str, ...]] = {
    "bp": ("BP not taken, patient asleep", "couldn't get a blood pressure, cuff broken"),
    "heart_rate": ("pulse not recorded",),
    "respiratory_rate": ("resp rate not counted",),
    "temperature": ("temperature not done, patient refused", "temp not taken"),
    "spo2": ("couldn't get a sats reading, cold hands", "no sats reading, probe faulty"),
    "weight": ("weight not done today",),
    "blood_glucose": ("blood sugar not checked yet",),
}

INTROS = ("", "", "Update on ", "Note for ", "Checked on ", "Round at 14:00, ", "Evening round, ")
CLOSINGS = (
    "",
    "",
    "Will recheck in an hour.",
    "Doctor informed.",
    "Resting comfortably.",
    "Family visited this afternoon.",
)
# How each canonical symptom may be spoken: (form, phrase). n = noun, a = adjective, v = verb.
SPOKEN_SYMPTOMS: dict[str, tuple[tuple[str, str], ...]] = {
    "headache": (("n", "a headache"), ("n", "head pain"), ("n", "headache")),
    "nausea": (("n", "nausea"), ("a", "nauseous")),
    "dizziness": (("n", "dizziness"), ("a", "dizzy")),
    "chest pain": (("n", "chest pain"), ("n", "chest discomfort")),
    "shortness of breath": (
        ("n", "shortness of breath"),
        ("a", "short of breath"),
        ("a", "breathless"),
    ),
    "abdominal pain": (("n", "abdominal pain"), ("n", "tummy pain"), ("n", "a stomach ache")),
    "fatigue": (("n", "fatigue"), ("a", "exhausted"), ("a", "very tired")),
    "cough": (("n", "a cough"), ("n", "a dry cough")),
    "vomiting": (("v", "vomited twice"), ("n", "vomiting")),
    "back pain": (("n", "back pain"), ("n", "lower back pain")),
    "confusion": (("a", "confused"), ("a", "disoriented"), ("n", "some confusion")),
    "insomnia": (("v", "couldn't sleep last night"), ("n", "trouble sleeping")),
}
SYMPTOM_FRAMES: dict[str, tuple[str, ...]] = {
    "n": ("Complains of {}.", "Reports {}.", "Also mentions {}.", "Has had {} since this morning."),
    "a": ("Feeling {}.", "{pronoun} is {}.", "Says {pronoun_lc} feels {}."),
    "v": ("{pronoun} {}.",),
}
NEGATED = ("Denies {}.", "No {}.")


# --- Case builder --------------------------------------------------------------------------


class CaseBuilder:
    def __init__(self, rng: random.Random, patients: list[SyntheticPatient]) -> None:
        self.rng = rng
        self.patients = patients

    def ward_mates(self, patient: SyntheticPatient) -> list[SyntheticPatient]:
        return [p for p in self.patients if p.ward == patient.ward and p.id != patient.id]

    def title(self, p: SyntheticPatient) -> str:
        return "Mr." if p.sex == "male" else self.rng.choice(("Mrs.", "Mrs.", "Ms."))

    def reference(self, p: SyntheticPatient, allow_ambiguous: bool) -> tuple[str, bool]:
        """How the nurse names the patient. Returns (text, is_ambiguous)."""
        same_family = [m for m in self.ward_mates(p) if m.family_name == p.family_name]
        options = ["title_full", "full", "title_family_room", "room_first"]
        if allow_ambiguous or not same_family:
            options.append("title_family")
        form = self.rng.choice(options)
        if form == "title_full":
            return f"{self.title(p)} {p.full_name}", False
        if form == "full":
            return p.full_name, False
        if form == "title_family_room":
            return f"{self.title(p)} {p.family_name} in {p.room}", False
        if form == "room_first":
            return f"the patient in {p.room}, {self.title(p)} {p.family_name}", False
        return f"{self.title(p)} {p.family_name}", bool(same_family)

    def values_for(self, measure: Measure, abnormal: bool) -> dict[str, float]:
        kinds = ("systolic_bp", "diastolic_bp") if measure == "bp" else (measure,)
        out: dict[str, float] = {}
        for kind in kinds:
            normal, abnormal_ranges, decimals = RANGES[kind]
            lo, hi = self.rng.choice(abnormal_ranges) if abnormal else normal
            out[kind] = round(self.rng.uniform(lo, hi), decimals)
        if measure == "bp":  # keep a physiological pulse pressure
            out["diastolic_bp"] = min(out["diastolic_bp"], out["systolic_bp"] - 25)
        return out

    def pick_measures(self, count: int) -> list[Measure]:
        chosen: list[Measure] = []
        while len(chosen) < count:
            m = self.rng.choices(MEASURES, weights=MEASURE_WEIGHTS)[0]
            if m not in chosen:
                chosen.append(m)
        return chosen

    def build(self, index: int, tag: str) -> Case:
        rng = self.rng
        tags = [tag] if tag != "mixed" else ["abbreviations", "self_correction"]
        style: Style = (
            "abbrev"
            if "abbreviations" in tags
            else "words"
            if "numbers_as_words" in tags
            else rng.choice(("plain", "plain", "abbrev"))
        )
        r = Renderer(rng, style)
        patient = rng.choice(self.patients)
        ref, ambiguous = self.reference(patient, allow_ambiguous=tag in ("plain", "abbreviations"))

        expected_vitals: list[ExpectedVital] = []
        uncertain: list[VitalKind] = []
        parts: list[str] = []
        measures = self.pick_measures(rng.randint(2, 4))
        abnormal_any = rng.random() < 0.45

        special_index = rng.randrange(len(measures))
        for i, measure in enumerate(measures):
            values = self.values_for(measure, abnormal=abnormal_any and rng.random() < 0.6)
            is_special = i == special_index
            if is_special and "self_correction" in tags:
                wrong = {
                    k: v + rng.choice((-6, -4, 4, 6)) * (0.1 if k == "temperature" else 1)
                    for k, v in values.items()
                }
                wrong = {k: round(v, RANGES[k][2]) for k, v in wrong.items()}
                parts.append(r.correction(measure, wrong, values))
            elif is_special and tag == "missing_values":
                parts.append(rng.choice(MISSING_PHRASES[measure]))
                continue
            elif is_special and tag == "implausible_value" and measure in IMPLAUSIBLE:
                bad = rng.choice(IMPLAUSIBLE[measure])
                key: VitalKind = "systolic_bp" if measure == "bp" else measure
                bad_values = dict(values) | {key: bad}
                parts.append(r.measure(measure, bad_values))
                uncertain.append(key)
                if measure == "bp":  # the diastolic part is still valid
                    expected_vitals.append(
                        ExpectedVital(
                            "diastolic_bp", values["diastolic_bp"], VITALS["diastolic_bp"].ucum
                        )
                    )
                continue
            else:
                parts.append(r.measure(measure, values))
            for kind, value in values.items():
                vital_kind = cast("VitalKind", kind)
                expected_vitals.append(ExpectedVital(vital_kind, value, VITALS[vital_kind].ucum))

        if tag == "implausible_value" and not uncertain:
            # The special measure had no implausible variant: add a reading for another measure.
            extra = rng.choice([m for m in IMPLAUSIBLE if m not in measures and m != "bp"])
            parts.append(r.measure(extra, {extra: rng.choice(IMPLAUSIBLE[extra])}))
            uncertain.append(extra)

        sentences = [f"{rng.choice(INTROS)}{ref}".strip()]
        sentences[0] = sentences[0][0].upper() + sentences[0][1:] + "."
        vitals_sentence = ", ".join(parts)
        sentences.append(vitals_sentence[0].upper() + vitals_sentence[1:] + ".")

        symptoms: list[str] = []
        pronoun = "He" if patient.sex == "male" else "She"
        for canonical in rng.sample(sorted(SPOKEN_SYMPTOMS), k=rng.choice((0, 1, 1, 2))):
            form, phrase = rng.choice(SPOKEN_SYMPTOMS[canonical])
            frame = rng.choice(SYMPTOM_FRAMES[form])
            sentence = frame.format(phrase, pronoun=pronoun, pronoun_lc=pronoun.lower())
            sentences.append(sentence[0].upper() + sentence[1:])
            symptoms.append(canonical)
        if rng.random() < 0.15 and tag in ("plain", "abbreviations", "numbers_as_words"):
            negated = rng.choice(
                [s for s in ("chest pain", "nausea", "shortness of breath") if s not in symptoms]
            )
            sentences.append(rng.choice(NEGATED).format(negated))
            tags.append("negation")

        medications: list[ExpectedMedication] = []
        if rng.random() < 0.55:
            name = rng.choice(sorted(MEDICATIONS))
            dose, route = rng.choice(MEDICATIONS[name])
            sentences.append(self.medication_sentence(r, name, dose, route))
            medications.append(ExpectedMedication(name, dose, route))

        expected_patient: str | None = None if ambiguous else str(patient.id)
        candidates = [str(patient.id)]
        if tag == "two_patients":
            other = rng.choice(self.ward_mates(patient))
            other_ref = rng.choice((f"{self.title(other)} {other.family_name}", other.full_name))
            sentences.append(
                rng.choice(
                    (
                        f"Also checked on {other_ref}, asleep, no concerns.",
                        f"{other_ref} next door is settled.",
                        f"Then saw {other_ref}, nothing new.",
                    )
                )
            )
            expected_patient = None
            candidates.append(str(other.id))
        elif ambiguous:
            candidates += [
                str(m.id) for m in self.ward_mates(patient) if m.family_name == patient.family_name
            ]
            tags.append("ambiguous_name")

        closing = rng.choice(CLOSINGS)
        if closing:
            sentences.append(closing)

        hard = {
            "self_correction",
            "implausible_value",
            "two_patients",
            "ambiguous_name",
            "negation",
        }
        medium = {"abbreviations", "numbers_as_words", "missing_values"}
        difficulty: Difficulty = (
            "hard" if hard & set(tags) else "medium" if medium & set(tags) else "easy"
        )
        return Case(
            id=f"case-{index:03d}",
            text=" ".join(sentences),
            ward=patient.ward,
            expected_patient_id=expected_patient,
            expected_patient_candidates=candidates,
            expected_vitals=expected_vitals,
            expected_symptoms=symptoms,
            expected_medications=medications,
            expected_uncertain_kinds=uncertain,
            difficulty=difficulty,
            tags=tags,
            voice=rng.choice(VOICES),
            audio_file=f"audio/case-{index:03d}.wav",
        )

    def medication_sentence(self, r: Renderer, name: str, dose: str, route: str) -> str:
        amount, unit = dose.split(" ", 1)
        spoken_unit = {"mg": "milligrams", "g": "gram", "units": "units", "puffs": "puffs"}[unit]
        if r.style == "abbrev":
            route_text = {"oral": "PO", "iv": "IV", "subcutaneous": "SC", "inhaled": "inhaled"}[
                route
            ]
            freq = r.pick("", "", " b.i.d.", " stat")
            return f"Given {name} {dose} {route_text}{freq}".rstrip(".") + "."
        route_text = {
            "oral": r.pick("orally", "by mouth"),
            "iv": r.pick("IV", "intravenously"),
            "subcutaneous": r.pick("subcutaneously", "subcut"),
            "inhaled": r.pick("via inhaler", "nebulised"),
        }[route]
        amount_text = r.num(float(amount)) if r.style == "words" else amount
        unit_text = spoken_unit if r.style == "words" else unit
        return r.pick(
            f"Gave {amount_text} {unit_text} {name} {route_text}.",
            f"{name.capitalize()} {amount_text} {unit_text} given {route_text}.",
        )


def generate_cases(seed: int = DEFAULT_SEED) -> list[Case]:
    rng = random.Random(seed)  # noqa: S311 - synthetic data
    builder = CaseBuilder(rng, generate_patients(seed))
    plan = [tag for tag, count in TAG_PLAN for _ in range(count)]
    assert len(plan) == CASE_COUNT  # noqa: S101 - invariant of the plan above
    rng.shuffle(plan)
    cases = [builder.build(i, tag) for i, tag in enumerate(plan, start=1)]
    for case in rng.sample(cases, k=round(CASE_COUNT * NOISE_SHARE)):
        case.tags.append("background_noise")
    return cases


# --- Output --------------------------------------------------------------------------------


def write_dataset(cases: list[Case], seed: int, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "cases.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for case in cases:
            f.write(json.dumps(asdict(case), ensure_ascii=False, sort_keys=True) + "\n")
    patients = [
        {**asdict(p), "id": str(p.id), "birth_date": p.birth_date.isoformat()}
        for p in generate_patients(seed)
    ]
    (out_dir / "patients.json").write_text(json.dumps(patients, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", type=Path, default=DATA_DIR)
    parser.add_argument("--audio", action="store_true", help="synthesize audio with a TTS provider")
    parser.add_argument("--tts", choices=("macos", "openai"), default="macos")
    args = parser.parse_args(argv)

    cases = generate_cases(args.seed)
    if args.audio:
        from evals.audio import synthesize_all

        synthesize_all(cases, args.out / "audio", provider=args.tts, seed=args.seed)
    path = write_dataset(cases, args.seed, args.out)
    print(f"Wrote {len(cases)} cases to {path}")


if __name__ == "__main__":
    main()
