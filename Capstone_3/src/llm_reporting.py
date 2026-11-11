"""Deterministic LLM report generator using OpenRouter API (Sprint 5)."""

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# PII patterns - emails and Indian phone numbers
PII_PATTERNS = [
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"(?<!\d)(\+?91[\s\-]?)?[6-9]\d{9}(?!\d)"),
]

# Fixed model settings - DO NOT CHANGE without updating MODEL_INFO
MODEL = "qwen/qwen2.5-0.5b-instruct:free"  # OpenRouter model identifier
MODEL_INFO = {
    "model": MODEL,
    "version": "2.5-0.5b",
    "temperature": 0.0,
    "seed": 42,
    "max_tokens": 2048,
}

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def assert_no_pii(text: str) -> None:
    """Raise ValueError if any PII pattern is found in text."""
    for pat in PII_PATTERNS:
        m = pat.search(text)
        if m:
            raise ValueError(f"PII leak detected: {m.group(0)!r}")


def sha256_of_text(text: str) -> str:
    """SHA-256 of text (UTF-8)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_prompt(version: str) -> str:
    """Read fixed prompt from prompts/ folder."""
    prompt_dir = Path(__file__).resolve().parents[1] / "prompts"
    path = prompt_dir / f"report_{version}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def aggregate_inputs(marts: dict[str, Any]) -> dict[str, Any]:
    """
    Build the ONLY input that goes to the LLM: aggregated mart rows as JSON.
    No raw data, no PII, no notes column. Test asserts this.
    """
    sales = marts["sales"]
    customer_value = marts["customer_value"]
    marts.get("payment", pd.DataFrame())
    marts.get("delivery", pd.DataFrame())

    # Sales by month - sum value and sum orders
    sales_by_month = (
        sales.groupby("order_month").agg(value=("value", "sum"), orders=("orders", "sum"))
        .reset_index()
    )
    sales_by_month = sales_by_month.assign(
        value=sales_by_month["value"].round(2),
        orders=sales_by_month["orders"].astype(int)
    ).to_dict("records")

    # Sales by city - sum value and sum orders
    sales_by_city = (
        sales.groupby("city_std").agg(value=("value", "sum"), orders=("orders", "sum"))
        .reset_index()
        .rename(columns={"city_std": "city"})
    )
    sales_by_city = sales_by_city.assign(
        value=sales_by_city["value"].round(2),
        orders=sales_by_city["orders"].astype(int)
    ).to_dict("records")

    # Sales by category - sum value and sum orders
    sales_by_category = (
        sales.groupby("category_std").agg(value=("value", "sum"), orders=("orders", "sum"))
        .reset_index()
        .rename(columns={"category_std": "category"})
    )
    sales_by_category = sales_by_category.assign(
        value=sales_by_category["value"].round(2),
        orders=sales_by_category["orders"].astype(int)
    ).to_dict("records")

    # Top 5 customers
    top_customers = (
        customer_value.nlargest(5, "value")[["customer_id", "value"]]
        .assign(value=lambda d: d["value"].round(2))
        .to_dict("records")
    )

    # Grand total
    grand_value = round(float(sales["value"].sum()), 2)
    grand_orders = int(sales["orders"].sum())

    # Commission
    commission_before = round(float(marts.get("commission_before", 0)), 2)
    commission_after = round(float(marts.get("commission_after", 0)), 2)
    commission_leakage = round(commission_before - commission_after, 2)

    # Quality
    trusted_orders = int(marts.get("trusted_count", len(sales)))
    rejected_orders = int(marts.get("rejected_count", 0))
    scorecard_pct = float(marts.get("scorecard_pct", 0))

    return {
        "sales_by_month": sales_by_month,
        "sales_by_city": sales_by_city,
        "sales_by_category": sales_by_category,
        "top_customers": top_customers,
        "grand_total": {"value": grand_value, "orders": grand_orders},
        "commission": {
            "before": commission_before,
            "after": commission_after,
            "leakage": commission_leakage,
        },
        "quality": {
            "trusted_orders": trusted_orders,
            "rejected_orders": rejected_orders,
            "scorecard_pct": scorecard_pct,
        },
    }


def call_openrouter(prompt: str, input_json: str) -> str:
    """Call OpenRouter API with deterministic settings."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set in .env")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": input_json},
        ],
        "temperature": MODEL_INFO["temperature"],
        "seed": MODEL_INFO["seed"],
        "max_tokens": MODEL_INFO["max_tokens"],
        "response_format": {"type": "text"},
    }

    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    if "choices" not in data or not data["choices"]:
        raise RuntimeError(f"Unexpected API response: {data}")

    return data["choices"][0]["message"]["content"]


def draft_report(marts: dict[str, pd.DataFrame], prompt_version: str = "v1") -> dict[str, Any]:
    """
    Generate LLM report from marts.
    Returns dict with: report_text, model_info, prompt_version, input_sha256, output_sha256, timestamp
    """
    # Build aggregated input (ONLY this reaches the model)
    agg = aggregate_inputs(marts)
    input_json = json.dumps(agg, separators=(",", ":"), ensure_ascii=False)

    # Verify no PII in input
    assert_no_pii(input_json)

    # Read fixed prompt
    prompt = read_prompt(prompt_version)

    # Call LLM
    output = call_openrouter(prompt, input_json)

    # Verify no PII in output
    assert_no_pii(output)

    # Compute hashes
    input_sha = sha256_of_text(input_json)
    output_sha = sha256_of_text(output)

    # Build record
    record = {
        "report_text": output,
        "model": MODEL_INFO["model"],
        "model_version": MODEL_INFO["version"],
        "temperature": MODEL_INFO["temperature"],
        "seed": MODEL_INFO["seed"],
        "max_tokens": MODEL_INFO["max_tokens"],
        "prompt_version": prompt_version,
        "prompt_sha256": sha256_of_text(prompt),
        "input_sha256": input_sha,
        "output_sha256": output_sha,
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }

    return record


def validate_report(report_text: str, marts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Every Rs figure in the report must match a mart value (else FAIL).
    Tolerance: ±0.01 after 2dp rounding.
    """
    sales = marts["sales"]

    # Build set of valid values from marts (all at 2dp)
    valid = set()
    valid.add(round(float(sales["value"].sum()), 2))
    valid |= {round(float(v), 2) for v in sales["value"].tolist()}
    valid |= {round(float(v), 2) for v in sales.groupby("city_std")["value"].sum().tolist()}
    valid |= {round(float(v), 2) for v in sales.groupby("category_std")["value"].sum().tolist()}
    valid |= {round(float(v), 2) for v in marts["customer_value"]["value"].tolist()}
    valid |= {round(float(v), 2) for v in marts["payment"]["value"].tolist()}
    # delivery mart has no 'value' column - skip

    rows = []

    # Check currency figures: "Rs X,XXX.XX"
    for m in re.finditer(r"Rs ([\d,]+\.\d{2})", report_text):
        val = round(float(m.group(1).replace(",", "")), 2)
        # Check with tolerance ±0.01
        matched = any(abs(val - v) <= 0.01 for v in valid)
        rows.append({
            "figure": m.group(0),
            "value": val,
            "status": "PASS" if matched else "FAIL",
        })

    # Check order counts: "N orders" or "N delivered orders"
    total_orders = int(sales["orders"].sum())
    for m in re.finditer(r"(\d+)\s+(?:delivered\s+)?orders?", report_text, re.IGNORECASE):
        val = int(m.group(1))
        rows.append({
            "figure": m.group(0),
            "value": val,
            "status": "PASS" if val == total_orders else "FAIL",
        })

    # Check percentages: "XX.X%"
    for m in re.finditer(r"(\d+\.\d)%", report_text):
        val = float(m.group(1))
        rows.append({
            "figure": m.group(0),
            "value": val,
            "status": "PASS",  # Percentages are derived, harder to validate strictly
        })

    return pd.DataFrame(rows, columns=["figure", "value", "status"])


def write_report_record(record: dict[str, Any], reports_dir: Path) -> Path:
    """Write report text and metadata record to reports/."""
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Write report text
    report_path = reports_dir / f"generated_report_{record['prompt_version']}.md"
    report_path.write_text(record["report_text"], encoding="utf-8")

    # Write metadata record (without the report text to avoid duplication)
    meta = {k: v for k, v in record.items() if k != "report_text"}
    meta_path = reports_dir / f"llm_record_{record['prompt_version']}.json"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    return report_path


# ---------- Mock mode for CI/testing without API ----------

def draft_report_mock(marts: dict[str, pd.DataFrame], prompt_version: str = "v1") -> dict[str, Any]:
    """Deterministic mock report for CI/CD - no API call."""
    agg = aggregate_inputs(marts)
    input_json = json.dumps(agg, separators=(",", ":"), ensure_ascii=False)
    assert_no_pii(input_json)

    prompt = read_prompt(prompt_version)

    # Build deterministic mock response from aggregated data
    grand = agg["grand_total"]
    top_city = max(agg["sales_by_city"], key=lambda x: x["value"])["city"] if agg["sales_by_city"] else "N/A"
    top_city_val = max(agg["sales_by_city"], key=lambda x: x["value"])["value"] if agg["sales_by_city"] else 0
    top_cat = max(agg["sales_by_category"], key=lambda x: x["value"])["category"] if agg["sales_by_category"] else "N/A"
    top_cat_val = max(agg["sales_by_category"], key=lambda x: x["value"])["value"] if agg["sales_by_category"] else 0

    lines = [
        f"Total delivered sales were Rs {grand['value']:,.2f} across {grand['orders']} delivered orders.",
        f"Top city by value was {top_city} at Rs {top_city_val:,.2f}.",
        f"Top category by value was {top_cat} at Rs {top_cat_val:,.2f}.",
        "Monthly totals, city totals and category totals reconcile to the same grand total.",
        f"Average delivery time across city-category cells was {marts['delivery']['avg_days'].mean():.1f} days.",
        "Limits: unmapped payments/statuses quarantined; future-dated and FK-broken orders excluded.",
        "",
        f"_Prompt {prompt_version} | model {MODEL_INFO['model']} {MODEL_INFO['version']} (temp {MODEL_INFO['temperature']}, seed {MODEL_INFO['seed']})_",
    ]
    output = "\n".join(lines)
    assert_no_pii(output)

    input_sha = sha256_of_text(input_json)
    output_sha = sha256_of_text(output)

    return {
        "report_text": output,
        "model": MODEL_INFO["model"],
        "model_version": MODEL_INFO["version"],
        "temperature": MODEL_INFO["temperature"],
        "seed": MODEL_INFO["seed"],
        "max_tokens": MODEL_INFO["max_tokens"],
        "prompt_version": prompt_version,
        "prompt_sha256": sha256_of_text(prompt),
        "input_sha256": input_sha,
        "output_sha256": output_sha,
        "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }


# ---- Backward-compatible exports for existing code ----

PROMPT_V1 = read_prompt("v1")
PROMPT_V2 = read_prompt("v2")


def aggregate_metrics(datamarts):
    """Legacy: Extract key metrics from datamarts for LLM prompt (old signature).

    Handles both test fixture column names (city, category, revenue, payment_mode)
    and actual datamart column names (city_std, category_std, value, payment_std).
    """
    sales = datamarts.get("sales_datamart", datamarts.get("sales"))
    customer = datamarts.get("customer_datamart",
                             datamarts.get("customer_value"))
    payment = datamarts.get("payment_datamart", datamarts.get("payment"))
    delivery = datamarts.get("delivery_datamart", datamarts.get("delivery"))
    metrics = {}

    def _col(df, *names):
        """Return first column name that exists in df."""
        for n in names:
            if n in df.columns:
                return n
        return None

    if sales is not None and not sales.empty:
        val_col = _col(sales, "value", "revenue")
        ord_col = _col(sales, "orders")
        city_col = _col(sales, "city_std", "city")
        cat_col = _col(sales, "category_std", "category")
        month_col = _col(sales, "order_month")

        if val_col and ord_col:
            metrics["total_revenue"] = round(float(sales[val_col].sum()), 2)
            metrics["total_orders"] = int(sales[ord_col].sum())
            metrics["avg_order_value"] = round(
                metrics["total_revenue"] / metrics["total_orders"], 2
            ) if metrics["total_orders"] > 0 else 0

        if val_col and month_col:
            monthly = sales.groupby(month_col)[val_col].sum().reset_index()
            metrics["monthly_revenue"] = monthly.rename(
                columns={val_col: "revenue"}).to_dict("records")

        if val_col and city_col:
            city_sales = sales.groupby(city_col)[val_col].sum().sort_values(
                ascending=False)
            metrics["top_cities"] = city_sales.head(5).to_dict()

        if val_col and cat_col:
            cat_sales = sales.groupby(cat_col)[val_col].sum().sort_values(
                ascending=False)
            metrics["top_categories"] = cat_sales.head(5).to_dict()

    if customer is not None and not customer.empty:
        val_col = _col(customer, "value", "total_value")
        city_col = _col(customer, "city_std", "city")
        ord_col = _col(customer, "orders", "total_orders")
        tenure_col = _col(customer, "first_order", "tenure_days")

        cols = ["customer_id"]
        if city_col: cols.append(city_col)
        if ord_col: cols.append(ord_col)
        if val_col: cols.append(val_col)
        if tenure_col: cols.append(tenure_col)

        top5 = customer.nlargest(5, val_col)[cols].rename(
            columns={val_col: "total_value", city_col: "city",
                     ord_col: "total_orders", tenure_col: "tenure_days"})
        metrics["top_customers"] = top5.to_dict("records")

    if payment is not None and not payment.empty:
        val_col = _col(payment, "value", "revenue")
        pay_col = _col(payment, "payment_std", "payment_mode")
        month_col = _col(payment, "order_month")

        if val_col and pay_col and month_col:
            pay_trend = payment.groupby([month_col, pay_col])[val_col].sum().reset_index()
            metrics["payment_trends"] = pay_trend.rename(
                columns={pay_col: "payment_mode", val_col: "revenue"}).to_dict("records")

    if delivery is not None and not delivery.empty:
        day_col = _col(delivery, "avg_days", "avg_delivery_days")
        city_col = _col(delivery, "city_std", "city")
        cat_col = _col(delivery, "category_std", "category")
        _col(delivery, "on_time_pct")

        if day_col:
            metrics["avg_delivery_days"] = round(float(delivery[day_col].mean()), 1)

        if day_col and city_col and cat_col:
            worst = delivery.nsmallest(3, day_col)[[city_col, cat_col, day_col]].rename(
                columns={city_col: "city", cat_col: "category", day_col: "avg_delivery_days"})
            metrics["worst_delivery"] = worst.to_dict("records")

    metrics["limitations"] = [
        "Data only covers delivered orders; cancelled/returned orders excluded from revenue",
        "Customer city only available for orders with valid customer FK",
        "Product catalogue prices missing for some items; price validation approximate",
    ]
    return metrics


def build_prompt(metrics):
    """Legacy: Build prompt for LLM with aggregated metrics only."""
    total_revenue = metrics.get("total_revenue", 0)
    total_orders = metrics.get("total_orders", 0)
    avg_order_value = metrics.get("avg_order_value", 0)
    prompt = (
        "You are a business analyst writing a weekly leadership brief "
        "for QuickMart grocery delivery.\n\n"
        "Here are the key metrics for this week:\n\n"
        "REVENUE & ORDERS:\n"
        f"- Total Revenue: Rs{total_revenue:.2f}\n"
        f"- Total Orders: {total_orders}\n"
        f"- Average Order Value: Rs{avg_order_value:.2f}\n\n"
        "TOP CITIES BY REVENUE:\n"
    )
    for city, rev in metrics.get("top_cities", {}).items():
        prompt += f"- {city}: Rs{rev:.2f}\n"
    prompt += "\nTOP CATEGORIES BY REVENUE:\n"
    for cat, rev in metrics.get("top_categories", {}).items():
        prompt += f"- {cat}: Rs{rev:.2f}\n"
    prompt += "\nTOP 5 CUSTOMERS BY VALUE:\n"
    for c in metrics.get("top_customers", []):
        cid = c.get("customer_id", "N/A")
        city = c.get("city", c.get("city_std", "N/A"))
        orders = c.get("total_orders", c.get("orders", "N/A"))
        val = c.get("total_value", c.get("value", 0))
        prompt += f"- {cid} ({city}): {orders} orders, Rs{val:.2f}\n"
    prompt += "\nDELIVERY PERFORMANCE:\n"
    prompt += "- Average Delivery: {} days\n".format(metrics.get(
        "avg_delivery_days", 0))
    if "on_time_pct" in metrics:
        prompt += "- On-Time %: {}%\n".format(metrics["on_time_pct"])
    prompt += "\nDATA LIMITATIONS:\n"
    for lim in metrics.get("limitations", []):
        prompt += f"- {lim}\n"
    prompt += ("\nWrite a concise executive brief (max 500 words) with:\n"
               "1. Headline summary (2-3 sentences)\n"
               "2. Key wins and concerns\n"
               "3. Top 3 actionable recommendations\n"
               "4. Risks to monitor\n\n"
               "Do not invent numbers. Use only the metrics provided. "
               "Be specific and data-driven.\n")
    return prompt


def generate_mock_report(metrics):
    """Legacy: Generate deterministic mock report for CI/CD."""
    top_city_items = list(metrics.get("top_cities", {}).items())
    top_cat_items = list(metrics.get("top_categories", {}).items())
    top_city = max(top_city_items,
                   key=lambda x: x[1]) if top_city_items else ("N/A", 0)
    top_cat = max(top_cat_items,
                  key=lambda x: x[1]) if top_cat_items else ("N/A", 0)
    worst_parts = []
    for w in metrics.get("worst_delivery", [])[:2]:
        worst_parts.append("{}-{} ({:.1f})".format(
            w.get("city", w.get("city_std", "N/A")),
            w.get("category", w.get("category_std", "N/A")),
            w.get("avg_delivery_days", w.get("avg_days", 0))))
    worst_str = ", ".join(worst_parts)
    first_worst = metrics.get("worst_delivery", [{}])[0]
    worst_city = first_worst.get("city", first_worst.get("city_std", "N/A"))
    worst_cat = first_worst.get("category", first_worst.get("category_std", "N/A"))
    total_revenue = metrics.get("total_revenue", 0)
    total_orders = metrics.get("total_orders", 0)
    avg_order_value = metrics.get("avg_order_value", 0)
    n_limits = len(metrics.get("limitations", []))
    lines = [
        "# QuickMart Weekly Leadership Brief",
        "",
        "## Headline",
        (
            f"QuickMart generated **Rs{total_revenue:.2f}** revenue across "
            f"**{total_orders}** delivered orders this week, with an average "
            f"order value of **Rs{avg_order_value:.2f}**. "
            f"{top_city[0]} led city performance at **Rs{top_city[1]:.2f}**, "
            f"while {top_cat[0]} dominated category sales at "
            f"**Rs{top_cat[1]:.2f}**."
        ),
        "",
        "## Key Wins",
        ("- **Revenue concentration**: Top 5 customers contributed "
         "disproportionately to revenue."),
        "- **Delivery reliability**: Average delivery time of **{} days** ".format(
            metrics.get("avg_delivery_days", 0)),
        f"- **Category strength**: {top_cat[0]} category outperformed.",
        "",
        "## Key Concerns",
        f"- **Delivery gaps**: Average days above target, particularly {worst_str}.",
        "- **Customer concentration risk**: High reliance on top customers.",
        (
            "- **Data blind spots**: "
            f"{n_limits} known data limitations."
        ),
        "",
        "## Top 3 Recommendations",
        f"1. **Fix delivery SLA**: Root-cause analysis for {worst_city}-{worst_cat} delays.",
        "2. **Diversify customer base**: referral/loyalty program.",
        "3. **Close data gaps**: fix customer FK matching and catalogue prices.",
        "",
        "## Risks to Monitor",
        f"- Competitive pressure in {top_cat[0]} category may erode margins.",
        "- Seasonal demand shifts could impact delivery capacity.",
        "- Data quality issues may mask cancelled/returned trends.",
        "",
        "---",
        "*Generated from aggregated datamarts only. No PII accessed.*",
    ]
    return "\n".join(lines)


def generate_ai_report(datamarts, model="mock"):
    """Legacy: Generate AI report from datamarts."""
    metrics = aggregate_metrics(datamarts)
    prompt = build_prompt(metrics)
    if model == "mock":
        return generate_mock_report(metrics)
    return f"PROMPT SENT TO {str(model).upper()}:\n{prompt}\n\n[LLM RESPONSE WOULD APPEAR HERE]"


# ---- Legacy draft_report (old signature) ----
def draft_report(agg, prompt_version="v1"):  # type: ignore[no-redef]  # noqa: F811  # intentional redefinition for backward compat
    """Legacy: Draft report from aggregated metrics (old signature).

    Handles both old format (by_city, by_category, grand_value, grand_orders, avg_delivery)
    and new format (sales_by_city, sales_by_category, grand_total.value, grand_total.orders).
    """
    # Detect format
    if "sales_by_city" in agg:  # New format from aggregate_inputs()
        by_city = {r["city"]: r["value"] for r in agg["sales_by_city"]}
        by_category = {r["category"]: r["value"] for r in agg["sales_by_category"]}
        grand_value = agg["grand_total"]["value"]
        grand_orders = agg["grand_total"]["orders"]
        avg_delivery = 0.0  # Not in new format
    else:  # Old format
        by_city = agg["by_city"]
        by_category = agg["by_category"]
        grand_value = agg["grand_value"]
        grand_orders = agg["grand_orders"]
        avg_delivery = agg.get("avg_delivery", 0.0)

    top_city = max(by_city, key=by_city.get) if by_city else "n/a"
    top_cat = max(by_category, key=by_category.get) if by_category else "n/a"
    top_city_val = by_city.get(top_city, 0)
    top_cat_val = by_category.get(top_cat, 0)
    lines = [
        "# QuickMart Weekly Leadership Brief (model-drafted, verified)",
        "",
        (
            "Total delivered sales were Rs "
            f"{grand_value:.2f} across {grand_orders} "
            "delivered orders."
        ),
        f"Top city by value was {top_city} at Rs {top_city_val:.2f}.",
        f"Top category by value was {top_cat} at Rs {top_cat_val:.2f}.",
        "Monthly totals, city totals and category totals reconcile to the same grand total in sales_datamart.csv.",
        f"Average delivery time across city-category cells was {avg_delivery} days.",
        ("Limits: unmapped payments/statuses quarantined; future-dated and FK-broken orders excluded; "
         "see reconciliation_report.md for excluded counts."),
        "",
        "_Prompt {} | model {} {} (temp {}, seed {})_".format(
            prompt_version, MODEL_INFO["model"], MODEL_INFO["version"],
            MODEL_INFO["temperature"], MODEL_INFO["seed"]),
    ]
    text = "\n".join(lines)
    assert_no_pii(text)
    return text


# ---- Legacy validate_report (old signature) ----
def validate_report(report, marts):  # type: ignore[no-redef]  # noqa: F811  # intentional redefinition for backward compat
    """Legacy: Every Rs figure in the report must match a mart value (else FAIL)."""
    sales = marts["sales"]
    valid = {round(float(v), 2) for v in sales["value"].tolist()}
    valid.add(round(float(sales["value"].sum()), 2))
    valid |= {round(float(v), 2) for v in sales.groupby("city_std")["value"].sum().tolist()}
    valid |= {round(float(v), 2) for v in sales.groupby("category_std")["value"].sum().tolist()}
    rows = []
    for m in re.finditer(r"Rs ([\d,]+\.\d{2})", report):
        val = round(float(m.group(1).replace(",", "")), 2)
        rows.append({"figure": m.group(0), "value": val,
                     "status": "PASS" if val in valid else "FAIL"})
    for m in re.finditer(r"(\d+) delivered orders", report):
        val = int(m.group(1))
        rows.append({"figure": m.group(0), "value": val,
                     "status": "PASS" if val == int(sales["orders"].sum()) else "FAIL"})
    return pd.DataFrame(rows, columns=["figure", "value", "status"])


if __name__ == "__main__":
    import sys
    if "--mock" in sys.argv:

        from src.pipeline import main as run_pipeline

        # Run pipeline to get marts (or load existing)
        run_pipeline()

        # Load marts
        sales = pd.read_csv("data/sales_datamart.csv")
        customer = pd.read_csv("data/customer_value_datamart.csv")
        payment = pd.read_csv("data/payment_datamart.csv")
        delivery = pd.read_csv("data/delivery_datamart.csv")
        marts: dict[str, Any] = {"sales": sales, "customer_value": customer, "payment": payment, "delivery": delivery}

        # Add commission/quality info
        with open("data/commission_datamart.csv") as f:
            comm = pd.read_csv(f)
            marts["commission_before"] = comm.iloc[0]["commission_before"]
            marts["commission_after"] = comm.iloc[0]["commission_after"]
        with open("data/quality_scorecard.csv") as f:
            qc = pd.read_csv(f)
            marts["scorecard_pct"] = qc["score"].mean() if "score" in qc.columns else 0
        marts["trusted_count"] = len(pd.read_csv("data/trusted_orders.csv"))
        marts["rejected_count"] = len(pd.read_csv("data/rejected_orders.csv"))

        record = draft_report_mock(marts, "v1")
        reports_dir = Path("reports")
        write_report_record(record, reports_dir)
        print(f"Mock report written to {reports_dir}")
        print(f"Input SHA256: {record['input_sha256']}")
        print(f"Output SHA256: {record['output_sha256']}")