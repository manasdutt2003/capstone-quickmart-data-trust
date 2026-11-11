"""Cleaning stage (Sprint-1 amendment): raw-text frames -> cleaned derivatives.

Raw extracts are NEVER edited. This module produces cleaned COPIES that every
later sprint consumes exclusively:
- whitespace stripped on all values
- case/spacing variants mapped to standards via config/*_mapping.csv
- placeholders (NA, N/A, -, unknown, ...) -> "" in clean columns
- dates parsed to ISO YYYY-MM-DD (unparseable -> "")
- numerics canonicalised: commas/currency/? removed (invalid -> "")
- discounts canonicalised to fraction strings ("10%" -> "0.1", "15" -> "0.15")
- every clean column keeps its original text in a raw_<col> mirror
- every row keeps _source_row (1-based data-row number) for lineage

Downstream modules (quality, dedup, validation, marts) take ONLY these frames.
"""

import re
from datetime import datetime

import pandas as pd

from .normalise import parse_discount_frac, parse_float, parse_int

PLACEHOLDER_TEXTS = {"NA", "N/A", "na", "n/a", "-", "--", "unknown", "UNKNOWN",
                     "Unknown", "null", "NULL", "None", "none", "?"}


def _clean_str(value: str) -> str:
    return value.strip()


def _std(mapping: dict[str, str], value: str, fallback: str) -> str:
    v = value.strip()
    if v in mapping:
        return mapping[v]
    if v == "":
        return mapping.get("", fallback)
    return fallback


from datetime import datetime
import re

def clean_date(value):
    if value is None:
        return ""

    value = str(value).strip()

    if value.upper() in ("", "NULL", "N/A", "NA", "NAN"):
        return ""

    # Remove ordinal suffixes (1st, 2nd, 3rd, 24th, etc.)
    value = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', value, flags=re.IGNORECASE)

    date_formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%m-%d-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%d.%m.%Y",
        "%d %B %Y",      # 24 November 2026
        "%d %b %Y",      # 24 Nov 2026
        "%d %B, %Y",     # 24 November, 2026
        "%d %b, %Y",     # 24 Nov, 2026
    ]

    for fmt in date_formats:
        try:
            # Fixed: Returns ISO format YYYY-MM-DD to match project requirements
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    return ""

import re

def clean_currency(value):
    if value is None:
        return ""

    value = str(value).strip()

    if value.upper() in ("", "NULL", "N/A", "NA", "NAN"):
        return ""

    # Handle accounting format: (1000) => -1000
    if value.startswith("(") and value.endswith(")"):
        value = "-" + value[1:-1]

    # Remove currency symbols and commas
    value = re.sub(r"[^\d.\-]", "", value)

    try:
        f = float(value)
        # Return as a clean string representation (drops unnecessary .0 for integers)
        return str(int(f)) if f == int(f) else str(f)
    except ValueError:
        return ""
import re

def _clean_num(value: str) -> str:
    v = str(value).strip()
    if v == "" or v in PLACEHOLDER_TEXTS:
        return ""
    
    # Handle accounting format: (1500) => -1500
    if v.startswith("(") and v.endswith(")"):
        v = "-" + v[1:-1]
        
    # Remove currency symbols and commas so parse_float can parse it
    v = re.sub(r"[^\d.\-]", "", v)
    
    f = parse_float(v)
    if f is None:
        return ""
    return str(int(f)) if f == int(f) else str(f)


def _clean_discount(value: str) -> str:
    v = value.strip()
    if v == "" or v in PLACEHOLDER_TEXTS:
        return ""
    frac = parse_discount_frac(v)
    return str(frac) if frac is not None else ""


def _with_lineage(clean: pd.DataFrame, raw: pd.DataFrame) -> pd.DataFrame:
    for col in list(clean.columns):
        clean[f"raw_{col}"] = raw[col].astype(str).values
    clean["_source_row"] = range(1, len(clean) + 1)
    return clean


def _clean_int_str(value):
    v = value.strip()
    if v == "" or v in PLACEHOLDER_TEXTS:
        return ""
    i = parse_int(v)
    return str(i) if i is not None else ""


def clean_customers(raw: pd.DataFrame, city_map: dict[str, str]) -> pd.DataFrame:
    clean = pd.DataFrame({
        "customer_id": raw["customer_id"].astype(str).str.strip(),
        "customer_name": raw["customer_name"].astype(str).str.strip(),
        "email": raw["email"].astype(str).apply(
            lambda v: "" if v.strip() in PLACEHOLDER_TEXTS else v.strip().lower()),
        "city": raw["city"].astype(str).apply(lambda v: _std(city_map, v, "UNMAPPED")),
        "phone": raw["phone"].astype(str).str.strip(),
        "signup_date": raw["signup_date"].astype(str).apply(clean_date),
    })
    clean = _with_lineage(clean, raw)
    # Sort by ALL columns for deterministic output regardless of input order
    clean = clean.sort_values(list(clean.columns)).reset_index(drop=True)
    # Reassign _source_row after sort for deterministic output
    clean["_source_row"] = range(1, len(clean) + 1)
    return clean


def clean_products(raw: pd.DataFrame, cat_map: dict[str, str]) -> pd.DataFrame:
    clean = pd.DataFrame({
        "product_id": raw["product_id"].astype(str).str.strip(),
        "product_name": raw["product_name"].astype(str).str.strip(),
        "category": raw["category"].astype(str).apply(lambda v: _std(cat_map, v, "UNMAPPED")),
        "unit_price": raw["unit_price"].astype(str).apply(_clean_num),
        "stock_qty": raw["stock_qty"].astype(str).apply(_clean_num),
    })
    clean = _with_lineage(clean, raw)
    # Sort by ALL columns for deterministic output regardless of input order
    clean = clean.sort_values(list(clean.columns)).reset_index(drop=True)
    # Reassign _source_row after sort for deterministic output
    clean["_source_row"] = range(1, len(clean) + 1)
    return clean


def clean_orders(
    raw: pd.DataFrame, status_map: dict[str, str], pay_map: dict[str, str]
) -> pd.DataFrame:
    clean = pd.DataFrame({
        "order_id": raw["order_id"].astype(str).str.strip(),
        "customer_id": raw["customer_id"].astype(str).str.strip(),
        "product_id": raw["product_id"].astype(str).str.strip(),
        "order_date": raw["order_date"].astype(str).apply(clean_date),
        "quantity": raw["quantity"].astype(str).apply(_clean_int_str),
        "unit_price_paid": raw["unit_price_paid"].astype(str).apply(_clean_num),
        "discount": raw["discount"].astype(str).apply(_clean_discount),
        "payment_mode": raw["payment_mode"].astype(str).apply(
            lambda v: _std(pay_map, v, "UNMAPPED")),
        "order_status": raw["order_status"].astype(str).apply(
            lambda v: _std(status_map, v, "UNMAPPED")),
        "delivery_days": raw["delivery_days"].astype(str).apply(_clean_int_str),
        "notes": raw["notes"].astype(str).str.strip(),
    })
    clean = _with_lineage(clean, raw)
    # Sort by ALL columns for deterministic output regardless of input order
    clean = clean.sort_values(list(clean.columns)).reset_index(drop=True)
    # Reassign _source_row after sort for deterministic output
    clean["_source_row"] = range(1, len(clean) + 1)
    return clean


def clean_all(
    customers: pd.DataFrame, products: pd.DataFrame, orders: pd.DataFrame,
    city_map: dict[str, str], cat_map: dict[str, str],
    status_map: dict[str, str], pay_map: dict[str, str],
    source_files=None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Clean all three extracts and attach row lineage.

    `source_files` optionally maps table name -> source filename
    (e.g. {"orders": "orders.csv"}); filenames only, never paths.
    """
    from .lineage import ensure_lineage

    cleaned = (
        clean_customers(customers, city_map),
        clean_products(products, cat_map),
        clean_orders(orders, status_map, pay_map),
    )
    names = ("customers", "products", "orders")
    out = []
    for frame, table in zip(cleaned, names):
        fname = None
        if source_files is not None:
            fname = source_files.get(table)
        frame = ensure_lineage(frame, source_file=fname)
        if "_source_row" in frame.columns:
            frame["source_row_number"] = frame["_source_row"].values
        out.append(frame)
    return (out[0], out[1], out[2])