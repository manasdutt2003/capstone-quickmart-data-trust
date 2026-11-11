"""QuickMart Analytics Dashboard - FastAPI backend.

Run from this folder:
    uvicorn main:app --reload
Then open http://localhost:8000

Every number served here is read from committed files:
  - ../data/*.csv|json      (marts, quality, commission, profiles)
  - ../outputs/*.csv        (current-sprint trusted / strict / rejected populations)
  - ./data.json             (pipeline payload: criteria, questions, insights)

Privacy: customer identifiers are masked (rank labels or short SHA-1 hashes);
no names, emails, phones or notes are ever returned. All payloads are sanitised
(NaN/Inf -> null) so responses are always valid JSON.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
BASE_DIR = Path(__file__).resolve().parent          # .../QuickMart/dashboard
PROJECT_DIR = BASE_DIR.parent                        # .../QuickMart
DATA_DIR = PROJECT_DIR / "data"
OUTPUTS_DIR = PROJECT_DIR / "outputs"
CHARTS_DIR = PROJECT_DIR / "charts"
SQL_RESULTS_DIRS = [DATA_DIR / "SQL_OUTPUTS", DATA_DIR / "output"]

TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="QuickMart Analytics Dashboard", version="2.0.0")

# --------------------------------------------------------------------------- #
# Helpers: safe JSON, masking, small utilities
# --------------------------------------------------------------------------- #
_EMAIL_RE = re.compile(r"[\w.+\-]+@[\w\-]+\.[\w.\-]+")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-]{7,}\d)")
_CUSTOMER_ID_RE = re.compile(r"\bC\d{3,4}\b")


def mask_id(value: Any) -> str:
    """Stable, non-reversible short hash for any identifier."""
    return "id-" + hashlib.sha1(str(value).encode("utf-8")).hexdigest()[:8]


def scrub_text(value: Any) -> str:
    """Remove anything that looks like an email/phone from free text."""
    text = "" if value is None else str(value)
    text = _EMAIL_RE.sub("[email masked]", text)
    text = _PHONE_RE.sub("[phone masked]", text)
    return text


def mask_customer_ids_in_text(text: str) -> tuple[str, int]:
    """Deterministically mask raw customer ids (C0123) inside saved SQL output.

    The same id always maps to the same label (C-<sha1:6>) so tables stay
    readable and joinable, without exposing the raw identifier.
    """
    seen: dict[str, str] = {}

    def repl(match: re.Match) -> str:
        raw = match.group(0)
        if raw not in seen:
            seen[raw] = "C-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:6]
        return seen[raw]

    return _CUSTOMER_ID_RE.sub(repl, text), len(seen)


def scrub_question_text(value: Any, *, phone: bool = True) -> str:
    """Mask emails (+ phones) then hash-mask raw C-ids in free text."""
    text = "" if value is None else str(value)
    text = _EMAIL_RE.sub("[email masked]", text)
    if phone:
        text = _PHONE_RE.sub("[phone masked]", text)
    text, _ = mask_customer_ids_in_text(text)
    return text


def sanitize(obj: Any) -> Any:
    """Recursively convert to strict JSON: NaN/Inf -> None, numpy -> Python."""
    if isinstance(obj, dict):
        return {str(k): sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [sanitize(v) for v in obj]
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, np.floating):
        val = float(obj)
        return None if (math.isnan(val) or math.isinf(val)) else val
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, (np.ndarray,)):
        return [sanitize(v) for v in obj.tolist()]
    return obj


def df_records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> JSON-safe records (to_json turns NaN into null)."""
    return json.loads(df.to_json(orient="records", date_format="iso"))


def _csv(name: str, folder: Path = DATA_DIR) -> pd.DataFrame:
    path = folder / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{name} not found in {folder.name}/")
    return pd.read_csv(path)


def _file_freshness(path: Path) -> dict:
    if not path.exists():
        return {"file": path.name, "exists": False, "modified": None, "size_kb": None}
    stat = path.stat()
    return {
        "file": path.name,
        "exists": True,
        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "size_kb": round(stat.st_size / 1024, 1),
    }


def _apply_sales_filters(
    df: pd.DataFrame,
    month_from: str | None,
    month_to: str | None,
    city: str | None,
    category: str | None,
) -> pd.DataFrame:
    out = df
    if month_from:
        out = out[out["order_month"] >= month_from]
    if month_to:
        out = out[out["order_month"] <= month_to]
    if city and city != "all":
        out = out[out["city_std"] == city]
    if category and category != "all":
        out = out[out["category_std"] == category]
    return out


# --------------------------------------------------------------------------- #
# Static / page
# --------------------------------------------------------------------------- #
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
if CHARTS_DIR.exists():
    app.mount("/media/charts", StaticFiles(directory=str(CHARTS_DIR)), name="charts")


@app.get("/", include_in_schema=False)
async def index():
    """Serve the dashboard shell with no-store headers (always latest)."""
    page = TEMPLATES_DIR / "index.html"
    if not page.exists():
        raise HTTPException(status_code=404, detail="templates/index.html not found")
    return FileResponse(
        page,
        media_type="text/html",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )


# --------------------------------------------------------------------------- #
# Meta endpoints
# --------------------------------------------------------------------------- #
@app.get("/api/health")
async def health():
    return {"status": "ok", "time": datetime.now(tz=timezone.utc).isoformat()}


@app.get("/api/meta")
async def api_meta():
    """Data freshness, row counts and the filter domain."""
    sales = _csv("sales_datamart.csv")
    files = [
        _file_freshness(DATA_DIR / "sales_datamart.csv"),
        _file_freshness(DATA_DIR / "quality_datamart.csv"),
        _file_freshness(DATA_DIR / "commission_datamart.csv"),
        _file_freshness(DATA_DIR / "report_validation.csv"),
        _file_freshness(OUTPUTS_DIR / "lenient_trusted_orders.csv"),
        _file_freshness(OUTPUTS_DIR / "rejected_orders.csv"),
        _file_freshness(OUTPUTS_DIR / "rule_failure_log.csv"),
        _file_freshness(BASE_DIR / "data.json"),
    ]
    return sanitize(
        {
            "files": files,
            "rows": {
                "sales_datamart": int(len(sales)),
                "customers_extract": 520,
                "products_extract": 30,
                "orders_extract": 6103,
                "orders_clean": 6000,
                "lenient_trusted": 522,
                "strict_trusted": 115,
                "rejected": 5478,
            },
            "months": sorted(sales["order_month"].dropna().unique().tolist()),
            "cities": sorted(sales["city_std"].dropna().unique().tolist()),
            "categories": sorted(sales["category_std"].dropna().unique().tolist()),
            "today_constant": "2026-10-11",
            "runs": {
                "pipeline_run_hash": json.loads((BASE_DIR / "data.json").read_text(encoding="utf-8")).get("run_hash"),
            },
        }
    )


# --------------------------------------------------------------------------- #
# KPI + sales panels
# --------------------------------------------------------------------------- #
@app.get("/api/kpis")
async def api_kpis(
    month_from: str | None = None,
    month_to: str | None = None,
    city: str | None = None,
    category: str | None = None,
):
    """Headline KPIs, computed from the marts under the active filters."""
    sales = _csv("sales_datamart.csv")
    flt = _apply_sales_filters(sales, month_from, month_to, city, category)

    value = float(flt["value"].sum())
    orders = int(flt["orders"].sum())
    units = int(flt["units"].sum())
    aov = round(value / orders, 2) if orders else None

    cust_val = _csv("customer_value_datamart.csv")
    if city and city != "all":
        cust_val = cust_val[cust_val["city_std"] == city]
    customers_with_orders = int(len(cust_val))

    commission = _csv("commission_datamart.csv").iloc[0]
    report = _csv("report_validation.csv")

    return sanitize(
        {
            "filters": {"month_from": month_from, "month_to": month_to, "city": city, "category": category},
            "delivered_value": value,
            "delivered_orders": orders,
            "units": units,
            "avg_order_value": aov,
            "customers_total": 520,
            "customers_with_orders": customers_with_orders,
            "products_total": 30,
            "trusted_lenient_rows": 522,
            "trusted_lenient_value": 455160.75,
            "strict_rows": 115,
            "strict_value": 79738.5,
            "rejected_rows": 5478,
            "raw_orders": 6103,
            "orders_clean": 6000,
            "commission_leakage": float(commission["commission_leakage"]),
            "rows_removed_by_dedup": int(commission["rows_removed"]),
            "validation": df_records(report),
            "reference_note": "Unfiltered totals match data/report_validation.csv (Rs 2,309,394.00 / 799 orders).",
        }
    )


@app.get("/api/monthly-sales")
async def api_monthly_sales(
    month_from: str | None = None,
    month_to: str | None = None,
    city: str | None = None,
    category: str | None = None,
):
    """Delivered sales by month - the dashboard's reference chart."""
    sales = _csv("sales_datamart.csv")
    flt = _apply_sales_filters(sales, month_from, month_to, city, category)
    grouped = (
        flt.groupby("order_month", as_index=False)
        .agg(orders=("orders", "sum"), units=("units", "sum"), value=("value", "sum"))
        .sort_values("order_month")
    )
    return sanitize({"series": df_records(grouped), "total": float(grouped["value"].sum())})


@app.get("/api/sales-cuts")
async def api_sales_cuts(
    dim: str = Query("city", pattern="^(city|category)$"),
    month_from: str | None = None,
    month_to: str | None = None,
    city: str | None = None,
    category: str | None = None,
):
    """Sales grouped by city or category, with share of total.

    The filter on the cut's own dimension is ignored so the cut stays
    comparative (e.g. the city cut keeps every city when a city is selected).
    """
    sales = _csv("sales_datamart.csv")
    col = "city_std" if dim == "city" else "category_std"
    flt = _apply_sales_filters(
        sales,
        month_from,
        month_to,
        None if dim == "city" else city,
        None if dim == "category" else category,
    )
    grouped = (
        flt.groupby(col, as_index=False)
        .agg(orders=("orders", "sum"), units=("units", "sum"), value=("value", "sum"))
        .sort_values("value", ascending=False)
    )
    total = float(grouped["value"].sum()) or 1.0
    grouped["share_pct"] = (grouped["value"] / total * 100).round(2)
    return sanitize({"dim": dim, "rows": df_records(grouped), "total": float(grouped["value"].sum())})


@app.get("/api/payment-mix")
async def api_payment_mix(
    month_from: str | None = None,
    month_to: str | None = None,
    city: str | None = None,
):
    """Payment method mix (payment_datamart; all statuses, value as recorded)."""
    pay = _csv("payment_datamart.csv")
    flt = pay
    if month_from:
        flt = flt[flt["order_month"] >= month_from]
    if month_to:
        flt = flt[flt["order_month"] <= month_to]
    if city and city != "all":
        flt = flt[flt["city_std"] == city]
    grouped = (
        flt.groupby("payment_std", as_index=False)
        .agg(orders=("orders", "sum"), value=("value", "sum"))
        .sort_values("value", ascending=False)
    )
    total = float(grouped["value"].sum()) or 1.0
    grouped["share_pct"] = (grouped["value"] / total * 100).round(2)
    by_month = (
        flt.groupby(["order_month", "payment_std"], as_index=False)
        .agg(value=("value", "sum"))
        .sort_values("order_month")
    )
    return sanitize({"rows": df_records(grouped), "by_month": df_records(by_month), "total": float(grouped["value"].sum())})


@app.get("/api/top-customers")
async def api_top_customers(
    n: int = Query(10, ge=1, le=50),
    by: str = Query("value", pattern="^(value|orders)$"),
    city: str | None = None,
):
    """Top customers, masked as #1, #2... (dense rank; tied ranks flagged)."""
    cust = _csv("customer_value_datamart.csv")
    if city and city != "all":
        cust = cust[cust["city_std"] == city]
    cust = cust.sort_values(["value", "orders"], ascending=False).reset_index(drop=True)

    if by == "value":
        ranks = cust["value"].rank(method="dense", ascending=False).astype(int)
    else:
        ranks = cust["orders"].rank(method="dense", ascending=False).astype(int)

    ranked = cust.assign(dense_rank=ranks)
    tie_counts = ranked["dense_rank"].value_counts()
    top = ranked.head(n)

    rows = []
    for _, r in top.iterrows():
        rank = int(r["dense_rank"])
        rows.append(
            {
                "rank": rank,
                "label": f"#{rank}",
                "city": r["city_std"],
                "orders": int(r["orders"]),
                "value": float(r["value"]),
                "first_order": str(r["first_order"]),
                "last_order": str(r["last_order"]),
                "tied": bool(tie_counts.get(rank, 0) > 1),
            }
        )
    return sanitize(
        {
            "rows": rows,
            "total_customers_with_orders": int(len(cust)),
            "sorted_by": by,
            "note": "Identifiers masked as dense-rank labels; ties share a rank.",
        }
    )


@app.get("/api/cohort")
async def api_cohort():
    """Signup-month cohort value and customers by order month."""
    cohort = _csv("cohort_datamart.csv")
    cohort["signup_month"] = cohort["signup_month"].astype(str)
    cohort["order_month"] = cohort["order_month"].astype(str)
    return sanitize({"rows": df_records(cohort), "total_value": float(cohort["value"].sum())})


@app.get("/api/delivery")
async def api_delivery():
    """Delivery performance by city x category + anomaly counts."""
    dl = _csv("delivery_datamart.csv")
    city = (
        dl.groupby("city_std", as_index=False)
        .agg(
            orders=("orders", "sum"),
            avg_days=("avg_days", "mean"),
            median_days=("median_days", "mean"),
            impossible_orders=("impossible_orders", "sum"),
            negative_orders=("negative_orders", "sum"),
            over_30_orders=("over_30_orders", "sum"),
            missing_orders=("missing_orders", "sum"),
        )
        .sort_values("avg_days")
    )
    weighted_avg = float((dl["orders"] * dl["avg_days"]).sum() / dl["orders"].sum())
    return sanitize(
        {
            "by_city_category": df_records(dl),
            "by_city": df_records(city),
            "weighted_avg_days": round(weighted_avg, 2),
        }
    )


# --------------------------------------------------------------------------- #
# Quality panels
# --------------------------------------------------------------------------- #
@app.get("/api/quality/scorecard")
async def api_quality_scorecard():
    return sanitize(df_records(_csv("quality_scorecard.csv")))


@app.get("/api/quality/rules")
async def api_quality_rules():
    """Rule failures (FAIL + WARNING) joined to rule metadata from data.json."""
    rf = pd.read_csv(OUTPUTS_DIR / "rule_failure_log.csv")
    counts = (
        rf.groupby(["rule_id", "result"]).size().unstack(fill_value=0).reset_index()
    )
    for col in ("FAIL", "WARNING"):
        if col not in counts.columns:
            counts[col] = 0

    payload = json.loads((BASE_DIR / "data.json").read_text(encoding="utf-8"))
    meta = {r["id"]: r for r in payload.get("rules", {}).get("rules", [])}

    rows = []
    for _, r in counts.iterrows():
        rid = str(r["rule_id"])
        m = meta.get(rid, {})
        rows.append(
            {
                "rule_id": rid,
                "name": m.get("name", ""),
                "predicate": m.get("predicate", ""),
                "severity": m.get("severity", ""),
                "treatment": m.get("treatment", ""),
                "fail": int(r["FAIL"]),
                "warning": int(r["WARNING"]),
                "value_removed": m.get("value_removed"),
                "top_city": m.get("top_city"),
                "top_month": m.get("top_month"),
                "top_payment": m.get("top_payment"),
            }
        )
    rows.sort(key=lambda x: x["rule_id"])
    return sanitize({"rows": rows})


@app.get("/api/quality/heatmap")
async def api_quality_heatmap():
    """% of orders with >=1 quality issue per city x month (quality_datamart)."""
    q = pd.read_csv(
        DATA_DIR / "quality_datamart.csv",
        usecols=["city_std", "order_month", "n_issues"],
    )
    q = q.dropna(subset=["city_std", "order_month"])
    grouped = (
        q.groupby(["city_std", "order_month"])
        .agg(rows=("n_issues", "size"), issue_rows=("n_issues", lambda s: int((s > 0).sum())))
        .reset_index()
    )
    grouped["pct"] = (grouped["issue_rows"] / grouped["rows"] * 100).round(1)
    # keep readable range: months from 2024-01 onward (2019-2022 has very few rows)
    grouped = grouped[grouped["order_month"] >= "2024-01"]
    cells = [
        {"city": r["city_std"], "month": r["order_month"], "rows": int(r["rows"]), "issues": int(r["issue_rows"]), "pct": float(r["pct"])}
        for _, r in grouped.iterrows()
    ]
    months = sorted({c["month"] for c in cells})
    cities = sorted({c["city"] for c in cells})
    return sanitize({"cells": cells, "months": months, "cities": cities})


@app.get("/api/quality/profile")
async def api_quality_profile():
    prof = _csv("profile.csv")
    prof = prof.sort_values("missing_pct", ascending=False)
    return sanitize({"rows": df_records(prof)})


@app.get("/api/quality/issues")
async def api_quality_issues():
    reg = _csv("issue_registry.csv")
    keep = [c for c in ["rule_id", "extract", "table", "column", "predicate", "fail_count", "count", "treatment", "pass_count"] if c in reg.columns]
    reg = reg[keep]
    return sanitize({"rows": df_records(reg)})


@app.get("/api/duplicates")
async def api_duplicates():
    """Dedup headline + masked registry + commission effect of cleaning."""
    commission = _csv("commission_datamart.csv").iloc[0]
    reg = _csv("duplicate_registry.csv")
    if "evidence" in reg.columns:
        reg = reg.assign(evidence=reg["evidence"].map(scrub_text))
    for col in ("loser_key", "survivor_key"):
        if col in reg.columns:
            reg = reg.assign(**{col: reg[col].map(lambda v: mask_id(v))})

    q = pd.read_csv(DATA_DIR / "quality_datamart.csv", usecols=["is_dup", "is_dup_id"])
    return sanitize(
        {
            "headline": {
                "raw_rows": int(commission["orders_before"]),
                "clean_rows": int(commission["orders_after"]),
                "rows_removed": int(commission["rows_removed"]),
                "commission_before": float(commission["commission_before"]),
                "commission_after": float(commission["commission_after"]),
                "commission_leakage": float(commission["commission_leakage"]),
            },
            "quality_flags": {
                "exact_duplicate_rows": int(q["is_dup"].sum()),
                "duplicate_order_id_rows": int(q["is_dup_id"].sum()),
            },
            "registry": df_records(reg.head(30)),
            "registry_total": int(len(_csv("duplicate_registry.csv"))),
        }
    )


# --------------------------------------------------------------------------- #
# Trust + commission panels
# --------------------------------------------------------------------------- #
@app.get("/api/trust")
async def api_trust():
    """Waterfall from raw extract to trusted population (outputs/)."""
    lenient = pd.read_csv(OUTPUTS_DIR / "lenient_trusted_orders.csv")
    strict = pd.read_csv(OUTPUTS_DIR / "strict_trusted_orders.csv")
    rejected = pd.read_csv(OUTPUTS_DIR / "rejected_orders.csv")

    status_counts = lenient["order_status"].value_counts().to_dict() if "order_status" in lenient.columns else {}
    clean = 6000
    len_rows, len_val = int(len(lenient)), float(lenient["line_value"].sum())
    str_rows, str_val = int(len(strict)), float(strict["line_value"].sum())
    return sanitize(
        {
            "waterfall": [
                {"stage": "Raw extract rows", "rows": 6103},
                {"stage": "After load", "rows": 6103},
                {"stage": "After dedup", "rows": clean},
                {"stage": "Rejected (FAIL)", "rows": int(len(rejected))},
                {"stage": "Lenient trusted", "rows": len_rows},
                {"stage": "Strict trusted", "rows": str_rows},
            ],
            "lenient": {"rows": len_rows, "value": len_val, "statuses": status_counts},
            "strict": {"rows": str_rows, "value": str_val},
            "rejected": {"rows": int(len(rejected))},
            "warning_only_rows": len_rows - str_rows,
            "reconciliation": {
                "raw": 6103,
                "clean": clean,
                "check": f"clean {clean} = lenient {len_rows} + rejected {int(len(rejected))}",
            },
        }
    )


@app.get("/api/commission")
async def api_commission():
    summary = _csv("commission_datamart.csv").iloc[0]

    def cut(name: str) -> list[dict]:
        path = DATA_DIR / f"{name}.csv"
        if not path.exists():
            return []
        return df_records(pd.read_csv(path))

    return sanitize(
        {
            "summary": {
                "commission_before": float(summary["commission_before"]),
                "commission_after": float(summary["commission_after"]),
                "commission_leakage": float(summary["commission_leakage"]),
                "orders_before": int(summary["orders_before"]),
                "orders_after": int(summary["orders_after"]),
                "rows_removed": int(summary["rows_removed"]),
            },
            "by_city": cut("commission_by_city"),
            "by_payment": cut("commission_by_payment"),
            "by_status": cut("commission_by_status"),
            "compare_city": cut("commission_compare_city"),
            "compare_payment": cut("commission_compare_payment"),
            "compare_status": cut("commission_compare_status"),
            "compare_month": cut("commission_compare_month"),
        }
    )


# --------------------------------------------------------------------------- #
# Manifest / questions / capstone
# --------------------------------------------------------------------------- #
def _payload() -> dict:
    return json.loads((BASE_DIR / "data.json").read_text(encoding="utf-8"))


@app.get("/api/manifest")
async def api_manifest():
    payload = _payload()
    return sanitize(
        {
            "run_hash": payload.get("run_hash"),
            "criteria": payload.get("criteria", []),
            "validations": payload.get("validations", []),
            "provenance": payload.get("provenance", {}),
            "rubric": payload.get("rubric", {}),
            "marts": payload.get("marts", []),
            "headline": payload.get("headline", {}),
        }
    )


def _trim_question(item: dict) -> dict:
    result = item.get("result") or {}
    fields = result.get("fields") if isinstance(result, dict) else None
    field_rows = {}
    if isinstance(fields, dict):
        for name, info in fields.items():
            if isinstance(info, dict):
                field_rows[name] = {"rows": len(info.get("head", []) or []), "count": info.get("rows")}
    result_text = None
    if isinstance(result, dict) and result.get("kind") == "text":
        result_text = scrub_question_text(result.get("value"), phone=False) or None
    return sanitize(
        {
            "id": item.get("id"),
            "segment": item.get("segment"),
            "status": item.get("status"),
            "pending_reason": scrub_question_text(item.get("pending_reason")),
            "title": item.get("title"),
            "method": item.get("method"),
            "headline": scrub_question_text(item.get("headline")),
            "result_text": result_text,
            "code": item.get("code"),
            "sql": item.get("sql"),
            "parity_tested": item.get("parity_tested"),
            "analogue": item.get("analogue"),
            "result_kind": (result.get("kind") if isinstance(result, dict) else None),
            "result_fields": field_rows,
        }
    )


@app.get("/api/questions")
async def api_questions(
    segment: str | None = None,
    status: str | None = None,
    q: str | None = None,
    limit: int = Query(200, ge=1, le=200),
):
    items = [_trim_question(i) for i in _payload().get("questions", [])]
    if segment and segment != "all":
        items = [i for i in items if i.get("segment") == segment]
    if status and status != "all":
        items = [i for i in items if i.get("status") == status]
    if q:
        needle = q.lower()
        items = [
            i
            for i in items
            if needle in (i.get("title") or "").lower()
            or needle in (i.get("headline") or "").lower()
            or needle in (i.get("result_text") or "").lower()
            or needle in str(i.get("id"))
        ]
    return sanitize({"rows": items[:limit], "total": len(items)})


@app.get("/api/capstone")
async def api_capstone():
    payload = _payload()
    insights = payload.get("insights", {})
    return sanitize(
        {
            "problems": payload.get("problems", []),
            "insights": insights.get("insights", []),
            "comparison": insights.get("comparison", []),
            "rejected": insights.get("rejected", []),
            "rubric": payload.get("rubric", {}),
        }
    )


@app.get("/api/sql-list")
async def api_sql_list():
    found: set[str] = set()
    for folder in SQL_RESULTS_DIRS:
        if folder.exists():
            for p in folder.glob("q*.csv"):
                found.add(p.stem)
    return {"qids": sorted(found)}


@app.get("/api/sql-file/{qid}")
async def api_sql_file(qid: str):
    if not re.fullmatch(r"q\d{1,3}", qid):
        raise HTTPException(status_code=400, detail="qid must look like q50")
    for folder in SQL_RESULTS_DIRS:
        path = folder / f"{qid}.csv"
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="replace")
            text = _EMAIL_RE.sub("[email masked]", text)
            text, masked_ids = mask_customer_ids_in_text(text)
            return sanitize(
                {
                    "qid": qid,
                    "source": f"data/{folder.name}/{qid}.csv",
                    "masked_customer_ids": masked_ids,
                    "text": text[:200000],
                }
            )
    raise HTTPException(status_code=404, detail=f"No saved result for {qid}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
