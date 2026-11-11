"""Shared normalisation / parsing helpers. Single source of truth."""

import csv
import re
from datetime import date, datetime
from pathlib import Path

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_DIGITS_RE = re.compile(r"\D+")

DATE_FORMATS = [
    "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y",
    "%d-%b-%y", "%d-%b-%Y", "%Y/%m/%d", "%d %b %Y",
]


def load_mapping(path: Path) -> dict[str, str]:
    with open(path, encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return {row["raw_value"]: row["standard_value"] for row in reader}


def standardise(mapping: dict[str, str], value: str, fallback: str) -> str:
    """Map a value to its standard form; already-standard values pass through.

    Idempotent: standardise(m, standardise(m, v)) == standardise(m, v).
    """
    v = value.strip()
    if v in mapping.values():
        return v
    if v in mapping:
        return mapping[v]
    if v == "":
        return mapping.get("", fallback)
    return fallback


def norm_id(value: str) -> str:
    """Canonical identifier: strip, upper, remove spaces/dashes."""
    return re.sub(r"[\s\-]+", "", value.strip().upper())


def norm_email(value: str) -> str:
    return value.strip().lower()


def norm_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def parse_date(value: str) -> date | None:
    v = value.strip()
    if not v:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    # last resort: ISO parse
    try:
        return date.fromisoformat(v)
    except ValueError:
        return None


def parse_float(value: str) -> float | None:
    v = value.strip().replace(",", "").replace("\u20b9", "").replace("?", "").strip()
    if v == "" or v.upper() in {"NA", "N/A", "NULL", "NONE", "UNKNOWN"}:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def parse_int(value: str) -> int | None:
    f = parse_float(value)
    if f is None:
        return None
    if f != int(f):
        return None
    return int(f)


def parse_discount_frac(value: str) -> float | None:
    """Return discount as fraction 0..1. '10%'->0.10, '0.1'->0.10, '15'->0.15, '20 percent'->0.20."""
    v = value.strip().lower()
    if v == "" or v in {"na", "n/a", "null", "none", "unknown"}:
        return None
    v = v.replace("percent", "").replace("%", "").strip()
    try:
        num = float(v.replace(",", ""))
    except ValueError:
        return None
    if num < 0:
        return None
    if num <= 1:
        return num  # fraction form
    return num / 100.0  # whole-percent form


def is_placeholder(value: str, placeholders: set[str]) -> bool:
    return value.strip() in placeholders


def is_blank(value: str) -> bool:
    return value.strip() == ""


def valid_email(value: str, placeholders: set[str]) -> bool:
    v = value.strip()
    if v == "" or v in placeholders:
        return False
    return bool(EMAIL_RE.match(v))


def phone_digits(value: str) -> str:
    return PHONE_DIGITS_RE.sub("", value)