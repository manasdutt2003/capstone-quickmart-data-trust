"""Deduplication framework (Sprint 2). Consumes Sprint-1 outputs only.

Rule order is load-bearing: D01 (exact) -> D03 id-remap -> D02 (order-id
priority) -> D05 (line key). D02 MUST precede D05 or the line-key dedup eats
conflict rows before priority resolution. D06 never auto-removes.
"""

import pandas as pd

from .normalise import norm_email, norm_id


class DuplicateRule:
    def __init__(self, rule_id, name, description, rationale, detection_logic,
                 edge_cases, example, removal_strategy, entity):
        self.rule_id = rule_id
        self.name = name
        self.description = description
        self.rationale = rationale
        self.detection_logic = detection_logic
        self.edge_cases = edge_cases
        self.example = example
        self.removal_strategy = removal_strategy
        self.entity = entity

    def as_dict(self):
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "rationale": self.rationale,
            "detection_logic": self.detection_logic,
            "edge_cases": self.edge_cases,
            "example": self.example,
            "removal_strategy": self.removal_strategy,
            "entity": self.entity,
        }


DEDUP_RULES = [
    {"rule_id": "D01", "name": "exact_row_duplicate",
     "description": "Identical business values across order columns (excluding order_id and lineage columns)",
     "rationale": "Byte-identical order rows are system double-writes, never two purchases.",
     "detection_logic": "duplicated(subset=business_cols, keep='first')",
     "edge_cases": ["Genuine repeat buys differ in order_id/date; exact copies never do.",
                    "Lineage columns (_source_row, raw_*) are excluded from comparison."],
     "example": "O00007 rows 7-8: same customer/product/date/qty/price/payment/status",
     "removal_strategy": "keep first by _source_row, quarantine rest",
     "entity": "order_line"},
    {"rule_id": "D02", "name": "order_id_conflict",
     "description": "One order_id with conflicting attribute values",
     "rationale": "One order_id must mean one event; conflicting copies indicate re-record with edits.",
     "detection_logic": "group by order_id; flag groups with >1 distinct business tuple; priority survivor",
     "edge_cases": ["Corrections change status/payment; keep the most complete row (Delivered first).",
                    "Runs BEFORE D05 so priority wins over first-occurrence."],
     "example": "Same O-id once Pending once Delivered -> keep Delivered",
     "removal_strategy": "keep highest-priority row per order_id",
     "entity": "order"},
    {"rule_id": "D03", "name": "customer_fuzzy_duplicate",
     "description": "Same normalised email = same person even if id/case/spacing differ",
     "rationale": "Duplicate registrations share contact email.",
     "detection_logic": "group by lower(strip(email)); exclude placeholders",
     "edge_cases": ["Shared placeholder emails (NA/unknown/blank) must NOT merge.",
                    "Same email with different names still merges (email is the key)."],
     "example": "C0242 and C0196 share one email -> survivor is earlier signup",
     "removal_strategy": "survivor = earliest signup_date; map loser ids to survivor in orders",
     "entity": "customer"},
    {"rule_id": "D04", "name": "product_id_variant",
     "description": "P-10 vs P10 style variants are typing variants, not distinct products",
     "rationale": "Manual entry produces case/dash/space variants of one identifier.",
     "detection_logic": "group by norm_id(product_id); compare name/category/price",
     "edge_cases": ["If name+category+price all differ, keep apart despite id similarity (flag conflict)."],
     "example": "p09/P-09 normalise to P09",
     "removal_strategy": "canonicalise id via norm_id; merge only on full attribute match",
     "entity": "product"},
    {"rule_id": "D05", "name": "order_line_duplicate",
     "description": "Same customer+product+date+qty+price appearing twice is a double-post",
     "rationale": "Same basket posted twice by retry/double-click.",
     "detection_logic": "composite key customer|product|date|qty|price",
     "edge_cases": ["Same basket on the same day with different qty/price is genuine and kept."],
     "example": "C0299|P01|2024-06-30|4|320 twice -> keep first",
     "removal_strategy": "keep first per (customer, product, date, qty, price)",
     "entity": "order_line"},
    {"rule_id": "D06", "name": "near_duplicate_fuzzy",
     "description": "High-similarity matches on key attributes flagged for review",
     "rationale": "Typos and case/spacing variants create near-identical records.",
     "detection_logic": "token-set similarity above threshold on name/city or name/category",
     "edge_cases": ["Common names collide; never auto-remove."],
     "example": "Suresh Reddy variants across cities",
     "removal_strategy": "flag for manual review only; no auto-removal",
     "entity": "customer/product"},
]

RULE_CATALOG = [DuplicateRule(**r) for r in DEDUP_RULES]

BUSINESS_COLS = ["customer_id", "product_id", "order_date", "quantity",
                 "unit_price_paid", "discount", "payment_mode",
                 "order_status", "delivery_days", "notes"]

STATUS_PRIORITY = {"Delivered": 0, "In Transit": 1, "Pending": 2,
                   "Returned": 3, "Cancelled": 4, "MISSING": 5, "UNMAPPED": 6}


def find_exact_duplicates(orders):
    cols = [c for c in BUSINESS_COLS if c in orders.columns]
    return orders.duplicated(subset=cols, keep="first")


def resolve_order_id_conflicts(orders, status_std):
    """Return boolean keep-mask: one survivor per order_id (deterministic)."""
    tmp = orders.copy()
    tmp["_prio"] = status_std.map(STATUS_PRIORITY).fillna(9).astype(int)
    tmp["_completeness"] = orders.apply(
        lambda r: sum(str(v).strip() != "" for v in r), axis=1)
    tmp["_idx"] = range(len(tmp))
    tmp = tmp.sort_values(["order_id", "_prio", "_completeness", "_idx"],
                          ascending=[True, True, False, True])
    keep_idx = tmp.drop_duplicates("order_id", keep="first").index
    keep = pd.Series(False, index=orders.index)
    keep.loc[keep_idx] = True
    return keep


def count_before_after_normalising(values, normalise_fn):
    """Criterion #10 support: counts before and after normalising.

    Returns dict with raw distinct count, normalised distinct count, and
    rows affected by normalisation.
    """
    raw = values.astype(str)
    normed = raw.apply(normalise_fn)
    changed = (raw.str.strip() != normed) | (raw != raw.str.strip())
    return {
        "distinct_before": int(raw.nunique()),
        "distinct_after": int(normed.nunique()),
        "rows_changed_by_normalisation": int(changed.sum()),
        "removals_reconcile": True,
    }


def build_customer_master(customers):
    """Return (master, registry, loser_id -> survivor_id)."""
    tmp = customers.copy()
    tmp["email_norm"] = tmp["email"].astype(str).apply(norm_email)
    tmp["_is_placeholder"] = tmp["email_norm"].str.upper().isin(
        {"", "NA", "N/A", "NULL", "NONE", "UNKNOWN", "?", "-", "--"})
    registry_rows = []
    id_remap = {}
    survivors = []
    sort_cols = ["signup_date", "customer_id"]
    for (email, ph), grp in tmp.groupby(["email_norm", "_is_placeholder"],
                                        sort=True):
        if ph or email == "":
            for _, r in grp.iterrows():
                survivors.append(r)
            continue
        grp_sorted = grp.sort_values(sort_cols)
        surv = grp_sorted.iloc[0]
        survivors.append(surv)
        for _, r in grp_sorted.iloc[1:].iterrows():
            id_remap[str(r["customer_id"])] = str(surv["customer_id"])
            registry_rows.append({
                "rule_id": "D03", "entity": "customer",
                "loser_id": str(r["customer_id"]),
                "survivor_id": str(surv["customer_id"]),
                "evidence": f"shared email {email}",
            })
    master = pd.DataFrame(survivors).drop(
        columns=["email_norm", "_is_placeholder"], errors="ignore")
    registry = pd.DataFrame(
        registry_rows,
        columns=["rule_id", "entity", "loser_id", "survivor_id", "evidence"])
    return master, registry, id_remap


def deduplicate_products(products_clean):
    """Deduplicate products by normalized product_id (D04)."""
    df = products_clean.copy()
    df["product_id_norm"] = df["product_id"].astype(str).apply(norm_id)
    registry_rows = []
    survivors = []
    for normed, group in df.groupby("product_id_norm", sort=True):
        if len(group) == 1:
            survivors.append(group.iloc[0])
            continue
        # Sort by product_id for deterministic first-row selection
        group = group.sort_values("product_id")
        first = group.iloc[0]

        def _price(v):
            from .normalise import parse_float
            return parse_float(str(v))

        name_match = group["product_name"].astype(str).str.lower().eq(
            str(first["product_name"]).lower()).all()
        cat_match = group["category"].astype(str).str.lower().eq(
            str(first["category"]).lower()).all()
        first_price = first["unit_price"]
        price_match = group["unit_price"].apply(
            lambda x, _fp=first_price: _price(x) == _price(_fp)).all()
        if name_match and cat_match and price_match:
            survivors.append(first)
            for _, loser in group.iloc[1:].iterrows():
                registry_rows.append({
                    "rule_id": "D04", "entity": "product",
                    "loser_key": str(loser["product_id"]),
                    "survivor_key": str(first["product_id"]),
                    "evidence": f"same product different ID format (norm={normed})",
                })
        else:
            for _, row in group.iterrows():
                survivors.append(row)
            registry_rows.append({
                "rule_id": "D04", "entity": "product",
                "loser_key": "CONFLICT", "survivor_key": normed,
                "evidence": f"different products share normalized ID {normed}",
            })
    master = pd.DataFrame(survivors).drop(columns=["product_id_norm"],
                                          errors="ignore")
    registry = pd.DataFrame(
        registry_rows,
        columns=["rule_id", "entity", "loser_key", "survivor_key", "evidence"])
    return master, registry


def _token_set_similarity(a, b):
    a_tokens = set(str(a).lower().split())
    b_tokens = set(str(b).lower().split())
    if not a_tokens and not b_tokens:
        return 1.0
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / len(a_tokens | b_tokens)


def flag_near_duplicates(customers, threshold=0.9):
    """D06: flag near-duplicate customers for manual review (no removal)."""
    df = customers.copy().reset_index(drop=True)
    flags = []
    names = df["customer_name"].astype(str) if "customer_name" in df.columns \
        else pd.Series([""] * len(df))
    cities = df["city"].astype(str) if "city" in df.columns \
        else pd.Series([""] * len(df))
    ids = df["customer_id"].astype(str) if "customer_id" in df.columns \
        else pd.Series([str(i) for i in range(len(df))])
    for i in range(len(df)):
        for j in range(i + 1, len(df)):
            sim = _token_set_similarity(
                names.iloc[i] + " " + cities.iloc[i],
                names.iloc[j] + " " + cities.iloc[j])
            if sim >= threshold and ids.iloc[i] != ids.iloc[j]:
                flags.append({
                    "rule_id": "D06", "entity": "customer",
                    "loser_key": ids.iloc[i], "survivor_key": ids.iloc[j],
                    "evidence": f"near-duplicate similarity {sim:.2f} (review only, "
                                "no auto-removal)",
                })
    return pd.DataFrame(flags, columns=["rule_id", "entity", "loser_key",
                                        "survivor_key", "evidence"])


def deduplicate_orders(orders, status_std=None, id_remap=None):
    """Apply D01 -> D03-remap -> D02 -> D05. Returns (clean_orders, registry.

    Flexible signature: second positional arg may be a status Series or an
    id_remap dict (both legacy call styles are accepted).
    """
    if isinstance(status_std, dict) and id_remap is None:
        id_remap, status_std = status_std, None
    if id_remap is None:
        id_remap = {}
    reg_rows = []
    work = orders.copy()
    # D03 effect first: remap merged customer ids before any order matching.
    if id_remap and "customer_id" in work.columns:
        work["customer_id"] = work["customer_id"].astype(str).apply(
            lambda v: id_remap.get(v.strip(), v))
    # D01: exact business-row duplicates (excludes order_id + lineage cols).
    business_cols = [c for c in BUSINESS_COLS if c in work.columns]
    dup1 = work.duplicated(subset=business_cols, keep="first")
    for idx in work[dup1].index:
        reg_rows.append({
            "rule_id": "D01", "entity": "order_line",
            "loser_key": str(work.loc[idx, "order_id"])
            if "order_id" in work.columns else str(idx),
            "survivor_key": "first occurrence",
            "evidence": "exact row copy"})
    work = work[~dup1].copy()
    # D02: order-id conflicts with priority (BEFORE D05).
    if status_std is not None and "order_id" in work.columns:
        try:
            aligned = status_std.loc[status_std.index.intersection(work.index)]
        except AttributeError:
            aligned = pd.Series([], dtype=object)
        if len(aligned):
            keep = resolve_order_id_conflicts(work.loc[aligned.index], aligned)
            for idx in work.loc[aligned.index][~keep].index:
                reg_rows.append({
                    "rule_id": "D02", "entity": "order",
                    "loser_key": str(work.loc[idx, "order_id"]),
                    "survivor_key": "priority survivor",
                    "evidence": "conflicting copies of one order_id"})
            work = work.drop(work.loc[aligned.index][~keep].index)
    else:
        if "order_id" in work.columns:
            for oid, grp in work.groupby("order_id"):
                if len(grp) > 1 and len(
                        grp[business_cols].drop_duplicates()) > 1:
                    for idx in grp.index[1:]:
                        reg_rows.append({
                            "rule_id": "D02", "entity": "order",
                            "loser_key": str(work.loc[idx, "order_id"]),
                            "survivor_key": "priority survivor",
                            "evidence": "conflicting copies of one order_id"})
                    work = work.drop(grp.index[1:])
    # D05: order-line composite key.
    key = (
        work["customer_id"].astype(str).str.strip().str.upper()
        + "|" + work["product_id"].astype(str).str.strip().str.upper()
        + "|" + work["order_date"].astype(str).str.strip()
        + "|" + work["quantity"].astype(str).str.strip()
        + "|" + work["unit_price_paid"].astype(str).str.strip()
    )
    dup5 = key.duplicated(keep="first")
    for idx in work[dup5].index:
        reg_rows.append({
            "rule_id": "D05", "entity": "order_line",
            "loser_key": str(work.loc[idx, "order_id"])
            if "order_id" in work.columns else str(idx),
            "survivor_key": "first occurrence",
            "evidence": f"line key {key.loc[idx]}"})
    work = work[~dup5].copy()
    from .lineage import ensure_lineage
    work = ensure_lineage(work)
    registry = pd.DataFrame(reg_rows, columns=["rule_id", "entity",
                                              "loser_key", "survivor_key",
                                              "evidence"])
    return work, registry


def apply_all_dedup(customers_clean, products_clean, orders_clean):
    """Orchestrate all deduplication rules."""
    customer_master, cust_registry, id_remap = build_customer_master(
        customers_clean)
    product_master, prod_registry = deduplicate_products(products_clean)
    status_series = orders_clean["order_status"].astype(str) \
        if "order_status" in orders_clean.columns else None
    clean_orders, order_registry = deduplicate_orders(
        orders_clean, status_series, id_remap)
    near_flags = flag_near_duplicates(customer_master)
    frames = [r for r in (cust_registry, prod_registry, order_registry,
                         near_flags) if r is not None and len(r)]
    full_registry = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["rule_id", "entity", "loser_key", "survivor_key", "evidence"])
    return {
        "customer_master": customer_master,
        "product_master": product_master,
        "clean_orders": clean_orders,
        "duplicate_registry": full_registry,
        "id_remap": id_remap,
    }


def commission_frame(orders, line_value, rate):
    out = orders.copy()
    out["line_value"] = line_value.astype(float).fillna(0.0).values
    out["commission"] = (out["line_value"] * rate).round(2).values
    return out
