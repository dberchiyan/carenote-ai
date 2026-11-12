"""Extraction schema: the LLM's structured output and the stored draft payload.

Changing this schema requires updating tests, the prompt version and the README.
"""

from pydantic import BaseModel, Field

from carenote.clinical.vitals import VitalKind


class Vital(BaseModel):
    kind: VitalKind
    value: float
    unit: str = Field(description="Unit as spoken; normalized to UCUM by our code, not the LLM.")
    source_text: str = Field(description="Exact span from the transcript, for highlighting.")


class Medication(BaseModel):
    name: str
    dose: str | None
    route: str | None
    source_text: str


class Extraction(BaseModel):
    patient_mention: str | None = Field(
        description='Placeholder token after redaction, e.g. "<PATIENT_1>".'
    )
    vitals: list[Vital]
    symptoms: list[str]
    medications: list[Medication]
    free_text_summary: str = Field(description="1-2 sentences, for the nurse.")
    uncertain: list[str] = Field(description="Anything the model was not sure about.")
