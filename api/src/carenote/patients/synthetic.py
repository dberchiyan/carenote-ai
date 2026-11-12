"""Deterministic synthetic patients (a small stand-in for Synthea with the same fields).

The same seed always yields the same patients and ids, so the eval dataset can reference them.
"""

import datetime as dt
import random
import uuid
from dataclasses import dataclass

WARDS = ("3A", "3B")
DEFAULT_SEED = 42
PATIENT_COUNT = 30
_NAMESPACE = uuid.UUID("6f1c6a2e-5d4b-4c8e-9a51-0c2f6e7d8b90")

# Some near-identical names share a ward on purpose: they make patient matching non-trivial.
_FIXED: tuple[tuple[str, str, str, str], ...] = (
    ("Anna", "Keller", "female", "3A"),
    ("Hanna", "Keller", "female", "3A"),
    ("Peter", "Braun", "male", "3B"),
    ("Petra", "Braun", "female", "3B"),
    ("John", "Smith", "male", "3A"),
    ("Jon", "Smyth", "male", "3B"),
)
_GIVEN_F = (
    "Maria",
    "Sophie",
    "Emma",
    "Olivia",
    "Grace",
    "Laura",
    "Clara",
    "Ruth",
    "Helen",
    "Irene",
    "Nora",
    "Alice",
    "Margaret",
    "Eva",
    "Lucy",
)
_GIVEN_M = (
    "Thomas",
    "Michael",
    "David",
    "George",
    "Henry",
    "Paul",
    "Frank",
    "Walter",
    "Arthur",
    "Oscar",
    "Samuel",
    "Victor",
    "Edward",
    "Lukas",
    "Daniel",
)
_FAMILY = (
    "Fischer",
    "Weber",
    "Wagner",
    "Becker",
    "Hoffmann",
    "Schulz",
    "Koch",
    "Richter",
    "Klein",
    "Wolf",
    "Neumann",
    "Schwarz",
    "Zimmermann",
    "Hartmann",
    "Lange",
    "Werner",
    "Krause",
    "Meier",
    "Lehmann",
    "Walker",
    "Turner",
    "Bennett",
    "Hughes",
    "Morgan",
    "Foster",
)


@dataclass(frozen=True)
class SyntheticPatient:
    id: uuid.UUID
    mrn: str
    given_name: str
    family_name: str
    birth_date: dt.date
    sex: str
    ward: str
    room: str

    @property
    def full_name(self) -> str:
        return f"{self.given_name} {self.family_name}"


def _room(ward: str, bed_index: int) -> str:
    """Two beds per room; ward 3A uses rooms 301+, ward 3B rooms 321+."""
    base = 300 + 20 * WARDS.index(ward)
    return f"{base + (bed_index + 1) // 2}{'ab'[(bed_index + 1) % 2]}"


def generate_patients(
    seed: int = DEFAULT_SEED, count: int = PATIENT_COUNT
) -> list[SyntheticPatient]:
    rng = random.Random(seed)  # noqa: S311 - synthetic data, not security
    people: list[tuple[str, str, str, str]] = list(_FIXED)
    used = {(g, f) for g, f, _, _ in people}
    while len(people) < count:
        sex = rng.choice(("female", "male"))
        given = rng.choice(_GIVEN_F if sex == "female" else _GIVEN_M)
        family = rng.choice(_FAMILY)
        if (given, family) in used:
            continue
        used.add((given, family))
        ward = WARDS[len(people) % 2]
        people.append((given, family, sex, ward))

    rooms: dict[str, int] = dict.fromkeys(WARDS, 0)
    patients = []
    for index, (given, family, sex, ward) in enumerate(people[:count], start=1):
        rooms[ward] += 1
        mrn = f"SYN-{seed:03d}-{index:04d}"
        birth = dt.date(1930, 1, 1) + dt.timedelta(days=rng.randrange(0, 365 * 70))
        patients.append(
            SyntheticPatient(
                id=uuid.uuid5(_NAMESPACE, mrn),
                mrn=mrn,
                given_name=given,
                family_name=family,
                birth_date=birth,
                sex=sex,
                ward=ward,
                room=_room(ward, rooms[ward]),
            )
        )
    return patients
