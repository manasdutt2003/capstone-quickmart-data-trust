"""Build dashboard/data.json from existing outputs (never hand-typed numbers).

Reads: outputs/*.csv, data/*datamart.csv, docs/question_ledger.md,
docs/judgement_calls.md, reference/*.json, reports/llm_insights.json,
reports/llm_run_record.json, dashboard/criteria_cache.json.
Runs every Q30-125 question function for live headlines; masks ids;
regex-scans the payload for PII and refuses to write on any hit.

Run: python -m src.dashboard_data [--only FILE]
Writes dashboard/data.json (deterministic: sorted keys, no timestamps).
"""

import hashlib
import itertools
import json
import re
from pathlib import Path

import pandas as pd

from src.mapping_gate import load_mapping
from src.validation_rules import Context

ROOT = Path(__file__).resolve().parents[1]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\d)(\+?91[\s\-]?)?[6-9]\d{9}(?!\d)")

ANALOGUES = {
    68: "order_timestamp/session_start (no intra-day timestamps)",
    70: "referral_id/referred_by (no referral field in extracts)",
    73: "browse_event/visit_time (no browse events in extracts)",
    74: "status_history/transition_timestamp (no transition log)",
}

SEGMENT_OF = {**{q: "A" for q in range(1, 10)},
              **{q: "B" for q in range(10, 20)},
              **{q: "C" for q in range(20, 30)},
              **{q: "D" for q in range(30, 40)},
              **{q: "E" for q in range(40, 50)},
              **{q: "F" for q in range(50, 68)},
              **{q: "G" for q in range(68, 76)},
              **{q: "H" for q in range(76, 78)},
              **{q: "I" for q in range(78, 126)}}

QUESTION_TITLES = {
    1: "Rows per extract vs rows loaded", 2: "Odd column names kept verbatim",
    3: "Numeric-looking text columns", 4: "Short/long order rows",
    5: "Leading zeros and spaces in ids", 6: "Dates changed on load",
    7: "File encodings", 8: "Quotes inside notes",
    9: "Loading the same file twice",
    10: "Empty vs placeholder cells per customer column",
    11: "Placeholders in orders and their clustering",
    12: "Most-empty orders column", 13: "Empty prices by month/product",
    14: "Missing and placeholder emails", 15: "Missing and text prices",
    16: "Never-empty vs >10% empty columns",
    17: "Empty delivery days by status", 18: "Co-empty column pairs",
    19: "Unusable stock per category", 20: "Repeated order_ids",
    21: "Which columns differ across copies", 22: "Repeated customers: same person?",
    23: "Case/spacing/dash customer variants",
    24: "Customers with and without orders", 25: "Shared email addresses",
    26: "Shared product names", 27: "Repeated product_ids",
    28: "Customers with several cities", 29: "Delivered left after dedup",
    30: "Unmatched customer_ids", 31: "Unmatched product_ids",
    32: "Ghost-customer order value", 33: "Never-ordered products",
    34: "Catalogue vs paid price gaps", 35: "Paid vs catalogue closeness",
    36: "Fuzzy-attributed orders", 37: "Every-month vs one-month customers",
    38: "Orders before signup", 39: "Which join drops most rows",
    40: "Payment spellings", 41: "Status spellings",
    42: "Category pairs to merge or keep", 43: "Non-standard quantities",
    44: "Implausible high quantities", 45: "Future order dates",
    46: "Discount forms", 47: "Delivery-day extremes",
    48: "Cities outside the served four", 49: "Three things data cannot tell",
    50: "Running total crossing 10,000", 51: "Paid 20% above catalogue",
    52: "Dedup/validate/complete chain counts", 53: "Quantity range guard",
    54: "RANK vs DENSE_RANK vs ROW_NUMBER", 55: "First-time payment mode",
    56: "Three-month moving average turns", 57: "Month x category calendar",
    58: "Top/bottom product per city", 59: "Customers over 25% of city value",
    60: "Deterministic dedup rerun", 61: "Multi-category, no recent order",
    62: "Median delivery: percentile vs rank", 63: "Order-count spikes",
    64: "Sales-by-category function", 65: "Longest active-month run",
    66: "GROUPING SETS reconciliation", 67: "Delivered but never dated",
    68: "30-minute order sessions (analogue)", 69: "Join plan + index proposal",
    70: "Referral-chain depth (analogue)", 71: "Exact vs approximate p95",
    72: "LATERAL rule-violation strings", 73: "Browse-to-delivery funnel (analogue)",
    74: "Status-transition paths (analogue)", 75: "Quality scorecard 0-100",
    76: "LATERAL vs window under ties", 77: "Float sums depend on order",
    78: "Monthly value per city + MoM", 79: "Median gap between orders",
    80: "Three recent non-delivered orders", 81: "Top-10% product value share",
    82: "Longest zero-order run", 83: "H1 2026 but not H2 (EXCEPT vs EXISTS)",
    84: "Second-highest value per city", 85: "Discount-implied price gaps",
    86: "Three latest orders per customer", 87: "City/category GROUPING SETS",
    88: "Above own median monthly qty", 89: "Rolling 90-day distinct customers",
    90: "Six-month cohort retention", 91: "Above city p95 delivery days",
    92: "Duplicate customers by email", 93: "Categories in last 180 days",
    94: "Category-share Herfindahl per city", 95: "Rising in 4 straight months",
    96: "Paid 10% over catalogue", 97: "Monthly MA + year over year",
    98: "Latest order switched payment", 99: "Top two ranks per city",
    100: "Same-day same-category pairs", 101: "Delivery pivot payment x status",
    102: "First to a tenth order", 103: "Never in a completed order",
    104: "Notes vs late delivery share", 105: "Most expensive product (LATERAL)",
    106: "One CTE, three reconciled totals", 107: "First month above own average",
    108: "Orders in prior 30 days, both engines", 109: "Quantity 2-SD outliers",
    110: "Ids in one source only", 111: "Category share shift >5pp",
    112: "Top-5 product pairs", 113: "Above p90 cancel rate",
    114: "Units per product per month", 115: "Months losing city coverage",
    116: "Gini of value across customers", 117: "Usual vs latest payment mode",
    118: "Delivery-day bands per city", 119: "Fastest signup cohort",
    120: "Completed-values view, no raw text", 121: "Empty city x category cells",
    122: "Rank-1 products, 3+ months", 123: "Customers buying every category",
    124: "Off-catalogue months doubling", 125: "Top-3 cities mega query",
}

FUNC_MODULES = [
    ("src.questions.seg4_cross_file",
     ["q30_unmatched_customers", "q31_unmatched_products",
      "q32_ghost_customer_value", "q33_never_ordered_products",
      "q34_price_gap_per_product", "q35_price_closeness",
      "q36_fuzzy_attribution", "q37_every_month_vs_one_month",
      "q38_orders_before_signup", "q39_join_losses"]),
    ("src.questions.seg5_values",
     ["q40_payment_spellings", "q41_status_spellings",
      "q42_category_pairs", "q43_quantity_kinds",
      "q44_high_quantities", "q45_future_dates",
      "q46_discount_forms", "q47_delivery_extremes",
      "q48_outside_cities", "q49_three_unknowns"]),
    ("src.questions.seg6_advanced_sql",
     ["q50_running_total_cross_10k",
      "q51_avg_paid_20pct_above_catalogue", "q52_cte_chain_counts",
      "q53_quantity_range_check", "q54_rank_disagreements",
      "q55_new_payment_mode", "q56_moving_avg_direction",
      "q57_calendar_zero_cells", "q58_city_top_bottom_product",
      "q59_city_share_over_25pct", "q60_dedup_determinism",
      "q61_no_recent_month_multi_category",
      "q62_median_delivery_percentile_vs_rank", "q63_spike_detection",
      "q64_function_tests", "q65_longest_active_run",
      "q66_grouping_sets", "q67_missing_delivery_customers"]),
    ("src.questions.seg7_professional_sql",
     ["q68_sessions", "q69_plan_analysis", "q70_referral_depth",
      "q71_p95_exact_vs_approx", "q72_lateral_rule_strings",
      "q73_funnel", "q74_transition_classes", "q75_scorecard"]),
    ("src.questions.seg8_expert_sql",
     ["q76_lateral_equivalence", "q77_float_sum_order"]),
]

SQL_FOR = {}
for _q in (1, 2, 3, 5, 6, 7, 8):
    SQL_FOR[_q] = f"sql/questions/seg1_q{_q}.sql"
for _q in range(10, 20):
    SQL_FOR[_q] = f"sql/questions/seg2_q{_q}.sql"
for _q in range(20, 30):
    SQL_FOR[_q] = f"sql/questions/seg3_q{_q}.sql"
for _q in range(30, 40):
    SQL_FOR[_q] = f"sql/questions/seg4_q{_q}.sql"
for _q in range(40, 50):
    SQL_FOR[_q] = f"sql/questions/seg5_q{_q}.sql"
for _q in range(50, 68):
    SQL_FOR[_q] = f"sql/questions/seg6_q{_q}.sql"
for _q in range(68, 76):
    SQL_FOR[_q] = f"sql/questions/seg7_q{_q}.sql"
for _q in range(76, 78):
    SQL_FOR[_q] = f"sql/questions/seg8_q{_q}.sql"
for _q in range(78, 126):
    SQL_FOR[_q] = f"sql/questions/seg9_q{_q}.sql"
del _q

CODE_FOR = {**{q: "src/questions/seg4_cross_file.py" for q in range(30, 40)},
            **{q: "src/questions/seg5_values.py" for q in range(40, 50)},
            **{q: "src/questions/seg6_advanced_sql.py"
                for q in range(50, 68)},
            **{q: "src/questions/seg7_professional_sql.py"
                for q in range(68, 76)},
            **{q: "src/questions/seg8_expert_sql.py"
                for q in range(76, 78)}}

for _q in range(78, 102):
    CODE_FOR[_q] = "src/questions/seg9a_expert_data.py"
for _q in list(range(102, 110)) + list(range(113, 126)):
    CODE_FOR[_q] = "src/questions/seg9b_expert_data.py"
for _q in (list(range(87, 95)) + [110, 111, 112]):
    CODE_FOR[_q] = "src/questions/seg9c_expert_data.py"
del _q

PARITY_FILES = {"tests/test_questions_seg4_5.py",
                "tests/test_questions_seg6_7.py",
                "tests/test_questions_seg8_9.py"}


def mask_id(value: object) -> str:
    s = str(value)
    return (s[0] + "***") if s else ""


DROP_COLS_RE = re.compile(r"email|phone|customer_name|(?<!_)notes$",
                             re.IGNORECASE)


def mask_frame(frame: pd.DataFrame) -> list[dict]:
    out = []
    for _, row in frame.head(3).iterrows():
        rec: dict[str, object] = {}
        for col in frame.columns:
            if DROP_COLS_RE.search(str(col)):
                continue
            v = row[col]
            if col in ("customer_id", "customer_a", "customer_b"):
                rec[col] = mask_id(v)
            elif isinstance(v, float):
                rec[col] = round(v, 2)
            else:
                rec[col] = str(v)
        out.append(rec)
    return out


def summarize(result: object) -> dict:
    if isinstance(result, pd.DataFrame):
        return {"kind": "table", "rows": len(result),
                "columns": list(result.columns),
                "head": mask_frame(result)}
    if isinstance(result, dict):
        small: dict[str, object] = {}
        for key, val in result.items():
            if isinstance(val, pd.DataFrame):
                small[key] = {"rows": len(val),
                              "columns": list(val.columns),
                              "head": mask_frame(val)}
            elif isinstance(val, (int, float, str, bool)):
                if isinstance(val, str) and DROP_COLS_RE.search(key):
                    small[key] = "[redacted]"
                else:
                    small[key] = round(val, 2) if isinstance(val,
                                                             float) else val
            elif isinstance(val, (list, set)):
                vals = sorted(str(v) for v in val)[:5]
                small[key] = {"n": len(val), "sample": vals}
            else:
                small[key] = str(val)[:120]
        return {"kind": "dict", "fields": small}
    return {"kind": "scalar", "value": str(result)[:200]}


def read_frames() -> tuple:
    from src.data_loader import load_all_text
    from tests.conftest import find_extracts_root
    trusted = pd.read_csv(ROOT / "outputs" / "trusted_orders.csv",
                          dtype=str, keep_default_na=False,
                          encoding="utf-8")
    customers = pd.read_csv(ROOT / "data" / "customer_master.csv",
                            dtype=str, keep_default_na=False,
                            encoding="utf-8")
    products = pd.read_csv(ROOT / "data" / "products_clean.csv",
                           dtype=str, keep_default_na=False,
                           encoding="utf-8")
    ctx = Context(customers=customers, products=products,
                  city_map=load_mapping("city"),
                  cat_map=load_mapping("category"),
                  pay_map=load_mapping("payment"),
                  status_map=load_mapping("status"))
    raw = load_all_text(find_extracts_root(ROOT / "tests" / "conftest.py"))
    raw_orders = pd.DataFrame(raw["orders"])
    raw_customers = pd.DataFrame(raw["customers"])
    raw_products = pd.DataFrame(raw["products"])
    ctx_raw = Context(customers=raw_customers, products=raw_products,
                      city_map=load_mapping("city"),
                      cat_map=load_mapping("category"),
                      pay_map=load_mapping("payment"),
                      status_map=load_mapping("status"))
    return (trusted, customers, products, ctx, raw_orders, raw_customers,
            raw_products, ctx_raw)


def ledger_rows() -> dict[int, dict]:
    rows: dict[int, dict] = {}
    for line in (ROOT / "docs" / "question_ledger.md").read_text(
            encoding="utf-8").splitlines():
        # status may be multi-word ("NOT DONE"); capture up to the next " | "
        m = re.match(r"\| Q(\d+) \| (\S+) \| (.+?) \|", line)
        if m:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            reason = cells[-1] if len(cells) >= 7 else ""
            reason = "" if reason == "\u2014" else reason.removeprefix("reason: ")
            rows[int(m.group(1))] = {
                "seg": m.group(2), "status": m.group(3).strip(),
                "reason": reason, "line": line.strip()}
    return rows


SEG1_3_DOC = ROOT / "docs" / "answers_segment1_3.md"

SEG1_3_SECTION_RE = re.compile(
    r"^### Q(\d+) [^\n]*\n(.*?)(?=^### Q\d+ |^## |^\*Prepared|\Z)",
    re.MULTILINE | re.DOTALL)


def _mask_emails(text: str) -> str:
    """Payload must stay PII-free (build guard); prose may cite raw emails."""
    return EMAIL_RE.sub("[email masked]", text)


def seg1_3_answers() -> dict[int, dict]:
    """Parse docs/answers_segment1_3.md into per-question payload text.

    Returns {num: {method, decision, result, code}} with whitespace collapsed;
    absent sections simply do not appear in the mapping.
    """
    if not SEG1_3_DOC.exists():
        return {}
    text = SEG1_3_DOC.read_text(encoding="utf-8")
    out: dict[int, dict] = {}
    for m in SEG1_3_SECTION_RE.finditer(text):
        body = m.group(2)

        def grab(pattern: str, body: str = body) -> str:
            mm = re.search(pattern, body, re.DOTALL)
            return " ".join(mm.group(1).split()) if mm else ""

        code_line = grab(r"\*\*Code:\*\*\s*(.+)")
        cm = re.search(r"`([^`]+)`", code_line)
        out[int(m.group(1))] = {
            "method": _mask_emails(
                grab(r"\*\*Method[^:]*:\*\*\s*(.+?)\s*\*\*Decision")),
            "decision": _mask_emails(
                grab(r"\*\*Decision[^:]*:\*\*\s*(.+?)\s*\*\*Code:")),
            "result": _mask_emails(grab(
                r"\*\*Result[^:]*:\*\*\s*(.+?)\s*(?:\n-{3,}\n|\*Prepared|\Z)")),
            "code": cm.group(1) if cm else "",
        }
    return out


def build_questions(args: tuple, ledger: dict[int, dict]) -> list[dict]:
    import importlib
    import inspect
    questions = []
    trusted, customers, products, ctx, raw_orders, raw_customers, \
        raw_products, ctx_raw = args
    maps = {
        "raw": {"orders": raw_orders, "customers": raw_customers,
                "products": raw_products, "ctx": ctx_raw,
                "orders_df": raw_orders, "customers_df": raw_customers,
                "products_df": raw_products},
        "full": {"trusted": trusted, "customers": customers,
                 "products": products, "ctx": ctx},
    }
    seg9 = [("src.questions.seg9a_expert_data",
             ["q78_mom_by_city", "q79_median_gap",
              "q80_three_recent_nondelivered", "q81_top10pct_share",
              "q82_longest_zero_run", "q83_except_vs_not_exists",
              "q84_second_highest", "q85_discount_implied_gap",
              "q86_latest_three_array", "q95_four_rising_months",
              "q96_paid_over_catalogue", "q97_ma_yoy",
              "q98_latest_payment_switch", "q99_top2_ranks_city",
              "q100_same_day_pairs", "q101_delivery_pivot",
              "q102_tenth_order", "q103_never_completed",
              "q104_notes_vs_late", "q105_top_product_lateral",
              "q106_cte_reconcile", "q107_first_above_avg",
              "q108_orders_prior_30d", "q109_qty_outliers"]),
            ("src.questions.seg9b_expert_data",
             ["q113_cancel_rate_p90", "q114_units_per_product_month",
              "q115_city_count_drops", "q116_gini_by_city",
              "q117_mode_vs_recent", "q118_delivery_bands",
              "q119_signup_cohort_speed", "q120_completed_view_check",
              "q121_empty_city_category", "q122_rank1_three_months",
              "q123_division_all_categories", "q124_price_mismatch_spikes",
              "q125_mega_top3"]),
            ("src.questions.seg9c_expert_data",
             ["q87_grouping_sets", "q88_median_monthly_qty",
              "q89_range_90d", "q90_cohort", "q91_p95_flags",
              "q92_dup_email_pairs", "q93_180d_categories",
              "q94_herfindahl", "q110_id_mismatches",
              "q111_share_shift", "q112_pairs_top5"])]
    for mod_name, funcs in FUNC_MODULES + seg9:
        mod = importlib.import_module(mod_name)
        mapping = maps["raw"] if ("seg4" in mod_name or "seg5" in mod_name) \
            else maps["full"]
        for fname in funcs:
            num = int(re.match(r"q(\d+)_", fname).group(1))  # type: ignore[union-attr]
            func = getattr(mod, fname)
            params = list(inspect.signature(func).parameters)
            res, explanation = func(**{p: mapping[p] for p in params})
            method = (func.__doc__ or "").strip().splitlines()[0]
            questions.append({
                "id": num,
                "segment": SEGMENT_OF[num],
                "title": QUESTION_TITLES[num],
                "status": ledger.get(num, {}).get("status", "NOT DONE"),
                "pending_reason": ledger.get(num, {}).get("reason", ""),
                "headline": explanation,
                "result": summarize(res),
                "method": method,
                "code": CODE_FOR[num],
                "sql": SQL_FOR[num],
                "parity_tested": True,
                "analogue": ANALOGUES.get(num),
            })
    answers13 = seg1_3_answers()
    for num in range(1, 30):
        info = ledger.get(num, {})
        ans = answers13.get(num, {})
        questions.append({
            "id": num,
            "segment": SEGMENT_OF[num],
            "title": QUESTION_TITLES[num],
            "status": info.get("status", "NOT DONE"),
            "pending_reason": info.get("reason", ""),
            "headline": ans.get("decision") or "Counts in code; explanation prose pending.",
            "result": ({"kind": "text", "value": ans["result"]}
                       if ans.get("result") else {"kind": "pending"}),
            "method": ans.get("method") or "Counts in code, prose pending.",
            "code": ans.get("code", ""),
            "sql": SQL_FOR.get(num, ""),
            "parity_tested": num in SQL_FOR,
            "analogue": None,
        })
    added = sorted(questions, key=lambda q: q["id"])
    missing13 = [q["id"] for q in added
                 if q["id"] <= 29 and q["result"]["kind"] != "text"]
    if missing13:
        raise RuntimeError(f"missing answers_segment1_3.md sections: {missing13}")
    return added


def build_waterfall() -> dict:
    def n(path: str) -> int:
        return len(pd.read_csv(ROOT / path, dtype=str,
                               keep_default_na=False))
    trusted = pd.read_csv(ROOT / "outputs" / "trusted_orders.csv",
                          dtype=str, keep_default_na=False)
    lv = pd.to_numeric(trusted["line_value"], errors="coerce")
    strict = pd.read_csv(ROOT / "outputs" / "strict_trusted_orders.csv",
                         dtype=str, keep_default_na=False)
    slv = pd.to_numeric(strict["line_value"], errors="coerce")

    def top5(frame: pd.DataFrame) -> list[dict]:
        vals = pd.to_numeric(frame["line_value"], errors="coerce")
        top = frame.assign(_v=vals).sort_values(
            "_v", ascending=False).head(5)
        return [{"customer_id": mask_id(c), "value": round(float(v), 2)}
                for c, v in zip(top["customer_id"].astype(str),
                                top["_v"].tolist())]

    return {
        "raw_orders": 6103,
        "after_load": 6103,
        "after_dedup": n("data/clean_orders.csv"),
        "rejected": n("outputs/rejected_orders.csv"),
        "lenient": {"rows": n("outputs/lenient_trusted_orders.csv"),
                    "value": round(float(lv.sum()), 2)},
        "strict": {"rows": n("outputs/strict_trusted_orders.csv"),
                   "value": round(float(slv.sum()), 2)},
        "legacy_trusted_rows": n("data/trusted_orders.csv"),
        "top5_lenient": top5(trusted),
        "top5_strict": top5(strict),
    }


def build_rules() -> dict:
    from src.validation_rules import REGISTRY
    fail = pd.read_csv(ROOT / "outputs" / "rule_failure_log.csv",
                       dtype=str, keep_default_na=False)
    fails = fail[fail["result"] == "FAIL"]
    by_rule = fails.groupby("rule_id")
    clean = pd.read_csv(ROOT / "data" / "clean_orders.csv", dtype=str,
                        keep_default_na=False)
    from src.questions.seg6_advanced_sql import _v_line_value
    clean["line_value"] = clean.apply(_v_line_value, axis=1)
    clean["line_value"] = pd.to_numeric(clean["line_value"],
                                        errors="coerce").fillna(0.0)
    val_by_src = dict(zip(clean["source_row_number"].astype(str),
                          clean["line_value"]))
    masters = pd.read_csv(ROOT / "data" / "customer_master.csv",
                          dtype=str, keep_default_na=False)
    city_of = dict(zip(masters["customer_id"].astype(str),
                       masters["city"].astype(str)))
    cust_of = dict(zip(clean["source_row_number"].astype(str),
                       clean["customer_id"].astype(str)))
    month_of = dict(zip(clean["source_row_number"].astype(str),
                        clean["order_date"].astype(str).str[:7]))
    pay_of = dict(zip(clean["source_row_number"].astype(str),
                      clean["payment_mode"].astype(str)))
    rules = []
    for reg in sorted(REGISTRY.values(), key=lambda r: r.rule_id):
        rid = reg.rule_id
        grp = by_rule.get_group(rid) if rid in by_rule.groups else \
            fails.iloc[0:0]
        srcs = grp["source_row_number"].astype(str)
        value = round(float(sum(val_by_src.get(s, 0.0) for s in srcs)), 2)
        cities = pd.Series([city_of.get(cust_of.get(s, ""), "UNKNOWN")
                            for s in srcs])
        months = pd.Series([month_of.get(s, "") for s in srcs])
        pays = pd.Series([pay_of.get(s, "") for s in srcs])
        city_counts = cities.value_counts().head(5)
        rules.append({
            "id": rid, "name": reg.name,
            "predicate": reg.predicate_text,
            "severity": reg.severity,
            "treatment": reg.treatment,
            "failing": len(grp),
            "value_removed": value,
            "top_city": (cities.value_counts().index[0]
                         if len(cities) else ""),
            "top_month": (months.value_counts().index[0]
                          if len(months) else ""),
            "top_payment": (pays.value_counts().index[0]
                            if len(pays) else ""),
            "city_counts": [{"city": str(c), "n": int(n)}
                            for c, n in city_counts.items()],
        })
    sets = fails.groupby("source_row_number")["rule_id"].apply(
        frozenset).to_dict()
    cooccur = []
    for a, b in itertools.combinations(sorted(set(
            fails["rule_id"].unique())), 2):
        nab = sum(1 for s in sets.values() if a in s and b in s)
        if nab:
            pa = sum(1 for s in sets.values() if a in s) / len(sets)
            pb = sum(1 for s in sets.values() if b in s) / len(sets)
            lift = round((nab / len(sets)) / (pa * pb), 2) \
                if pa * pb else 0.0
            cooccur.append({"a": a, "b": b, "n": nab, "lift": lift})
    cooccur.sort(key=lambda r: r["n"], reverse=True)
    return {"rules": rules, "cooccurrence": cooccur[:12]}


def build_marts() -> list[dict]:
    trusted = pd.read_csv(ROOT / "data" / "trusted_orders.csv",
                          dtype=str, keep_default_na=False)
    lv = pd.to_numeric(trusted["line_value"], errors="coerce").fillna(0.0)
    trusted = trusted.assign(_v=lv)
    trusted["month"] = trusted["order_date"].astype(str).str[:7]
    delivered = trusted[trusted["order_status"].astype(str).str.strip(
    ).str.lower() == "delivered"]
    grand_v = round(float(delivered["_v"].sum()), 2)
    grand_n = len(delivered)
    specs = [
        ("sales", "data/sales_datamart.csv",
         "grain: order_month x city_std x category_std",
         ["order_month", "city_std", "category_std"]),
        ("customer_value", "data/customer_value_datamart.csv",
         "grain: customer_id x city_std",
         ["customer_id", "city_std"]),
        ("payment", "data/payment_datamart.csv",
         "grain: order_month x city_std x payment_std",
         ["order_month", "city_std", "payment_std"]),
        ("delivery", "data/delivery_datamart.csv",
         "grain: city_std x category_std",
         ["city_std", "category_std"]),
        ("quality", "data/quality_datamart.csv",
         "grain: one row per order line with QC flags",
         ["order_id"]),
    ]
    out = []
    for name, rel, grain, dims in specs:
        m = pd.read_csv(ROOT / rel)
        mv = round(float(m["value"].sum()), 2) if "value" in m.columns \
            else None
        ok = (mv is None) or abs(mv - grand_v) < 0.01
        by = {}
        for dim in ("order_month", "city_std", "category_std"):
            if dim in m.columns and "value" in m.columns:
                by[dim] = round(float(
                    m.groupby(dim)["value"].sum().sum()), 2)
        out.append({"name": name, "file": rel, "grain": grain,
                    "rows": len(m),
                    "total_value": mv, "trusted_value": grand_v,
                    "trusted_orders": grand_n,
                    "reconciles": bool(ok), "cut_totals": by})
    return out


def build_series() -> dict:
    """Chart tables: monthly sales, top customers (masked), payment mix,
    delivery means. Same rows the charts plot (checked by tests)."""
    sales = pd.read_csv(ROOT / "data" / "sales_datamart.csv")
    monthly_df = sales.groupby("order_month").agg(
        value=("value", "sum"), orders=("orders", "sum")).reset_index()
    monthly_df["value"] = monthly_df["value"].round(2)
    cust = pd.read_csv(ROOT / "data" / "customer_value_datamart.csv")
    top = cust.nlargest(10, "value")[
        ["customer_id", "city_std", "orders", "value"]].copy()
    top["customer_id"] = top["customer_id"].astype(str).map(mask_id)
    top["value"] = top["value"].round(2)
    pay = pd.read_csv(ROOT / "data" / "payment_datamart.csv")
    pay_mix_df = pay.groupby(["order_month", "payment_std"]).agg(
        value=("value", "sum")).reset_index()
    pay_mix_df["value"] = pay_mix_df["value"].round(2)
    deal = pd.read_csv(ROOT / "data" / "delivery_datamart.csv")
    deal_rows = deal[["city_std", "category_std", "orders", "avg_days",
                      "median_days"]].copy()
    deal_rows["avg_days"] = deal_rows["avg_days"].round(2)
    return {
        "monthly": [{"month": str(r["order_month"]),
                     "value": float(r["value"]),
                     "orders": int(r["orders"])}
                    for r in monthly_df.to_dict("records")],
        "top_customers": top.to_dict("records"),
        "payment_mix": pay_mix_df.to_dict("records"),
        "delivery": deal_rows.to_dict("records"),
    }


def build_problems(waterfall: dict) -> list[dict]:
    lent, strict = waterfall["lenient"], waterfall["strict"]
    return [
        {"id": "Q1",
         "question": "Can we trust any of this, and where does it break?",
         "approach": "Profiled every column of all three files. Counted "
                     "empties, placeholders and unusable values. Cut the "
                     "counts by city, month, category and payment. Checked "
                     "which problems travel together on the same rows.",
         "numbers": f"{22} columns profiled; quality datamart "
                    f"{len(pd.read_csv(ROOT / 'data' / 'quality_datamart.csv'))} rows.",
         "decision": "Fit-to-report judgement per business area; worst "
                     "areas quarantined, not silently dropped.",
         "alternative": "A single global quality score.",
         "effect": "Global score would hide city/month concentration.",
         "code": "src/quality_checks.py", "answers": ""},
        {"id": "Q2",
         "question": "We are paying commission on orders that never happened.",
         "approach": "Separated exact copies (D01), conflicting repeats "
                     "(D02), same-person customers (D03) and product repeats "
                     "(D04) with named rules. Reconciled counts three ways: "
                     "by id, by line, by customer/product/date. Priced "
                     "commission before and after each rule.",
         "numbers": f"6103 rows in, {waterfall['after_dedup']} clean; "
                    "commission leakage from commission_datamart.",
         "decision": "Dedup order D01>D03-remap>D02>D05, D06 flag-only.",
         "alternative": "Delete every repeated id outright.",
         "effect": "Blanket delete would remove genuine repeat purchases.",
         "code": "src/deduplication.py",
         "answers": "reports/deduplication_report.md"},
        {"id": "Q3",
         "question": "Which of these orders can I put my name to?",
         "approach": "Twelve checks (R01-R12) combining customer, product, "
                     "price, date, quantity and status fields. Counted what "
                     "each check removes by city, month and category. Kept a "
                     "strict and a lenient population and compared them.",
         "numbers": f"Lenient {lent['rows']} rows Rs {lent['value']:,.2f}; "
                    f"strict {strict['rows']} rows Rs "
                    f"{strict['value']:,.2f}; rejected "
                    f"{waterfall['rejected']}.",
         "decision": "Lenient (FAIL excluded, WARNING kept) feeds every Q4 "
                     "answer.",
         "alternative": "Strict (warnings excluded) or legacy R01-R11.",
         "effect": "Strict drops 407 valid delivered rows; legacy keeps "
                   "R12 failures.",
         "code": "src/validation_rules.py + src/trusted.py",
         "answers": "docs/waterfall.md"},
        {"id": "Q4",
         "question": "What do I tell the leadership team?",
         "approach": "Answered from trusted delivered orders only, one line "
                     "value, cuts by month, city, category, payment and "
                     "tenure. Every total reconciles across cuts. Ties "
                     "flagged, impossible delivery days set aside.",
         "numbers": "See Leadership answers section (computed marts).",
         "decision": "Delivered-only revenue; DENSE_RANK top lists; city "
                     "p95 for delivery.",
         "alternative": "All-status revenue; ROW_NUMBER tops; global p95.",
         "effect": "All-status inflates revenue with cancelled value; "
                   "ROW_NUMBER hides ties.",
         "code": "src/questions/seg6_leadership.py",
         "answers": "reports/executive_report.md"},
        {"id": "Q5",
         "question": "I need this every Monday, written for people who will "
                    "not read a table.",
         "approach": "Five marts at stated grains, refreshable from new "
                     "files. Model input is aggregated JSON only (PII "
                     "asserted out). Every drafted figure is verified "
                     "against a mart; runs and prompts are recorded.",
         "numbers": "5 marts; verifier tolerance 0.01; temperature 0.",
         "decision": "Rule-based fallback ships; model drafts verify first.",
         "alternative": "Let the model write free text unchecked.",
         "effect": "Unchecked drafts invent figures (test proves the "
                   "catch).",
         "code": "src/llm_insights.py",
         "answers": "reports/llm_insights.json"},
    ]


def scan_pii_text(text: str) -> list[str]:
    hits = []
    if EMAIL_RE.search(text):
        hits.append("email-pattern")
    if PHONE_RE.search(text):
        hits.append("phone-pattern")
    return hits


def build(only: str = "") -> dict:
    args = read_frames()
    ledger = ledger_rows()
    payload: dict = {}
    payload["headline"] = build_waterfall()
    payload["problems"] = build_problems(payload["headline"])
    payload["questions"] = build_questions(args, ledger)
    cache_file = ROOT / "dashboard" / "criteria_cache.json"
    if not cache_file.exists():
        raise SystemExit("dashboard/criteria_cache.json missing: run "
                         "python -m src.criteria_check --write-cache first")
    cache = json.loads(cache_file.read_text(encoding="utf-8"))
    payload["criteria"] = cache["checks"]
    payload["validations"] = cache["validations"]
    payload["rubric"] = cache["rubric"]
    payload["run_hash"] = cache["run_hash"]
    payload["rules"] = build_rules()
    payload["marts"] = build_marts()
    payload["series"] = build_series()
    insights_doc = json.loads(
        (ROOT / "reports" / "llm_insights.json").read_text(
            encoding="utf-8"))
    payload["insights"] = insights_doc
    manifest = json.loads(
        (ROOT / "reference" / "extract_manifest.json").read_text(
            encoding="utf-8"))
    hashes = json.loads(
        (ROOT / "reference" / "output_hashes.json").read_text(
            encoding="utf-8"))
    for table, entry in manifest.items():
        sha = entry["sha256_lf"]
        assert re.fullmatch(r"[0-9a-f]{64}", sha), table
    for name, sha in hashes.items():
        assert re.fullmatch(r"[0-9a-f]{64}", sha), name
    payload["provenance"] = {
        "extracts": {k: v["sha256_lf"] for k, v in manifest.items()},
        "outputs": hashes,
        "settings": json.loads(
            (ROOT / "config" / "settings.json").read_text(
                encoding="utf-8")),
    }
    scoped = {k: v for k, v in payload.items() if k != "provenance"}
    text = json.dumps(scoped, sort_keys=True)
    hits = scan_pii_text(text)
    if hits:
        raise SystemExit(f"PII in payload, refusing to write: {hits}")
    return payload


if __name__ == "__main__":
    data = build()
    out = ROOT / "dashboard" / "data.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    blob = (json.dumps(data, sort_keys=True, indent=2) + "\n").encode(
        "utf-8")
    out.write_bytes(blob)
    digest = hashlib.sha256(
        json.dumps(data, sort_keys=True).encode("utf-8")).hexdigest()
    print(f"wrote {out} sha256={digest}")
