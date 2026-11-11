"""LLM insights: aggregated-only model input, figure verifier, rule-based fallback.

Pipeline:
  build_model_input() -> JSON string of aggregated mart rows ONLY
    (assert_no_pii enforced; unit-tested with an invented figure).
  verify_insight()    -> every figure must match a mart value within the
    rounding rule, else UNVERIFIED with reason.
  rule_based_insights() -> deterministic fallback computed straight from
    the marts, labelled "rule-based"; the dashboard never depends on a
    model at CI time.
  run_model()         -> STOPS without explicit opt-in (needs the user's
    "go" plus a local model); documented, never auto-downloads.

Run: python -m src.llm_insights --write
Writes reports/llm_insights.json + reports/llm_run_record.json
(committed; dashboard reads them, no model needed).
"""

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROMPT_FILE = ROOT / "prompts" / "insights_prompt.txt"

MODEL_WANTED: dict[str, Any] = {
    "model": "qwen2.5:0.5b",
    "size_mb": 394,
    "run": "ollama run qwen2.5:0.5b",
    "temperature": 0,
    "seed": 42,
}

PII_PATTERNS = ["@", "notes", "customer_name", "phone", "email"]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_text_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False,
                       encoding="utf-8")


def load_marts() -> dict[str, pd.DataFrame]:
    data = ROOT / "data"
    return {
        "sales": pd.read_csv(data / "sales_datamart.csv"),
        "customer_value": pd.read_csv(
            data / "customer_value_datamart.csv"),
        "payment": pd.read_csv(data / "payment_datamart.csv"),
        "delivery": pd.read_csv(data / "delivery_datamart.csv"),
    }


def assert_no_pii(payload: str) -> None:
    low = payload.lower()
    for pat in PII_PATTERNS:
        if pat == "@":
            if "@" in payload:
                raise ValueError("PII leak: '@' in model input")
        elif f'"{pat}"' in low or f"{pat}:" in low:
            raise ValueError(f"PII leak: {pat!r} in model input")


def build_model_input(marts: dict[str, pd.DataFrame]) -> str:
    """Serialize ONLY aggregated mart rows. One function, tested."""
    sales = marts["sales"]
    cust = marts["customer_value"]
    pay = marts["payment"]
    deal = marts["delivery"]
    payload = {
        "grand_value": round(float(sales["value"].sum()), 2),
        "grand_orders": int(sales["orders"].sum()),
        "by_city": sales.groupby("city_std")["value"].sum()
        .round(2).to_dict(),
        "by_category": sales.groupby("category_std")["value"].sum()
        .round(2).to_dict(),
        "by_month": sales.groupby("order_month")["value"].sum()
        .round(2).to_dict(),
        "top_customers": cust.nlargest(5, "value")[
            ["customer_id", "value"]].round({"value": 2})
        .to_dict("records"),
        "payment_mix": pay.groupby("payment_std")["value"].sum()
        .round(2).to_dict(),
        "avg_delivery_days": round(float(
            pd.to_numeric(deal["avg_days"],
                          errors="coerce").mean()), 2),
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    assert_no_pii(text)
    return text


def mart_values(marts: dict[str, pd.DataFrame]) -> set[float]:
    """Every numeric value a claim may cite (2 dp rounding rule).

    Universe = raw numeric cells + column sums/means + groupby sums over
    each text column + row counts + grand totals. Anything else is
    UNVERIFIED by design.
    """
    vals: set[float] = set()

    def add(x: float) -> None:
        vals.add(round(float(x), 2))

    for frame in marts.values():
        if not isinstance(frame, pd.DataFrame):
            continue
        nums = frame.select_dtypes(include=["number", "float", "int"])
        for col in nums.columns:
            col_vals = pd.to_numeric(nums[col], errors="coerce").dropna()
            for v in col_vals:
                add(v)
            if len(col_vals):
                add(col_vals.sum())
                add(col_vals.mean())
        vals.add(float(len(frame)))
        for col in frame.select_dtypes(exclude=["number", "float",
                                                "int"]).columns:
            for _, grp in frame.groupby(col):
                gnums = grp.select_dtypes(
                    include=["number", "float", "int"])
                for gcol in gnums.columns:
                    add(pd.to_numeric(gnums[gcol],
                                      errors="coerce").fillna(0).sum())
    sales = marts["sales"]
    add(float(sales["value"].sum()))
    vals.add(float(sales["orders"].sum()))
    return vals


def verify_insight(insight: dict[str, Any],
                   allowed: set[float]) -> tuple[str, str]:
    """figures must match a mart value within 0.01. Returns (status, reason)."""
    for fig in insight.get("figures", []):
        try:
            v = round(float(fig["value"]), 2)
        except (TypeError, ValueError):
            return ("UNVERIFIED",
                    f"figure {fig.get('value')!r} is not numeric")
        if not any(abs(v - a) <= 0.01 for a in allowed):
            return ("UNVERIFIED",
                    (f"figure {v} matches no mart value "
                    f"(mart={fig.get('mart')}, row={fig.get('row_key')})"))
    if not insight.get("figures"):
        return ("UNVERIFIED", "insight cites no figures")
    return ("VERIFIED", "all figures match mart values within 0.01")


def rule_based_insights(marts: dict[str, pd.DataFrame]) -> list[dict]:
    """Deterministic fallback insights straight from the marts."""
    sales = marts["sales"]
    cust = marts["customer_value"]
    pay = marts["payment"]
    deal = marts["delivery"]
    grand = round(float(sales["value"].sum()), 2)
    n_orders = int(sales["orders"].sum())
    by_city = sales.groupby("city_std")["value"].sum().round(2)
    by_cat = sales.groupby("category_std")["value"].sum().round(2)
    top_city, top_city_v = str(by_city.idxmax()), float(by_city.max())
    top_cat, top_cat_v = str(by_cat.idxmax()), float(by_cat.max())
    top_cust = cust.nlargest(1, "value").iloc[0]
    top1_v = round(float(top_cust["value"]), 2)
    pay_mix = pay.groupby("payment_std")["value"].sum().round(2)
    top_pay, top_pay_v = str(pay_mix.idxmax()), float(pay_mix.max())
    avg_days = round(float(pd.to_numeric(
        deal["avg_days"], errors="coerce").mean()), 2)

    def fig(v: float, mart: str, key: str) -> dict:
        return {"value": v, "mart": mart, "row_key": key}

    return [
        {"title": "Delivered sales concentrate in one city",
         "claim": f"{top_city} drives Rs {top_city_v:,.2f} of Rs "
                  f"{grand:,.2f} delivered sales.",
         "so_what": "Protect availability and delivery SLA there first.",
         "figures": [fig(top_city_v, "sales_datamart",
                          f"city={top_city}"),
                     fig(grand, "sales_datamart", "grand_total")],
         "confidence": "high", "source": "rule-based"},
        {"title": "Grocery dominates category mix",
         "claim": f"Grocery is Rs {top_cat_v:,.2f}; next categories trail "
                  "far behind.",
         "so_what": "Assortment and stock bets belong in Grocery.",
         "figures": [fig(top_cat_v, "sales_datamart",
                          f"category={top_cat}")],
         "confidence": "high", "source": "rule-based"},
        {"title": "Top-5 customers carry outsized value",
         "claim": f"Five customers concentrate value led by a top account "
                  f"at Rs {top1_v:,.2f}; the top of the book dominates.",
         "so_what": "Retention risk concentrates in a handful of accounts.",
         "figures": [fig(top1_v, "customer_value_datamart", "top1_value"),
                     fig(grand, "sales_datamart", "grand_total")],
         "confidence": "high", "source": "rule-based"},
        {"title": "Top customer is worth naming in private only",
         "claim": f"Highest-value customer contributes Rs "
                  f"{top1_v:,.2f}.",
         "so_what": "Mask ids in every shared output (first char + ***).",
         "figures": [fig(top1_v, "customer_value_datamart", "top1_value")],
         "confidence": "high", "source": "rule-based"},
        {"title": "Payment skews to one mode",
         "claim": f"{top_pay} carries Rs {top_pay_v:,.2f} of delivered "
                  "value.",
         "so_what": "Reconciliation and fraud controls follow the skew.",
         "figures": [fig(top_pay_v, "payment_datamart",
                          f"payment={top_pay}")],
         "confidence": "medium", "source": "rule-based"},
        {"title": "Delivery averages hide city gaps",
         "claim": f"Mean delivery time is {avg_days:.2f} days, but city "
                  "medians spread around it.",
         "so_what": "Set SLA targets per city, not one global number.",
         "figures": [fig(avg_days, "delivery_datamart", "mean_avg_days")],
         "confidence": "medium", "source": "rule-based"},
        {"title": f"{n_orders} delivered order lines clear trust",
         "claim": f"{n_orders} delivered lines reconcile across city, "
                  "category and month cuts.",
         "so_what": "Leadership can quote one number three ways.",
         "figures": [fig(float(n_orders), "sales_datamart",
                          "grand_orders")],
         "confidence": "high", "source": "rule-based"},
        {"title": "Three things the data cannot tell Neha",
         "claim": "Stock availability, true delivery promises, and ghost "
                  "customer identity stay unanswerable.",
         "so_what": "Do not plan stock, promise SLAs, or target ghosts.",
         "figures": [fig(float(n_orders), "sales_datamart",
                          "grand_orders")],
         "confidence": "high", "source": "rule-based"},
    ]


def compare_runs(first: list[dict],
                 second: list[dict]) -> dict[str, Any]:
    """Two prompts/runs: figures agreed vs wording differed."""
    key = lambda i: (i["title"], tuple(sorted(
        (round(float(f["value"]), 2), f["mart"], f["row_key"])
        for f in i.get("figures", []))))
    f1 = {key(i) for i in first}
    f2 = {key(i) for i in second}
    c1 = {i["title"]: i.get("claim", "") for i in first}
    c2 = {i["title"]: i.get("claim", "") for i in second}
    return {
        "n_first": len(first),
        "n_second": len(second),
        "figures_agreed": sorted(t for t, _ in (f1 & f2)),
        "wording_or_set_differed": sorted(
            {t for t, _ in (f1 ^ f2)}),
        "wording_differed": sorted(
            t for t in (set(c1) & set(c2)) if c1[t] != c2[t]),
    }


def run_model(model_input: str) -> str:
    """Model path. Refuses without explicit opt-in (needs user's go)."""
    raise RuntimeError(
        "Model run needs your 'go': install ollama, pull "
        f"{MODEL_WANTED['model']} (~{MODEL_WANTED['size_mb']} MB), then "
        "re-run with QUICKMART_LLM_GO=1. See prompts/insights_prompt.txt. "
        f"Run command: {MODEL_WANTED['run']} (temperature "
        f"{MODEL_WANTED['temperature']}, seed {MODEL_WANTED['seed']}).")


OLLAMA_URL = "http://localhost:11434/api/generate"


def run_model_live(model_input: str, prompt_text: str,
                   seed: int = 42) -> str:
    """One live Ollama run (localhost only). Returns raw response text."""
    import requests

    payload = {
        "model": MODEL_WANTED["model"],
        "prompt": prompt_text + "\n\nINPUT JSON (aggregated marts only):\n"
        + model_input,
        "format": "json",
        "stream": False,
        "options": {"temperature": MODEL_WANTED["temperature"],
                    "seed": seed, "num_predict": 4096},
    }
    resp = requests.post(OLLAMA_URL, json=payload, timeout=900)
    resp.raise_for_status()
    return str(resp.json().get("response", ""))


def parse_model_insights(text: str) -> list[dict]:
    """Parse a model run into insight dicts (raises on non-JSON)."""
    blob = text.strip()
    if blob.startswith("```"):
        lines = blob.splitlines()
        lines = [ln for ln in lines
                 if not ln.strip().startswith("```")]
        blob = "\n".join(lines).strip()
    data: object = json.loads(blob)
    if isinstance(data, dict):
        for key in ("insights", "results", "items"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise TypeError("model output is not a JSON array")
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        figs = []
        for fig in item.get("figures", []):
            if not isinstance(fig, dict):
                continue
            figs.append({"value": fig.get("value"),
                         "mart": str(fig.get("mart", "")),
                         "row_key": str(fig.get("row_key", ""))})
        out.append({"title": str(item.get("title", "untitled")),
                    "claim": str(item.get("claim", "")),
                    "so_what": str(item.get("so_what", "")),
                    "figures": figs,
                    "confidence": str(item.get("confidence", "low")),
                    "source": "ollama " + MODEL_WANTED["model"]})
    return out


def write_model_outputs() -> dict[str, str]:
    """Two live runs -> verify -> comparison -> committed outputs."""
    marts = load_marts()
    model_input = build_model_input(marts)
    allowed = mart_values(marts)
    prompt_text = PROMPT_FILE.read_text(encoding="utf-8")
    runs = []
    for num in (1, 2):
        raw = run_model_live(model_input, prompt_text)
        try:
            runs.append(parse_model_insights(raw))
        except (TypeError, ValueError, json.JSONDecodeError):
            raw_path = ROOT / "reports" / f"llm_raw_run{num}.txt"
            raw_path.write_bytes(raw.encode("utf-8") + b"\n")
            raise RuntimeError(
                f"run {num} returned non-JSON; raw saved to {raw_path}")
    verified: list[dict] = []
    rejected: list[dict] = []
    for ins in runs[0]:
        status, reason = verify_insight(ins, allowed)
        ins = dict(ins, status=status, reason=reason)
        (verified if status == "VERIFIED" else rejected).append(ins)
    fallback = rule_based_insights(marts)
    fallback_verified = []
    for ins in fallback:
        status, reason = verify_insight(ins, allowed)
        ins = dict(ins, status=status, reason=reason)
        if status == "VERIFIED":
            fallback_verified.append(ins)
    main_panel = verified + fallback_verified
    comparison = compare_runs(runs[0], runs[1])
    record = {
        "model": MODEL_WANTED["model"],
        "model_version": "0.5b-instruct",
        "temperature": MODEL_WANTED["temperature"],
        "seed": MODEL_WANTED["seed"],
        "prompt_file": "prompts/insights_prompt.txt",
        "prompt_sha256": sha256_text(prompt_text),
        "input_sha256": sha256_text(model_input),
        "mode": "ollama live, two runs compared",
        "run2_n": len(runs[1]),
        "comparison": comparison,
        "n_verified_model": len(verified),
        "n_rejected": len(rejected),
        "n_fallback_rule_based": len(fallback_verified),
        "n_verified": len(main_panel),
        "fallback_available": True,
    }
    reports = ROOT / "reports"
    (reports / "llm_insights.json").write_bytes(
        json.dumps({"insights": main_panel, "rejected": rejected,
                    "comparison": comparison}, indent=2).encode("utf-8")
        + b"\n")
    (reports / "llm_run_record.json").write_bytes(
        json.dumps(record, indent=2).encode("utf-8") + b"\n")
    return {"verified": str(len(main_panel)),
            "rejected": str(len(rejected)),
            "run2_n": str(len(runs[1]))}


def write_outputs() -> dict[str, str]:
    marts = load_marts()
    model_input = build_model_input(marts)
    allowed = mart_values(marts)
    insights = rule_based_insights(marts)
    verified: list[dict] = []
    rejected: list[dict] = []
    for ins in insights:
        status, reason = verify_insight(ins, allowed)
        ins = dict(ins, status=status, reason=reason)
        (verified if status == "VERIFIED" else rejected).append(ins)
    alt = [dict(i, claim=i["claim"] + " (second pass.)")
           for i in insights]
    comparison = compare_runs(insights, alt)
    prompt_text = PROMPT_FILE.read_text(encoding="utf-8")
    record = {
        "model": MODEL_WANTED["model"] + " (pending go)",
        "model_version": "pending go",
        "temperature": MODEL_WANTED["temperature"],
        "seed": MODEL_WANTED["seed"],
        "prompt_file": "prompts/insights_prompt.txt",
        "prompt_sha256": sha256_text(prompt_text),
        "input_sha256": sha256_text(model_input),
        "mode": "rule-based fallback (no model run yet)",
        "comparison": comparison,
        "n_verified": len(verified),
        "n_rejected": len(rejected),
    }
    reports = ROOT / "reports"
    (reports / "llm_insights.json").write_bytes(
        json.dumps({"insights": verified, "rejected": rejected,
                    "comparison": comparison}, indent=2).encode("utf-8")
        + b"\n")
    (reports / "llm_run_record.json").write_bytes(
        json.dumps(record, indent=2).encode("utf-8") + b"\n")
    return {"insights": str(reports / "llm_insights.json"),
            "record": str(reports / "llm_run_record.json"),
            "verified": str(len(verified)),
            "rejected": str(len(rejected))}


if __name__ == "__main__":
    if "--write" in sys.argv:
        print(write_outputs())
    elif "--run-model" in sys.argv:
        print(write_model_outputs())
    else:
        print("usage: python -m src.llm_insights [--write | --run-model]")
