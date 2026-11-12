"""Switch an extraction between the redacted form we store and the real words the nurse sees.

Stored payloads (every version, and the audit log) hold placeholders only. The browser gets the
original words so spans can be highlighted, and whatever it sends back is de-identified again
before it is stored, so a nurse's edit never puts a name into the append-only audit log.
"""

from collections.abc import Callable

from carenote.contracts.extraction import Extraction
from carenote.pipeline.redaction import reredact, unredact


def _map_text(extraction: Extraction, fn: Callable[[str], str]) -> Extraction:
    return extraction.model_copy(
        update={
            "patient_mention": fn(extraction.patient_mention)
            if extraction.patient_mention
            else None,
            "vitals": [
                v.model_copy(update={"source_text": fn(v.source_text)}) for v in extraction.vitals
            ],
            "medications": [
                m.model_copy(update={"source_text": fn(m.source_text)})
                for m in extraction.medications
            ],
            "free_text_summary": fn(extraction.free_text_summary),
            "uncertain": [fn(x) for x in extraction.uncertain],
        }
    )


def reidentify(extraction: Extraction, mapping: dict[str, str]) -> Extraction:
    """Placeholders -> original words, for an authorized viewer."""
    return _map_text(extraction, lambda text: unredact(text, mapping))


def deidentify(extraction: Extraction, mapping: dict[str, str]) -> Extraction:
    """Original words -> placeholders, before anything from the browser is stored."""
    return _map_text(extraction, lambda text: reredact(text, mapping))
