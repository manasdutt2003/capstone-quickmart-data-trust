"""Smoke-test every API endpoint with TestClient (no server needed).

Run from the dashboard folder:
    python tests/smoke_api.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

import main as m

client = TestClient(m.app)

ENDPOINTS = [
    "/api/health",
    "/api/meta",
    "/api/kpis",
    "/api/kpis?city=Bengaluru&month_from=2026-01&month_to=2026-10",
    "/api/monthly-sales",
    "/api/monthly-sales?city=Bengaluru",
    "/api/sales-cuts?dim=city",
    "/api/sales-cuts?dim=category",
    "/api/payment-mix",
    "/api/payment-mix?city=Chennai",
    "/api/top-customers?n=10&by=value",
    "/api/top-customers?n=5&by=orders",
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
    "/api/questions?limit=5",
    "/api/questions?segment=I&status=DONE&limit=5",
    "/api/capstone",
    "/api/sql-list",
    "/api/sql-file/q90",
]

failures = 0
for ep in ENDPOINTS:
    r = client.get(ep)
    ok = r.status_code == 200
    body = None
    json_ok = False
    if ok:
        try:
            body = json.loads(r.text)
            json_ok = True
        except Exception as e:
            print(f"[BAD JSON] {ep}: {e}")
    nan_ok = True
    if body is not None:
        text = r.text
        if "NaN" in text or "Infinity" in text:
            nan_ok = False
    status = "OK " if (ok and json_ok and nan_ok) else "FAIL"
    if status == "FAIL":
        failures += 1
    print(f"[{status}] {ep} -> {r.status_code} len={len(r.text)}{'' if nan_ok else ' HAS-NaN'}")

# key value checks
k = client.get("/api/kpis").json()
print()
print("KPIs:", {kk: k[kk] for kk in ("delivered_value", "delivered_orders", "avg_order_value", "trusted_lenient_rows", "commission_leakage")})
assert k["delivered_value"] == 2309394.0, "sales total mismatch"
assert k["delivered_orders"] == 799, "orders mismatch"

t = client.get("/api/trust").json()
print("trust:", t["lenient"], t["strict"], t["reconciliation"])
assert t["lenient"]["rows"] == 522 and t["lenient"]["value"] == 455160.75

rq = client.get("/api/questions?limit=125").json()
print("questions total:", rq["total"])
assert rq["total"] == 125, "question count mismatch"
rows = rq["rows"]
assert all(q["status"] == "DONE" for q in rows), "non-DONE question remains"
assert not any(q.get("pending_reason") for q in rows), "pending_reason on a question"
seg13 = [q for q in rows if q["id"] <= 29]
assert all(q["result_kind"] == "text" and q.get("result_text") for q in seg13), \
    "segment 1-3 result text missing"
assert not any(re.search(r"[\w.+\-]+@[\w\-]+\.[\w.\-]+",
                         (q.get("result_text") or "") + (q.get("headline") or ""))
               for q in rows), "email leak in API questions"
assert not any(re.search(r"\bC\d{3,4}\b",
                         (q.get("headline") or "") + (q.get("result_text") or ""))
               for q in rows), "raw C-id leak in API questions"
rn = client.get("/api/questions", params={"status": "NOT DONE"}).json()
assert rn["total"] == 0, "NOT DONE filter not empty"
rsearch = client.get("/api/questions", params={"q": "4,524,250"}).json()
assert any(x["id"] == 29 for x in rsearch["rows"]), "result-text search miss (Q29)"
print("questions: 125 DONE / 0 NOT DONE; seg1-3 text payloads; search ok")

print()
print("FAILURES:", failures)
sys.exit(1 if failures else 0)
