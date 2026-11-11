"""Trusted-order rule engine (Sprint 3). Each rule -> PASS / FAIL / WARNING."""

import enum
import math
import re
from dataclasses import dataclass

import pandas as pd

from .line_value import line_value, row_line_value
from .mapping_gate import (
    MappingGateError,
    apply_mapping_with,
    load_mapping,
)
from .normalise import (
    norm_id,
    parse_date,
    parse_discount_frac,
    parse_float,
    parse_int,
)


def _is_nan(x):
    return isinstance(x, float) and math.isnan(x)


def _norm_id(value):
    import re
    return re.sub(r"[\s\-]+", "", str(value).strip().upper())


RULES = [
    {"rule_id": "R01", "name": "Customer Exists", "severity": "FAIL",
     "description": "customer_id exists in customer master"},
    {"rule_id": "R02", "name": "Product Exists", "severity": "FAIL",
     "description": "product_id exists in product master"},
    {"rule_id": "R03", "name": "Customer Signup Before Order",
     "severity": "FAIL",
     "description": "customer signup_date <= order_date"},
    {"rule_id": "R04", "name": "Valid Order Date", "severity": "FAIL",
     "description": "order_date is parseable and not future"},
    {"rule_id": "R05", "name": "Valid Quantity", "severity": "FAIL",
     "description": "quantity is positive integer"},
    {"rule_id": "R06", "name": "Valid Price", "severity": "FAIL",
     "description": "unit_price_paid is non-negative"},
    {"rule_id": "R07", "name": "Valid Discount", "severity": "WARNING",
     "description": "discount is parseable and 0-100%"},
    {"rule_id": "R08", "name": "Valid Status", "severity": "FAIL",
     "description": "order_status is not MISSING/UNMAPPED"},
    {"rule_id": "R09", "name": "Valid Delivery Days", "severity": "WARNING",
     "description": "delivery_days is 0-30 for Delivered, null/0 for Cancelled"},
    {"rule_id": "R10", "name": "Price vs Catalogue", "severity": "WARNING",
     "description": "unit_price_paid within 30% of catalogue price"},
    {"rule_id": "R11", "name": "Valid Payment", "severity": "WARNING",
     "description": "payment_mode is not MISSING/UNMAPPED"},
]


def line_value_of(qty, price, disc_frac):
    """Legacy entry point; delegates arithmetic to src.line_value.line_value.

    Frozen mapping preserved: None discount means 0.0 discount (not NULL).
    New code must call src.line_value.line_value directly for NULL semantics.
    """
    if qty is None or price is None:
        return None
    d = disc_frac if disc_frac is not None else 0.0
    return line_value(qty, price, d)


def _as_date(value):
    d = parse_date(str(value if value is not None else ""))
    return d.isoformat() if d else None


def validate_orders(orders, customers, products, city_map, cat_map, pay_map,
                    status_map, today="2026-10-11"):
    """Validate orders against R01-R11. Returns trusted/rejected/warning/log."""
    df = orders.copy()
    results = pd.DataFrame(index=df.index)

    cust_map = set(customers["customer_id"].astype(str).str.strip())
    prod_map = set(products["product_id"].astype(str).str.strip())
    prod_price = dict(zip(products["product_id"].astype(str).str.strip(),
                          products["unit_price"]))
    cust_signup = dict(zip(customers["customer_id"].astype(str).str.strip(),
                           customers["signup_date"]))

    results["R01"] = df["customer_id"].astype(str).str.strip().isin(
        cust_map).values
    results["R02"] = df["product_id"].astype(str).str.strip().isin(
        prod_map).values

    def _check_signup(row):
        cust_id = str(row["customer_id"]).strip()
        if cust_id not in cust_signup:
            return False
        signup = _as_date(cust_signup[cust_id])
        order = _as_date(row["order_date"])
        return signup is not None and order is not None and signup <= order

    results["R03"] = df.apply(_check_signup, axis=1).values
    results["R04"] = df["order_date"].apply(
        lambda x: _as_date(x) is not None and _as_date(x) <= today).values

    def _qty_ok(x):
        if x is None:
            return False
        if isinstance(x, float):
            if _is_nan(x):
                return False
            return x == int(x) and int(x) > 0
        s = str(x).strip()
        if s == "":
            return False
        i = parse_int(s)
        return i is not None and i > 0

    results["R05"] = df["quantity"].apply(_qty_ok).values

    def _price_ok(x):
        if x is None:
            return False
        if isinstance(x, float):
            if _is_nan(x):
                return False
            return x >= 0
        s = str(x).strip()
        if s == "":
            return False
        f = parse_float(s)
        return f is not None and f >= 0

    results["R06"] = df["unit_price_paid"].apply(_price_ok).values

    def _disc_ok(x):
        if x is None or _is_nan(x) \
                or str(x).strip() == "":
            return True
        try:
            f = float(str(x))
        except (ValueError, TypeError):
            d = parse_discount_frac(str(x))
            return d is not None and 0 <= d <= 1
        return 0 <= f <= 1

    results["R07"] = df["discount"].apply(_disc_ok).values
    results["R08"] = (~df["order_status"].isin(
        ["MISSING", "UNMAPPED"])).values

    def _check_delivery(row):
        status = row["order_status"]
        days = row["delivery_days"]
        if status == "Delivered":
            if days is None or _is_nan(days):
                return False
            try:
                return 0 <= int(days) <= 30
            except (ValueError, TypeError):
                return False
        if status == "Cancelled":
            if days is None or str(days).strip() == "":
                return True
            try:
                return int(days) == 0
            except (ValueError, TypeError):
                return False
        return True

    results["R09"] = df.apply(_check_delivery, axis=1).values

    def _check_price(row):
        pid = str(row["product_id"]).strip()
        if pid not in prod_map:
            return True
        cat_price = prod_price.get(pid)
        if cat_price is None or _is_nan(cat_price):
            return True
        paid = row["unit_price_paid"]
        if paid is None or _is_nan(paid):
            return True
        disc = row["discount"]
        try:
            d = float(disc) if disc is not None and str(disc).strip() != "" \
                else 0.0
        except (ValueError, TypeError):
            d = parse_discount_frac(str(disc)) or 0.0
        if d >= 1:
            return True
        try:
            implied = float(paid) / (1 - d)
            return abs(implied - float(cat_price)) / float(cat_price) <= 0.3
        except (ValueError, TypeError, ZeroDivisionError):
            return True

    results["R10"] = df.apply(_check_price, axis=1).values
    results["R11"] = (~df["payment_mode"].isin(
        ["MISSING", "UNMAPPED"])).values

    fail_rules = [r["rule_id"] for r in RULES if r["severity"] == "FAIL"]
    warn_rules = [r["rule_id"] for r in RULES if r["severity"] == "WARNING"]

    df["validation_status"] = "PASS"
    df.loc[~results[fail_rules].all(axis=1), "validation_status"] = "FAIL"
    df.loc[(results[fail_rules].all(axis=1))
           & (~results[warn_rules].all(axis=1)), "validation_status"] = "WARNING"

    trusted = df[df["validation_status"] == "PASS"].drop(
        columns=["validation_status"])
    rejected = df[df["validation_status"] == "FAIL"].drop(
        columns=["validation_status"])
    warning = df[df["validation_status"] == "WARNING"].drop(
        columns=["validation_status"])

    from .lineage import ensure_lineage
    trusted = ensure_lineage(trusted)
    rejected = ensure_lineage(rejected)
    warning = ensure_lineage(warning)

    failure_rows = []
    for idx, row in df.iterrows():
        for rule in RULES:
            if not results.loc[idx, rule["rule_id"]]:
                failure_rows.append({
                    "order_id": row["order_id"]
                    if "order_id" in df.columns else idx,
                    "rule_id": rule["rule_id"],
                    "rule_name": rule["name"],
                    "severity": rule["severity"],
                    "description": rule["description"],
                })
    rule_failure_log = pd.DataFrame(failure_rows)

    validation_dm = results.copy()
    validation_dm.insert(0, "order_id",
                         df["order_id"] if "order_id" in df.columns else df.index)
    validation_dm["validation_status"] = df["validation_status"].values

    return {
        "trusted_orders": trusted,
        "rejected_orders": rejected,
        "warning_orders": warning,
        "rule_failure_log": rule_failure_log,
        "validation_datamart": validation_dm,
    }


def evaluate(orders, customers, products, status_std, payment_std,
             today="2026-10-11", price_tol=0.30):
    """Legacy entry point. Returns (verdict_df, fail_mask, line_values)."""
    res = validate_orders(orders, customers, products, {}, {}, {}, {},
                          today=today)
    verdict_df = res["validation_datamart"].drop(
        columns=["order_id", "validation_status"], errors="ignore")
    order_ids = orders["order_id"] if "order_id" in orders.columns \
        else orders.index
    status_by_id = res["validation_datamart"].set_index("order_id")[
        "validation_status"] \
        if "order_id" in res["validation_datamart"].columns else None
    fail_mask = pd.Series(
        [(status_by_id.loc[oid] == "FAIL") if status_by_id is not None
         else True for oid in order_ids], index=orders.index)

    def _lv(row):
        return row_line_value(row)

    line_values = pd.Series([_lv(r) for _, r in orders.iterrows()],
                            index=orders.index)
    return verdict_df, fail_mask, line_values


class RuleResult(str, enum.Enum):
    """Possible outcome of one rule on one order line."""

    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


@dataclass(frozen=True)
class Rule:
    """Frozen rule definition. Bodies live in evaluate_rule (stubs for now)."""

    rule_id: str
    name: str
    predicate_text: str
    fields_used: tuple
    files_joined: tuple
    severity: str  # FAIL | WARNING
    treatment: str  # set_aside | flag | correct
    rationale: str

    def __post_init__(self):
        if self.severity not in ("FAIL", "WARNING"):
            raise ValueError(f"bad severity: {self.severity}")
        if self.treatment not in ("set_aside", "flag", "correct"):
            raise ValueError(f"bad treatment: {self.treatment}")


@dataclass(frozen=True, eq=False)
class Context:
    """Everything a rule may read. Rules never read files themselves."""

    customers: pd.DataFrame
    products: pd.DataFrame
    city_map: dict
    cat_map: dict
    pay_map: dict
    status_map: dict
    today: str = "2026-10-11"


RULE_DEFINITIONS = [
    Rule("R01", "Customer Exists",
         "customer_id exists in the customer master",
         ("customer_id",), ("orders", "customers"),
         "FAIL", "set_aside",
         "Unmatched customer ids cannot attribute value to anyone."),
    Rule("R02", "Product Exists",
         "product_id exists in the product master",
         ("product_id",), ("orders", "products"),
         "FAIL", "set_aside",
         "Unmatched product ids cannot attribute value to anything."),
    Rule("R03", "Customer Signup Before Order",
         "customer signup_date <= order_date",
         ("customer_id", "signup_date", "order_date"),
         ("orders", "customers"),
         "FAIL", "set_aside",
         "Orders before signup imply a wrong date on one side. Rows whose "
         "customer is unmatched are NOT evaluated here: they return PASS "
         "with failing_detail='skipped_due_to_R01' (NOT_EVALUATED is "
         "forbidden) and are counted. Duplicate customer rows resolve to "
         "the Sprint 2 D03 survivor (earliest signup). Same-day orders pass."),
    Rule("R04", "Valid Order Date",
         "order_date is parseable and not after TODAY",
         ("order_date",), ("orders",),
         "FAIL", "set_aside",
         "Future dates are typing errors, scheduled orders or wrong years. "
         "Upper bound is TODAY (2026-10-11, inclusive); lower bound is the "
         "earliest signup_date in the customer master (no order predates "
         "the business's first signup), inclusive, derived per input."),
    Rule("R05", "Valid Quantity",
         "quantity is a positive whole number",
         ("quantity",), ("orders",),
         "FAIL", "set_aside",
         "Zero, negative or fractional quantities cannot ship. Bad values "
         "are classified separately (word/decimal/empty/zero/negative) via "
         "the raw_quantity mirror. Implausible highs use an IQR fence "
         "(Q3 + 3*IQR, computed on the input; value equal to the fence "
         "passes); the 99th percentile was rejected as it collapses onto "
         "the pathological 500-spike and flags nothing."),
    Rule("R06", "Valid Price",
         "unit_price_paid is positive and near the catalogue price",
         ("product_id", "unit_price_paid", "discount"), ("orders", "products"),
         "FAIL", "set_aside",
         "Net paid (price*(1-discount)) must be within 10% of catalogue "
         "(R06_PRICE_TOLERANCE; 5% run rejected: inside discount-rounding "
         "and catalogue-staleness noise yet still nukes the headline). No "
         "catalogue price means UNVERIFIABLE, hence WARNING, not FAIL."),
    Rule("R07", "Valid Discount",
         "discount parses to a fraction in 0..1",
         ("discount",), ("orders",),
         "WARNING", "flag",
         "Fraction-vs-percent rule finalised here: (0,1] fractions (bare 1 "
         "counts separately), (1,100] percentages, else FAIL. Severity stays "
         "WARNING (treatment flag-for-correction); only truly unusable "
         "discounts FAIL the check outcome."),    Rule("R08", "Valid Status",
         "order_status is not MISSING or UNMAPPED",
         ("order_status",), ("orders",),
         "FAIL", "set_aside",
         "Unknown status cannot decide revenue membership."),
    Rule("R09", "Valid Payment",
         "payment_mode passes the mapping gate",
         ("payment_mode",), ("orders",),
         "WARNING", "flag",
         "Unknown payment does not invalidate the order event (customer, "
         "product, date and value stay verifiable); it only limits "
         "payment-behaviour answers, so WARNING not FAIL. FAIL alternative "
         "would set aside every UNMAPPED/MISSING-payment row from Q4."),
    Rule("R10", "Valid Delivery Days",
         "delivery_days is an integer in 0..30 for Delivered",
         ("order_status", "delivery_days"), ("orders",),
         "WARNING", "flag",
         "Upper bound 30: brief-stated and data-consistent (genuine values "
         "all <= 7; only the planted 45-spike exceeds it). Cancelled rows "
         "with positive days are WARNING (suspicious metadata, but the "
         "cancellation itself stands)."),
    Rule("R11", "Inventory Feasibility",
         "quantity does not exceed recorded stock_qty",
         ("product_id", "quantity"), ("orders", "products"),
         "WARNING", "flag",
         "Stock is a point-in-time snapshot that cannot be time-aligned to "
         "order dates, so it can never hard-gate: WARNING only. Products "
         "with unusable stock are skipped with a count, not failed."),
    Rule("R12", "Cross-field Business Rule",
         "delivered/cancelled/signup invariants hold together",
         ("order_status", "order_date", "delivery_days", "signup_date",
          "customer_id"),
         ("orders", "customers"),
         "FAIL", "set_aside",
         "Sub-conditions R12a (delivered not future), R12b (delivered has "
         "days), R12c (cancelled has no positive days), R12d (signup not "
         "after TODAY), each counted. R12c-only violations stay WARNING "
         "for consistency with R10-cancelled."),
]


def build_registry(rules):
    """Index rules by rule_id, rejecting duplicates."""
    registry = {}
    for rule in rules:
        if rule.rule_id in registry:
            raise ValueError(f"duplicate rule_id: {rule.rule_id}")
        registry[rule.rule_id] = rule
    return registry


REGISTRY = build_registry(RULE_DEFINITIONS)


def evaluate_rule(rule, orders_df, ctx):
    """Dispatch to the rule body. Returned Series is indexed like the input.

    Unknown rule ids fall back to a PASS stub (defensive; the registry
    covers R01-R12, all implemented).
    """
    impl = _IMPLS.get(rule.rule_id)
    if impl is None:
        return pd.Series([RuleResult.PASS.value] * len(orders_df),
                         index=orders_df.index)
    return impl(orders_df, ctx)["result"]


def evaluate_all(orders_df, ctx, rules=None):
    """Long-format results, one row per (order line, rule), sorted.

    Columns: source_row_number, rule_id, result, failing_detail.
    source_row_number comes from _source_row when present, else 1-based
    position, so shuffling input rows cannot change the output.
    """
    if rules is None:
        rules = RULE_DEFINITIONS
    if "_source_row" in orders_df.columns:
        src_rows = orders_df["_source_row"]
    else:
        src_rows = pd.Series(range(1, len(orders_df) + 1),
                             index=orders_df.index)
    rows = []
    for rule in rules:
        impl = _IMPLS.get(rule.rule_id)
        if impl is None:
            verdicts = evaluate_rule(rule, orders_df, ctx)
            details = pd.Series([""] * len(orders_df), index=orders_df.index)
        else:
            frame = impl(orders_df, ctx)
            verdicts, details = frame["result"], frame["failing_detail"]
        for idx in orders_df.index:
            rows.append({
                "source_row_number": src_rows.loc[idx],
                "rule_id": rule.rule_id,
                "result": verdicts.loc[idx],
                "failing_detail": details.loc[idx],
            })
    out = pd.DataFrame(rows, columns=["source_row_number", "rule_id",
                                      "result", "failing_detail"])
    return out.sort_values(
        ["source_row_number", "rule_id"]).reset_index(drop=True)


R06_PRICE_TOLERANCE = 0.10


def _result_frame(passed, details, index):
    return pd.DataFrame({"result": pd.Series(list(passed), index=index),
                         "failing_detail": pd.Series(list(details),
                                                     index=index)})


def _master_sets(customers, column):
    """Exact values and normalised map, excluding empty identifiers."""
    vals = customers[column].astype(str).str.strip() \
        if column in customers.columns else pd.Series([], dtype=object)
    exact = {v for v in vals if v != ""}
    norm_map = {}
    for v in exact:
        norm_map.setdefault(norm_id(v), v)
    return exact, norm_map


def _r01_customer_exists(orders_df, ctx):
    """R01: FAIL iff unmatched after norm_id normalisation.

    Exact rule (documented): trim, UPPER case, remove spaces and dashes.
    Details distinguish matched_exact / matched_normalised /
    unmatched_after_normalisation so both counts and rescued rows are
    directly countable.
    """
    exact, norm_map = _master_sets(ctx.customers, "customer_id")
    observed = orders_df["customer_id"].astype(str).str.strip()
    results, details = [], []
    for v in observed:
        if v in exact:
            results.append(RuleResult.PASS.value)
            details.append("matched_exact")
        elif norm_id(v) in norm_map:
            results.append(RuleResult.PASS.value)
            details.append("matched_normalised")
        else:
            results.append(RuleResult.FAIL.value)
            details.append("unmatched_after_normalisation")
    return _result_frame(results, details, orders_df.index)


def _r02_product_exists(orders_df, ctx):
    """R02: same two-count design as R01, over product_id."""
    exact, norm_map = _master_sets(ctx.products, "product_id")
    observed = orders_df["product_id"].astype(str).str.strip()
    results, details = [], []
    for v in observed:
        if v in exact:
            results.append(RuleResult.PASS.value)
            details.append("matched_exact")
        elif norm_id(v) in norm_map:
            results.append(RuleResult.PASS.value)
            details.append("matched_normalised")
        else:
            results.append(RuleResult.FAIL.value)
            details.append("unmatched_after_normalisation")
    return _result_frame(results, details, orders_df.index)


def _signup_lookup(customers):
    """Map stripped customer_id -> signup text of the D03 survivor.

    Mirrors the Sprint 2 customer-dedup choice: earliest parseable
    signup_date wins; unparseable sorts last; ties keep first row
    (mergesort for determinism). Returns (exact, normalised) maps so
    R01-rescued spellings evaluate against the same record instead of
    being skipped.
    """
    if "customer_id" not in customers.columns or len(customers) == 0:
        return {}, {}
    tmp = customers.copy()
    tmp["_cid"] = tmp["customer_id"].astype(str).str.strip()
    tmp = tmp[tmp["_cid"] != ""]
    tmp["_skey"] = tmp["signup_date"].astype(str).str.strip() \
        if "signup_date" in tmp.columns else ""
    tmp["_skey"] = tmp["_skey"].apply(
        lambda v: _as_date(v) or "~")
    tmp = tmp.sort_values(["_cid", "_skey"], kind="mergesort")
    first = tmp.drop_duplicates("_cid")
    exact = dict(zip(first["_cid"], first["signup_date"].astype(str)))
    normed = {}
    for cid, signup in exact.items():
        normed.setdefault(norm_id(cid), signup)
    return exact, normed


def _r03_signup_before_order(orders_df, ctx):
    """R03: order_date >= signup_date (same day passes).

    Unmatched customers are NOT evaluated: PASS with
    failing_detail='skipped_due_to_R01' (NOT_EVALUATED is forbidden).
    Unparseable dates FAIL (the predicate cannot hold).
    """
    signup, signup_norm = _signup_lookup(ctx.customers)
    results, details = [], []
    for _, row in orders_df.iterrows():
        cid = str(row["customer_id"]).strip()
        start_text = signup.get(cid, signup_norm.get(norm_id(cid)))
        if start_text is None:
            results.append(RuleResult.PASS.value)
            details.append("skipped_due_to_R01")
            continue
        order = _as_date(row["order_date"])
        start = _as_date(start_text)
        if order is None:
            results.append(RuleResult.FAIL.value)
            details.append("unparseable_order_date")
        elif start is None:
            results.append(RuleResult.FAIL.value)
            details.append("unparseable_signup_date")
        elif start <= order:
            results.append(RuleResult.PASS.value)
            details.append("signup_ok")
        else:
            results.append(RuleResult.FAIL.value)
            details.append("order_before_signup")
    return _result_frame(results, details, orders_df.index)


def _r04_lower_bound(ctx):
    """Earliest signup_date in the customer master, or None.

    No order can predate the business's first recorded signup; derived
    per input so it stays data-driven on any extract.
    """
    if "signup_date" not in ctx.customers.columns:
        return None
    sds = pd.to_datetime(ctx.customers["signup_date"].astype(str).str.strip(),
                         errors="coerce").dropna()
    if len(sds) == 0:
        return None
    return sds.min().date().isoformat()


def _r04_valid_order_date(orders_df, ctx):
    """R04: parseable, <= TODAY (inclusive), >= signup-min bound (inclusive)."""
    lower = _r04_lower_bound(ctx)
    results, details = [], []
    for v in orders_df["order_date"].astype(str):
        day = _as_date(v)
        if day is None:
            results.append(RuleResult.FAIL.value)
            details.append("unparseable_order_date")
        elif day > ctx.today:
            results.append(RuleResult.FAIL.value)
            details.append("after_today")
        elif lower is not None and day < lower:
            results.append(RuleResult.FAIL.value)
            details.append("before_lower_bound")
        else:
            results.append(RuleResult.PASS.value)
            details.append("ok")
    return _result_frame(results, details, orders_df.index)


def _r05_fence(quantities):
    """IQR fence Q3 + 3*IQR over numeric quantities, or None if empty."""
    q = pd.to_numeric(quantities.astype(str).str.strip(),
                      errors="coerce").dropna()
    if len(q) == 0:
        return None
    q1, q3 = q.quantile(0.25), q.quantile(0.75)
    return float(q3 + 3 * (q3 - q1))


def _classify_bad_quantity(raw_text):
    """Separate invalid quantities using the raw mirror when available."""
    s = str(raw_text).strip()
    if s == "":
        return "invalid:empty"
    if re.search(r"[A-Za-z]", s):
        return "invalid:word"
    return "invalid:decimal_or_malformed"


def _r05_valid_quantity(orders_df, ctx):
    """R05: whole positive integer within the IQR fence (fence value passes).

    Bad values are classified separately (word/decimal/empty via the
    raw_quantity mirror when present, else invalid:empty; zero; negative).
    """
    _ = ctx
    fence = _r05_fence(orders_df["quantity"])
    has_raw = "raw_quantity" in orders_df.columns
    results, details = [], []
    for idx, row in orders_df.iterrows():
        q = parse_int(str(row["quantity"]))
        if q is None:
            results.append(RuleResult.FAIL.value)
            raw = row["raw_quantity"] if has_raw else row["quantity"]
            details.append(_classify_bad_quantity(raw))
        elif q == 0:
            results.append(RuleResult.FAIL.value)
            details.append("not_positive:zero")
        elif q < 0:
            results.append(RuleResult.FAIL.value)
            details.append("not_positive:negative")
        elif fence is not None and q > fence:
            results.append(RuleResult.FAIL.value)
            details.append(f"implausible:above_fence_{fence:g}")
        else:
            results.append(RuleResult.PASS.value)
            details.append("ok")
    return _result_frame(results, details, orders_df.index)


def _catalogue_prices(products):
    """Map stripped product_id -> catalogue price for usable prices only."""
    if "product_id" not in products.columns or \
            "unit_price" not in products.columns:
        return {}
    out = {}
    for _, row in products.iterrows():
        pid = str(row["product_id"]).strip()
        if pid == "":
            continue
        price = parse_float(str(row["unit_price"]))
        if price is not None and price > 0:
            out[pid] = price
    return out


def _r06_valid_price(orders_df, ctx, tol=R06_PRICE_TOLERANCE):
    """R06: positive price within tolerance of catalogue net price.

    Tolerance is R06_PRICE_TOLERANCE (10%, recommended; boundary inclusive
    within float epsilon). No usable catalogue price -> WARNING
    (unverifiable), never FAIL.
    """
    cat = _catalogue_prices(ctx.products)
    results, details = [], []
    for _, row in orders_df.iterrows():
        price = parse_float(str(row["unit_price_paid"]))
        if price is None or price <= 0:
            results.append(RuleResult.FAIL.value)
            details.append("non_positive_price")
            continue
        pid = str(row["product_id"]).strip()
        if pid not in cat:
            results.append(RuleResult.WARNING.value)
            details.append("unverifiable:no_catalogue_price")
            continue
        disc = parse_discount_frac(str(row["discount"])) \
            if str(row["discount"]).strip() != "" else 0.0
        if disc is None:
            disc = 0.0
        rel = abs(line_value(1, price, disc) - cat[pid]) / cat[pid]
        if rel <= tol + 1e-9:
            results.append(RuleResult.PASS.value)
            details.append("within_tolerance")
        else:
            results.append(RuleResult.FAIL.value)
            details.append("outside_tolerance")
    return _result_frame(results, details, orders_df.index)


def _r07_classify(text):
    """Classify one raw discount text under the fraction-vs-percent rule.

    Returns (detail, fraction_or_None, passed). Bare 1 is a fraction
    (1.0 = free) counted separately; 0 means no discount; empty means no
    claim. Anything else FAILs.
    """
    s = str(text).strip()
    if s == "":
        return "no_discount_claimed", 0.0, True
    t = s.replace("percent", "").replace("%", "").strip()
    try:
        n = float(t.replace(",", ""))
    except ValueError:
        return "invalid:unparseable", None, False
    if n == 0:
        return "fraction:zero", 0.0, True
    if 0 < n <= 1:
        if n == 1:
            return "fraction:bare_one", 1.0, True
        return "fraction", n, True
    if 1 < n <= 100:
        return "percentage", n / 100.0, True
    return "invalid:out_of_range", None, False


def _r07_valid_discount(orders_df, ctx):
    """R07: resolve percentage vs fraction on the raw mirror when present."""
    _ = ctx
    col = "raw_discount" if "raw_discount" in orders_df.columns \
        else "discount"
    results, details = [], []
    for v in orders_df[col].astype(str):
        detail, _frac, passed = _r07_classify(v)
        results.append(RuleResult.PASS.value if passed
                       else RuleResult.FAIL.value)
        details.append(detail)
    return _result_frame(results, details, orders_df.index)


def _gate_standard(mapping, value, name):
    """Standardise one value through the gate; unseen -> UNMAPPED marker."""
    try:
        return apply_mapping_with(pd.Series([value]), mapping, name).iloc[0]
    except MappingGateError:
        return "UNMAPPED"


def _is_unmapped(standard):
    return standard == "UNMAPPED" or standard.startswith("UNMAPPED_")


def _r08_valid_status(orders_df, ctx):
    """R08: status passes the mapping gate; MISSING/UNMAPPED FAIL visibly."""
    _ = ctx
    mapping = load_mapping("status")
    col = "raw_order_status" if "raw_order_status" in orders_df.columns \
        else "order_status"
    results, details = [], []
    for v in orders_df[col].astype(str):
        std = _gate_standard(mapping, v, "status")
        if std == "MISSING":
            results.append(RuleResult.FAIL.value)
            details.append("missing_status")
        elif _is_unmapped(std):
            results.append(RuleResult.FAIL.value)
            details.append("unmapped_status")
        else:
            results.append(RuleResult.PASS.value)
            details.append("ok")
    return _result_frame(results, details, orders_df.index)


def _r09_valid_payment(orders_df, ctx):
    """R09: payment passes the mapping gate; unknowns are WARNING (flag).

    Decision: an unknown payment method does not invalidate the order
    event itself, so rows stay; only payment-behaviour answers lose them.
    """
    _ = ctx
    mapping = load_mapping("payment")
    col = "raw_payment_mode" if "raw_payment_mode" in orders_df.columns \
        else "payment_mode"
    results, details = [], []
    for v in orders_df[col].astype(str):
        std = _gate_standard(mapping, v, "payment")
        if std == "MISSING":
            results.append(RuleResult.WARNING.value)
            details.append("missing_payment")
        elif _is_unmapped(std):
            results.append(RuleResult.WARNING.value)
            details.append("unmapped_payment")
        else:
            results.append(RuleResult.PASS.value)
            details.append("ok")
    return _result_frame(results, details, orders_df.index)


R10_DELIVERY_UPPER = 30


def _r10_valid_delivery_days(orders_df, ctx):
    """R10: status-aware delivery plausibility (upper bound 30)."""
    _ = ctx
    results, details = [], []
    for _, row in orders_df.iterrows():
        status = str(row["order_status"]).strip()
        text = str(row["delivery_days"]).strip()
        if status == "Delivered":
            if text == "":
                results.append(RuleResult.FAIL.value)
                details.append("missing_delivery_days")
                continue
            days = parse_int(text)
            if days is None:
                results.append(RuleResult.FAIL.value)
                details.append("non_integer_delivery_days")
            elif days < 0:
                results.append(RuleResult.FAIL.value)
                details.append("negative_delivery_days")
            elif days > R10_DELIVERY_UPPER:
                results.append(RuleResult.FAIL.value)
                details.append(f"above_upper_bound_{R10_DELIVERY_UPPER}")
            else:
                results.append(RuleResult.PASS.value)
                details.append("ok")
        elif status == "Cancelled":
            if text == "":
                results.append(RuleResult.PASS.value)
                details.append("ok")
                continue
            days = parse_int(text)
            if days is None:
                results.append(RuleResult.WARNING.value)
                details.append("unparseable_delivery_days")
            elif days != 0:
                results.append(RuleResult.WARNING.value)
                details.append("cancelled_with_delivery_days")
            else:
                results.append(RuleResult.PASS.value)
                details.append("ok")
        else:
            results.append(RuleResult.PASS.value)
            details.append("no_delivery_rule_for_status")
    return _result_frame(results, details, orders_df.index)


def _stock_map(products):
    """Map stripped product_id -> usable stock, skipping unusable stock."""
    if "product_id" not in products.columns or \
            "stock_qty" not in products.columns:
        return {}
    out = {}
    for _, row in products.iterrows():
        pid = str(row["product_id"]).strip()
        if pid == "":
            continue
        stock = parse_float(str(row["stock_qty"]))
        if stock is not None and stock >= 0:
            out[pid] = stock
    return out


def _r11_inventory_feasibility(orders_df, ctx):
    """R11: quantity vs recorded stock; WARNING only, never FAIL.

    Stock is a point-in-time snapshot that cannot be time-aligned to
    order dates, so it cannot hard-gate. Unusable stock (missing, text,
    negative) and unparseable quantities are skipped with counts, not
    failed (R05 owns quantity validity).
    """
    stock = _stock_map(ctx.products)
    results, details = [], []
    for _, row in orders_df.iterrows():
        pid = str(row["product_id"]).strip()
        if pid not in stock:
            results.append(RuleResult.PASS.value)
            details.append("skipped_unusable_stock")
            continue
        qty = parse_int(str(row["quantity"]))
        if qty is None:
            results.append(RuleResult.PASS.value)
            details.append("skipped_unparseable_quantity")
            continue
        if qty > stock[pid]:
            results.append(RuleResult.WARNING.value)
            details.append("insufficient_stock")
        else:
            results.append(RuleResult.PASS.value)
            details.append("ok")
    return _result_frame(results, details, orders_df.index)


def _r12_cross_field(orders_df, ctx):
    """R12: cross-field invariants; FAIL, except R12c-only stays WARNING.

    Sub-conditions (each counted): R12a delivered not future-dated; R12b
    delivered has delivery_days; R12c cancelled has no positive days;
    R12d signup not after TODAY. Unparseable dates and unmatched
    customers contribute no tag (owned by R01/R03/R04).
    """
    signup_exact, signup_norm = _signup_lookup(ctx.customers)
    results, details = [], []
    for _, row in orders_df.iterrows():
        tags = []
        status = str(row["order_status"]).strip()
        order_day = _as_date(row["order_date"])
        days_text = str(row["delivery_days"]).strip()
        if status == "Delivered":
            if order_day is not None and order_day > ctx.today:
                tags.append("R12a:future_delivered_date")
            if days_text == "":
                tags.append("R12b:delivered_missing_days")
        if status == "Cancelled" and days_text != "":
            days = parse_int(days_text)
            if days is not None and days > 0:
                tags.append("R12c:cancelled_positive_days")
        cid = str(row["customer_id"]).strip()
        start_text = signup_exact.get(cid, signup_norm.get(norm_id(cid)))
        if start_text is not None:
            start = _as_date(start_text)
            if start is not None and start > ctx.today:
                tags.append("R12d:signup_after_today")
        if not tags:
            results.append(RuleResult.PASS.value)
            details.append("ok")
        elif tags == ["R12c:cancelled_positive_days"]:
            results.append(RuleResult.WARNING.value)
            details.append(";".join(tags))
        else:
            results.append(RuleResult.FAIL.value)
            details.append(";".join(tags))
    return _result_frame(results, details, orders_df.index)


_IMPLS = {
    "R01": _r01_customer_exists,
    "R02": _r02_product_exists,
    "R03": _r03_signup_before_order,
    "R04": _r04_valid_order_date,
    "R05": _r05_valid_quantity,
    "R06": _r06_valid_price,
    "R07": _r07_valid_discount,
    "R08": _r08_valid_status,
    "R09": _r09_valid_payment,
    "R10": _r10_valid_delivery_days,
    "R11": _r11_inventory_feasibility,
    "R12": _r12_cross_field,
}
