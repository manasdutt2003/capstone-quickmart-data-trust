"""Canonical line-value definition (Sprint 3, deliverable 1).

This module holds the ONE Python definition of line value. Every other
module must call `line_value` instead of recomputing the formula
(enforced by tests/test_line_value_single_definition.py).

Formula: line_value = quantity * unit_price_paid * (1 - discount_frac),
rounded to 2 dp. Null in any input gives NULL (None), never 0 — the
zero-fill used by legacy commission/mart paths lives at those call
sites (frozen) and in deduplication.commission_frame fillna, not here.
Parsing stays at call sites via normalise (frozen behaviour); the
percentage-vs-fraction discount rule lives once in
normalise.parse_discount_frac.
"""


def line_value(qty, price, discount_frac):
    """Single line-value definition. None in -> None out; else round 2dp."""
    if qty is None or price is None or discount_frac is None:
        return None
    return round(qty * price * (1 - discount_frac), 2)


def row_line_value(row):
    """Line value for one order-line mapping (parsing + legacy mapping).

    Parsing mirrors the historical row parsers exactly: int()/float()
    first with parse_* fallback, blank discount means 0.0, unparseable
    discount means 0.0, discount >= 1 maps to 0.0. None quantity or price
    gives None (never 0); callers zero-fill where their frozen contract
    requires it.
    """
    from .normalise import parse_discount_frac, parse_float, parse_int

    try:
        qty = int(row["quantity"]) \
            if str(row["quantity"]).strip() != "" else None
    except (ValueError, TypeError):
        qty = parse_int(str(row["quantity"]))
    try:
        price = float(row["unit_price_paid"]) \
            if str(row["unit_price_paid"]).strip() != "" else None
    except (ValueError, TypeError):
        price = parse_float(str(row["unit_price_paid"]))
    disc = row.get("discount", 0)
    try:
        disc = float(disc) if disc is not None and str(disc).strip() != "" \
            else 0.0
    except (ValueError, TypeError):
        disc = parse_discount_frac(str(disc)) or 0.0
    return line_value(qty, price,
                      disc if (disc is not None and disc < 1) else 0.0)
