"""Live end-to-end check against the running server.

Usage: start the server first (uvicorn main:app) then run
    python tests/live_check.py
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parent.parent.parent  # .../QuickMart
DATA = ROOT / "data"


def get(path):
    req = urllib.request.Request(BASE + path, headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read(), dict(r.headers)


def wait_ready():
    for _ in range(40):
        try:
            st, body, _ = get("/api/health")
            if st == 200:
                return True
        except Exception:
            time.sleep(0.5)
    return False


if not wait_ready():
    print("SERVER DID NOT START")
    sys.exit(1)

failures = 0

print("=== static assets ===")
for path, expect in [
    ("/", "text/html"),
    ("/static/styles.css", "text/css"),
    ("/static/app.js", "javascript"),
    ("/static/charts.js", "javascript"),
    ("/static/vendor/chart.umd.min.js", "javascript"),
    ("/media/charts/monthly_sales.png", "image/png"),
]:
    st, body, headers = get(path)
    ok = st == 200 and expect in headers.get("content-type", "")
    if not ok:
        failures += 1
    print(f"[{'OK ' if ok else 'FAIL'}] {path} -> {st} type={headers.get('content-type')} bytes={len(body)}")

print()
print("=== api endpoints ===")
ENDPOINTS = [
    "/api/health",
    "/api/meta",
    "/api/kpis",
    "/api/kpis?city=Bengaluru&month_from=2026-01&month_to=2026-10",
    "/api/kpis?category=Grocery",
    "/api/monthly-sales",
    "/api/monthly-sales?city=Mysuru&month_from=2025-01&month_to=2026-10",
    "/api/sales-cuts?dim=city&category=Grocery",
    "/api/sales-cuts?dim=category&city=Bengaluru",
    "/api/payment-mix",
    "/api/payment-mix?city=Chennai&month_from=2026-01&month_to=2026-10",
    "/api/top-customers?n=10&by=value",
    "/api/top-customers?n=5&by=orders&city=Mysuru",
    "/api/cohort",
    "/api/delivery",
    "/api/quality/scorecard",
    "/api/quality/rules",
    "/api/quality/heatmap",
    "/api/quality/profile",
    "/api/quality/issues",
    "/api/duplicates",
    "/api/trust",
    "/api/commission",
    "/api/manifest",
    "/api/questions?limit=200",
    "/api/questions?segment=F&status=DONE&q=percentile",
    "/api/capstone",
    "/api/sql-list",
    "/api/sql-file/q100",
]

for ep in ENDPOINTS:
    try:
        st, body, headers = get(ep)
        text = body.decode("utf-8")
        json_ok = True
        try:
            json.loads(text)
        except Exception as e:
            json_ok = False
            print(f"     bad json: {e}")
        no_nan = ("NaN" not in text) and ("Infinity" not in text)
        ok = st == 200 and json_ok and no_nan
        if not ok:
            failures += 1
        print(f"[{'OK ' if ok else 'FAIL'}] {ep} -> {st} json={json_ok} no-nan={no_nan} len={len(text)}")
    except Exception as e:
        failures += 1
        print(f"[FAIL] {ep} -> {e}")

print()
print("=== privacy spot-check (no emails / long digit runs / raw customer ids) ===")
import re

leak = False
for ep in [
    "/api/duplicates",
    "/api/top-customers?n=50",
    "/api/questions?limit=200",
    "/api/quality/issues",
    "/api/sql-file/q54",
    "/api/sql-file/q61",
    "/api/sql-file/q100",
    "/api/manifest",
    "/api/capstone",
]:
    _, body, _ = get(ep)
    text = body.decode("utf-8")
    emails = re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text)
    long_digits = re.findall(r"\b\d{10,}\b", text)
    raw_ids = re.findall(r"\bC\d{3,4}\b", text)
    if emails or long_digits or raw_ids:
        leak = True
        print(f"[LEAK] {ep}: emails={emails[:3]} digits={long_digits[:3]} raw_ids={raw_ids[:3]}")
    else:
        print(f"[OK ] {ep}: no emails / digit runs / raw ids")
if leak:
    failures += 1

print()
print("=== KPI cross-check vs source files ===")
import pandas as pd

kpis = json.loads(get("/api/kpis")[1])
sales = pd.read_csv(DATA / "sales_datamart.csv")
report = pd.read_csv(DATA / "report_validation.csv")
checks = [
    ("delivered_value == sales_datamart total", kpis["delivered_value"], float(sales["value"].sum())),
    ("delivered_orders == sales_datamart orders", kpis["delivered_orders"], int(sales["orders"].sum())),
    ("delivered_orders == report_validation 799", kpis["delivered_orders"], 799.0),
    ("aov == value / orders", kpis["avg_order_value"], round(float(sales["value"].sum()) / int(sales["orders"].sum()), 2)),
    ("leakage == commission_datamart", kpis["commission_leakage"], 7756.28),
]
for name, got, want in checks:
    ok = abs(float(got) - float(want)) < 0.011
    if not ok:
        failures += 1
    print(f"[{'OK ' if ok else 'FAIL'}] {name}: got={got} want={want}")

print()
print("TOTAL FAILURES:", failures)
sys.exit(1 if failures else 0)
