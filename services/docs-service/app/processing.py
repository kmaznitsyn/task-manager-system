"""Deterministic extraction stub for logistics documents.

Real-world this would call an OCR/LLM pipeline. Here we keep it
self-contained: regex/keyword matching against `raw_text`. Each doc_type
declares the fields it wants and the patterns that locate them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import DocType


@dataclass(frozen=True)
class _Field:
    name: str
    # Regex with a single capturing group. Case-insensitive, multiline.
    pattern: str
    required: bool = True


# Patterns intentionally loose — they only need to demo the pipeline.
_RULES: dict[DocType, tuple[_Field, ...]] = {
    DocType.bill_of_lading: (
        _Field("bol_number", r"B/?L(?:\s*number)?\s*[:#]\s*([A-Z0-9-]+)"),
        _Field("consignor", r"consignor\s*[:#]\s*([^\n]+)"),
        _Field("consignee", r"consignee\s*[:#]\s*([^\n]+)"),
        _Field("weight_kg", r"weight\s*[:#]\s*([\d.,]+)\s*kg", required=False),
    ),
    DocType.manifest: (
        _Field("vessel", r"vessel\s*[:#]\s*([^\n]+)"),
        _Field("voyage", r"voyage\s*[:#]\s*([A-Z0-9-]+)"),
        _Field("items_count", r"items?\s*[:#]\s*(\d+)", required=False),
    ),
    DocType.proof_of_delivery: (
        _Field("signed_by", r"signed\s*by\s*[:#]\s*([^\n]+)"),
        _Field("delivered_at", r"delivered\s*at\s*[:#]\s*([^\n]+)"),
        _Field("condition", r"condition\s*[:#]\s*([^\n]+)", required=False),
    ),
    DocType.invoice: (
        _Field("invoice_number", r"invoice\s*(?:no|number|#)\s*[:#]?\s*([A-Z0-9-]+)"),
        _Field("total_amount", r"total\s*[:#]\s*([\d.,]+)"),
        _Field("currency", r"currency\s*[:#]\s*([A-Z]{3})", required=False),
    ),
    DocType.customs_declaration: (
        _Field("country_of_origin", r"country\s*of\s*origin\s*[:#]\s*([^\n]+)"),
        _Field("hs_code", r"HS\s*code\s*[:#]\s*([\d.]+)"),
        _Field("declared_value", r"declared\s*value\s*[:#]\s*([\d.,]+)", required=False),
    ),
}


class ExtractionError(Exception):
    """Raised when one or more required fields cannot be found."""

    def __init__(self, missing: list[str]):
        super().__init__(f"missing required fields: {', '.join(missing)}")
        self.missing = missing


def extract(doc_type: DocType, raw_text: str) -> dict:
    """Extract structured fields from raw_text per the rules for doc_type.

    Returns a dict of {field_name: value}. Raises ExtractionError if any
    required field is missing.
    """
    rules = _RULES[doc_type]
    out: dict[str, str] = {}
    missing: list[str] = []
    for field in rules:
        match = re.search(field.pattern, raw_text, re.IGNORECASE | re.MULTILINE)
        if match:
            out[field.name] = match.group(1).strip()
        elif field.required:
            missing.append(field.name)
    if missing:
        raise ExtractionError(missing)
    return out
