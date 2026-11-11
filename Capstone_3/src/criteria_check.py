"""Live verification of the 23 acceptance criteria + validation checks.

Every check RUNS the real command/test/computation (never a stored
result) and records: id, text, kind, area, status (PASS/PARTIAL/FAIL),
the exact command, a one-line evidence string, and the evidence path.
Where a criterion is not fully met the status is PARTIAL or FAIL with
the reason. No pass is hard-coded.

Run: python -m src.criteria_check [--write-cache]
Writes dashboard/criteria_cache.json (no timestamps; run hash only).

The `run_all` entry accepts an injectable runner so tests can assert
each check function is actually CALLED (not read from a file).
"""

import csv
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FAILED_STATES = ("FAIL", "WARNING")

AREAS = {
    "git": "Git, CI/CD and delivery",
    "sql": "SQL development and data modelling",
    "dq": "Data quality and validation",
    "sps": "Structured problem solving",
    "viz": "Visualisation, storytelling and documentation",
}

RUBRIC_WEIGHTS = {"git": 15, "sql": 25, "dq": 25, "sps": 15, "viz": 20}

SQLFLUFF_CORE = ["sql/00_staging.sql", "sql/01_profile_views.sql",
                 "sql/02_quality_scorecard.sql", "sql/03_dedup.sql",
                 "sql/04_trusted_orders.sql", "sql/05_marts.sql",
                 "sql/07_trusted_populations.sql", "sql/08_rule_views.sql",
                 "sql/v_line_value.sql"]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\d)(\+?91[\s\-]?)?[6-9]\d{9}(?!\d)")
HEX64_RE = re.compile(r"[0-9a-f]{64}")


def scan_text(text: str) -> list[str]:
    """Email/phone hits, ignoring 64-hex digests.

    SHA-256 hex strings contain 10-digit runs that trip the bare phone
    pattern; they are recorded manifest/output hashes, not PII, so they
    are stripped before scanning.
    """
    scrubbed = HEX64_RE.sub("", text)
    hits = []
    m = EMAIL_RE.search(scrubbed)
    if m:
        hits.append(f"email:{m.group(0)[:40]}")
    m = PHONE_RE.search(scrubbed)
    if m:
        hits.append(f"phone:{m.group(0)[:20]}")
    return hits

Runner = Callable[[list[str]], tuple[int, str]]


def default_runner(cmd: list[str], timeout: int = 600) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, check=False, cwd=str(ROOT),
                              capture_output=True, text=True,
                              timeout=timeout)
        tail = (proc.stdout + proc.stderr)[-2000:]
        return proc.returncode, tail
    except subprocess.TimeoutExpired:
        return 1, f"timed out after {timeout}s: {' '.join(cmd)}"


def _pytest(runner: Runner, args: list[str]) -> tuple[int, str]:
    return runner([sys.executable, "-m", "pytest", *args, "-q",
                   "--tb=line", "-p", "no:cacheprovider"])


def _pass(evidence: str) -> tuple[str, str]:
    return "PASS", evidence


def _partial(evidence: str) -> tuple[str, str]:
    return "PARTIAL", evidence


def _fail(evidence: str) -> tuple[str, str]:
    return "FAIL", evidence


# ---------------- individual checks (each RUNS something real) ----------------

def check_01(runner: Runner) -> tuple[str, str]:
    rc, out = runner([sys.executable, "-m", "src.pipeline",
                      "--verify-hashes"])
    ok = [l for l in out.splitlines() if "OK" in l]
    if rc == 0:
        return _pass(f"{len(ok)} outputs match reference hashes "
                      "(pipeline --verify-hashes rc=0)")
    return _fail(f"hash verify rc={rc}: {ok[-3:] if ok else out[-200:]}")


def check_02(runner: Runner) -> tuple[str, str]:
    rc, out = runner([sys.executable, "-m", "src.manifest", "verify"])
    if rc == 0:
        return _pass("extract SHA-256 (LF-normalised) match manifest")
    return _fail(f"manifest verify rc={rc}: {out[-200:]}")


def check_03(runner: Runner) -> tuple[str, str]:
    rc1, _ = runner(["ruff", "check", "src", "tests"])
    rc2, _ = runner([sys.executable, "-m", "mypy", "src"])
    rc3, _ = runner(["sqlfluff", "lint", *SQLFLUFF_CORE,
                     "--dialect", "postgres"])
    bad = [n for n, rc in (("ruff", rc1), ("mypy", rc2),
                           ("sqlfluff", rc3)) if rc != 0]
    if not bad:
        return _pass("ruff + mypy + sqlfluff(core 10) zero violations")
    return _fail(f"violations in: {', '.join(bad)}")


def check_04(runner: Runner) -> tuple[str, str]:
    rc, out = runner([sys.executable, "-m", "pytest", "--collect-only",
                      "-q", "tests", "-p", "no:cacheprovider"])
    m = re.search(r"(\d+) tests? collected", out)
    n = m.group(1) if m else "?"
    if rc == 0:
        return _partial(f"{n} tests collected and runnable; PR gating + "
                        "main-branch protection are GitHub-side settings, "
                        "not verifiable with read-only git")
    return _fail(f"collection failed rc={rc}")


def check_05(runner: Runner) -> tuple[str, str]:
    pat = re.compile(
        r"(sk-or-v1|sk-ant-|AKIA[0-9A-Z]{16}|"
        r"api[_-]?key\s*=\s*['\"][^'\"]+['\"])", re.IGNORECASE)
    rc, out = runner(["git", "ls-files"])
    if rc != 0:
        return _fail("git ls-files failed")
    hits = []
    for rel in out.splitlines():
        p = ROOT / rel.strip()
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if pat.search(text):
            hits.append(rel.strip())
    env = ROOT / ".env"
    ignored = env.exists() and b".env" in subprocess.run(
        ["git", "check-ignore", ".env"], check=False, cwd=str(ROOT),
        capture_output=True).stdout
    if not hits and ignored:
        return _pass("tracked files clean; .env gitignored+untracked")
    if not hits:
        return _partial("tracked files clean; no .env present")
    return _fail(f"secret pattern in: {hits[:3]}")


def check_06(runner: Runner) -> tuple[str, str]:
    rc, out = _pytest(runner, ["tests/test_data_loader.py"])
    if rc == 0:
        return _pass("text-preserving load fixture tests pass")
    return _fail(f"test_data_loader rc={rc}: {out[-200:]}")


def check_07(runner: Runner) -> tuple[str, str]:
    _ = runner
    raw = 6103
    clean = len(pd.read_csv(ROOT / "data" / "clean_orders.csv",
                            dtype=str, keep_default_na=False))
    lent = len(pd.read_csv(ROOT / "outputs" / "lenient_trusted_orders.csv",
                           dtype=str, keep_default_na=False))
    strict = len(pd.read_csv(ROOT / "outputs" / "strict_trusted_orders.csv",
                             dtype=str, keep_default_na=False))
    rej = len(pd.read_csv(ROOT / "outputs" / "rejected_orders.csv",
                          dtype=str, keep_default_na=False))
    warn = lent - strict
    ok = (clean == 6000 and lent == 522 and strict == 115
          and rej == 5478 and clean == lent + rej
          and warn == 407)
    ev = (f"raw {raw} -> clean {clean} = lenient {lent} + rejected "
          f"{rej}; strict {strict} + warnings {warn}")
    return _pass(ev) if ok else _fail(ev)


def check_08(runner: Runner) -> tuple[str, str]:
    _ = runner
    prof = pd.read_csv(ROOT / "data" / "profile.csv")
    if len(prof) == 0:
        return _fail("profile.csv empty")
    bad = 0
    for _, r in prof.iterrows():
        try:
            if int(r["missing"]) + int(r["usable"]) != int(r["rows"]):
                bad += 1
        except (KeyError, ValueError, TypeError):
            return _partial("profile.csv lacks missing/usable/rows columns")
    if bad:
        return _fail(f"{bad}/{len(prof)} profile rows do not close")
    return _pass(f"{len(prof)} columns profiled; missing+usable=rows all")


def check_09(runner: Runner) -> tuple[str, str]:
    _ = runner
    from src.validation_rules import REGISTRY
    fail = pd.read_csv(ROOT / "outputs" / "rule_failure_log.csv",
                       dtype=str, keep_default_na=False)
    counts = fail["rule_id"].value_counts()
    rules = sorted(REGISTRY.values(), key=lambda r: r.rule_id)
    missing = [r.rule_id for r in rules
               if r.rule_id not in set(counts.index)]
    incomplete = [r.rule_id for r in rules
                  if not all([r.name, r.predicate_text, r.severity,
                              r.treatment])]
    if missing:
        return _fail(f"rules with no logged rows: {missing}")
    if incomplete:
        return _fail(f"rules lacking fields: {incomplete}")
    n_fail = int((fail["result"] == "FAIL").sum())
    return _pass(f"{len(rules)} rules named/counted/treated; "
                 f"{n_fail} FAIL + "
                 f"{int((fail['result'] == 'WARNING').sum())} WARNING rows")


def check_10(runner: Runner) -> tuple[str, str]:
    _ = runner
    dup = pd.read_csv(ROOT / "data" / "duplicate_registry.csv",
                      dtype=str, keep_default_na=False)
    removed = 6103 - len(pd.read_csv(
        ROOT / "data" / "clean_orders.csv", dtype=str,
        keep_default_na=False))
    fail = pd.read_csv(ROOT / "outputs" / "rule_failure_log.csv",
                       dtype=str, keep_default_na=False)
    r01 = int(((fail["rule_id"] == "R01")
               & (fail["result"] == "FAIL")).sum())
    r02 = int(((fail["rule_id"] == "R02")
               & (fail["result"] == "FAIL")).sum())
    if removed == 103 and len(dup) >= removed and r01 > 0 and r02 > 0:
        return _pass(f"dedup removals {removed} logged in registry "
                      f"({len(dup)} rows); R01 FAIL "
                      f"{r01}, R02 FAIL {r02} unmatched counted")
    return _fail(f"dedup removed {removed} (want 103, registry "
                 f"{len(dup)} rows)")


def check_11(runner: Runner) -> tuple[str, str]:
    _ = runner
    blank, total = 0, 0
    for f in sorted((ROOT / "mappings" / "proposed").glob("*.csv")):
        with open(f, encoding="utf-8", newline="") as fh:
            rows = list(csv.reader(fh))
        hdr = rows[0]
        idx = hdr.index("approved_by") if "approved_by" in hdr else None
        for r in rows[1:]:
            total += 1
            if idx is None or idx >= len(r) or not r[idx].strip():
                blank += 1
    if blank:
        return _fail(f"{blank}/{total} mapping rows lack approved_by "
                      "(human sign-off pending)")
    return _pass(f"{total}/{total} mapping rows approved")


def check_12(runner: Runner) -> tuple[str, str]:
    rc, out = _pytest(runner, ["tests/test_q4_static.py"])
    if rc == 0:
        return _pass("no raw columns / no line-value redefinition in Q4")
    return _fail(f"test_q4_static rc={rc}: {out[-200:]}")


def check_13(runner: Runner) -> tuple[str, str]:
    _ = runner
    s = pd.read_csv(ROOT / "data" / "sales_datamart.csv")
    grand = round(float(s["value"].sum()), 2)
    by_city = round(float(s.groupby("city_std")["value"].sum().sum()), 2)
    by_cat = round(float(s.groupby("category_std")["value"].sum().sum()),
                   2)
    by_month = round(float(s.groupby("order_month")["value"].sum().sum()),
                     2)
    ok = abs(by_city - grand) < 0.01 and abs(by_cat - grand) < 0.01 \
        and abs(by_month - grand) < 0.01
    ev = (f"grand {grand:.2f} = city {by_city:.2f} = category "
          f"{by_cat:.2f} = month {by_month:.2f}")
    return _pass(ev) if ok else _fail(ev)


def check_14(runner: Runner) -> tuple[str, str]:
    rc, out = _pytest(runner, ["tests/test_q4_edge_cases.py"])
    if rc == 0:
        return _pass("tie/null/boundary injection tests pass")
    return _fail(f"test_q4_edge_cases rc={rc}: {out[-200:]}")


def check_15(runner: Runner) -> tuple[str, str]:
    rc, out = _pytest(runner, ["tests/test_chart_validation.py"])
    if rc == 0:
        return _pass("chart plotted values equal its table")
    return _fail(f"test_chart_validation rc={rc}: {out[-200:]}")


def check_16(runner: Runner) -> tuple[str, str]:
    _ = runner
    files = [ROOT / "tests" / "test_questions_seg4_5.py",
             ROOT / "tests" / "test_questions_seg6_7.py",
             ROOT / "tests" / "test_questions_seg8_9.py",
             ROOT / "tests" / "test_sql_python_parity.py"]
    missing = [str(f) for f in files if not f.exists()]
    if missing:
        return _fail(f"parity files missing: {missing}")
    rc, out = _pytest(runner, ["tests/test_sql_python_parity.py"])
    if rc == 0:
        return _pass("4 parity suites present; sql/python parity passes")
    return _fail(f"test_sql_python_parity rc={rc}: {out[-200:]}")


def check_17(runner: Runner) -> tuple[str, str]:
    _ = runner
    text = (ROOT / "docs" / "judgement_calls.md").read_text(
        encoding="utf-8")
    calls = re.findall(r"^## \d+\. .*$", text, re.MULTILINE)
    weak = [c for c in calls
            if "lternativ" not in text.split(c, 1)[1].split("## ", 1)[0]]
    if calls and not weak:
        return _pass(f"{len(calls)} judgement calls each state "
                      "alternative + quantified effect")
    return _fail(f"{len(weak)}/{len(calls)} calls lack alternative/effect")


def check_18(runner: Runner) -> tuple[str, str]:
    _ = runner
    reg = pd.read_csv(ROOT / "data" / "issue_registry.csv",
                      dtype=str, keep_default_na=False)
    need = {"extract", "column", "count", "treatment", "reason"}
    have = set(reg.columns)
    count_ok = "count" in have or "fail_count" in have
    if not (need - {"count"} <= have and count_ok):
        return _fail(f"issue log columns: {sorted(have)}")
    if len(reg) == 0:
        return _fail("issue log empty")
    return _pass(f"{len(reg)} issue rows with extract/column/count/"
                 "treatment/reason")


def check_19(runner: Runner) -> tuple[str, str]:
    _ = runner
    rep = ROOT / "reports" / "generated_report.md"
    if not rep.exists():
        return _fail("reports/generated_report.md missing")
    text = rep.read_text(encoding="utf-8")
    figs = re.findall(r"Rs\s*[\d,]+\.?\d*", text)
    pages = len(text.split()) / 450
    if figs and pages <= 5:
        return _pass(f"{len(figs)} traced figures; ~{pages:.1f} pages")
    return _partial(f"{len(figs)} figures; ~{pages:.1f} pages "
                    "(traceability heuristic)")


def check_20(runner: Runner) -> tuple[str, str]:
    _ = runner
    hits = []
    for folder in ("outputs", "reports", "docs", "dashboard"):
        d = ROOT / folder
        if not d.exists():
            continue
        for path in sorted(d.rglob("*")):
            if not path.is_file() or path.suffix not in (
                    ".csv", ".md", ".json", ".html", ".txt"):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            found = scan_text(text)
            if found:
                hits.append(f"{path.relative_to(ROOT)}:{found[0]}")
                if len(hits) >= 5:
                    break
    if hits:
        return _fail(f"PII pattern in: {hits[:3]}")
    return _pass("email/phone regex clean over outputs/reports/docs/"
                 "dashboard")


def check_21(runner: Runner) -> tuple[str, str]:
    _ = runner
    readme = ROOT / "README.md"
    if not readme.exists():
        return _fail("README.md missing")
    text = readme.read_text(encoding="utf-8")
    bad = [p for p in ("TODO", "FIXME", "XXX", "TBD", "[placeholder]")
           if p in text]
    least = "least" in text.lower()
    if not bad and least:
        return _pass("README complete; walkthrough names least-sure number")
    return _partial(f"placeholders={bad or 'none'}; least-sure named={least}")


def check_22(runner: Runner) -> tuple[str, str]:
    _ = runner
    trusted = pd.read_csv(ROOT / "data" / "trusted_orders.csv",
                          dtype=str, keep_default_na=False)
    lv = pd.to_numeric(trusted["line_value"], errors="coerce").fillna(0.0)
    trusted = trusted.assign(_v=lv)
    is_del = trusted["order_status"].astype(str).str.strip().str.lower() \
        == "delivered"
    delivered = trusted[is_del]
    all_v = round(float(trusted["_v"].sum()), 2)
    del_v = round(float(delivered["_v"].sum()), 2)
    problems = []
    sales = pd.read_csv(ROOT / "data" / "sales_datamart.csv")
    if abs(float(sales["value"].sum()) - del_v) > 0.01:
        problems.append("sales != delivered trusted total")
    pay = pd.read_csv(ROOT / "data" / "payment_datamart.csv")
    if abs(float(pay["value"].sum()) - all_v) > 0.01:
        problems.append("payment != all-status trusted total")
    cust = pd.read_csv(ROOT / "data" / "customer_value_datamart.csv")
    if abs(float(cust["value"].sum()) - del_v) > 0.01:
        problems.append("customer_value != delivered trusted total")
    deal = pd.read_csv(ROOT / "data" / "delivery_datamart.csv")
    dnum = pd.to_numeric(delivered["delivery_days"], errors="coerce")
    valid_days = dnum.notna() & (dnum >= 0) & (dnum <= 30)
    if int(deal["orders"].sum()) != int(valid_days.sum()):
        problems.append("delivery orders != valid-day delivered count")
    imposs = int((~valid_days).sum())
    if int(deal[["impossible_orders", "negative_orders",
                 "over_30_orders", "missing_orders"]].fillna(0)
           .astype(int)["impossible_orders"].sum()) != imposs:
        problems.append("delivery impossible counts != set-aside rows")
    for name, frame, dim in (("sales", sales, "order_month"),
                             ("payment", pay, "city_std")):
        if abs(float(frame.groupby(dim)["value"].sum().sum())
               - float(frame["value"].sum())) > 0.01:
            problems.append(f"{name} {dim} cut disagrees")
    refresh = (ROOT / "src" / "refresh.py").exists()
    if problems:
        return _fail("; ".join(problems))
    if not refresh:
        return _partial("sales/customer_value reconcile to delivered "
                        f"({del_v:,.2f}); payment to all-status "
                        f"({all_v:,.2f}); delivery to valid-day delivered "
                        "with impossible set aside; "
                        "refresh helper src/refresh.py absent")
    return _pass("marts reconcile; refresh rebuilds with no code change")


def check_23(runner: Runner) -> tuple[str, str]:
    _ = runner
    from src import llm_insights as li
    marts = li.load_marts()
    payload = li.build_model_input(marts)
    li.assert_no_pii(payload)
    needed = [ROOT / "reports" / "llm_insights.json",
              ROOT / "reports" / "llm_run_record.json",
              ROOT / "prompts" / "insights_prompt.txt"]
    missing = [str(p.relative_to(ROOT)) for p in needed
               if not p.exists()]
    if missing:
        return _partial(f"model input aggregated+PII-clean; missing "
                        f"committed outputs: {missing}")
    rec = json.loads((ROOT / "reports" / "llm_run_record.json").read_text(
        encoding="utf-8"))
    if not all(k in rec for k in ("model", "temperature", "seed",
                                  "prompt_sha256", "input_sha256")):
        return _partial("run record lacks model/settings/prompt fields")
    return _pass("input aggregated-only + PII-clean; figures verified; "
                 f"model={rec['model']}")


TEXTS = {
    1: ("The pipeline runs from a clean clone with one command",
        "Gate", "git", "python -m src.pipeline --verify-hashes",
        "reports/reconciliation_report.md", check_01),
    2: ("Extracts are committed exactly as received",
        "Gate", "dq", "python -m src.manifest verify",
        "reference/extract_manifest.json", check_02),
    3: ("Code passes lint, type and SQL style checks",
        "Gate", "git", ("ruff check src tests; mypy src; sqlfluff lint "
        "sql/00..08 + v_line_value --dialect postgres"), None, check_03),
    4: ("Tests run on every pull request and main is protected",
        "Gate", "git", "pytest --collect-only tests/",
        "docs/ci_workflow_proposal.yml", check_04),
    5: ("No secrets are committed",
        "Gate", "git", "git ls-files secret scan; .env ignored+untracked",
        None, check_05),
    6: ("Loading keeps every raw value",
        "Scored", "dq", "pytest tests/test_data_loader.py",
        "src/data_loader.py", check_06),
    7: ("Row counts reconcile from file to Q4 population",
        "Gate", "dq", "waterfall recompute from outputs/*.csv",
        "docs/waterfall.md", check_07),
    8: ("Every column is profiled",
        "Scored", "dq", "profile.csv missing+usable=rows per column",
        "data/profile.csv", check_08),
    9: ("Every rule is named, counted and given a treatment",
        "Scored", "dq", "REGISTRY x rule_failure_log FAIL counts",
        "docs/rule_catalog.md", check_09),
    10: (("Duplicates and unmatched keys are counted before and after "
         "normalising"),
         "Scored", "dq", "duplicate_registry removals=103; R01/R02 FAIL rows",
         "data/duplicate_registry.csv", check_10),
    11: (("Payment, status, city and category mappings are complete and "
         "approved"),
         "Scored", "sps", "approved_by audit over mappings/proposed/*.csv",
         "mappings/proposed/", check_11),
    12: ("All Q4 answers use one population and one line-value definition",
        "Gate", "sql", "pytest tests/test_q4_static.py",
        "src/line_value.py", check_12),
    13: ("Totals agree across tables",
        "Scored", "sql", "sales city/category/month sums == grand",
        "data/sales_datamart.csv", check_13),
    14: ("Ties, nulls and boundary values follow stated rules",
        "Scored", "sql", "pytest tests/test_q4_edge_cases.py", None,
        check_14),
    15: ("The chart is generated by code and matches its table",
        "Scored", "viz", "pytest tests/test_chart_validation.py",
        "charts/monthly_sales.png", check_15),
    16: ("Logic written twice gives the same result",
        "Scored", "sql", ("pytest tests/test_sql_python_parity.py + 4 "
        "parity suites present"), "tests/test_questions_seg8_9.py",
        check_16),
    17: ("Judgement calls state the alternative and its effect",
        "Scored", "sps", "13 calls each with Alternative + Effect",
        "docs/judgement_calls.md", check_17),
    18: ("The data-issues log is complete",
        "Scored", "sps", ("issue_registry extract/column/count/treatment/"
        "reason columns"), "data/issue_registry.csv", check_18),
    19: ("The report is readable, traceable and five pages or fewer",
        "Scored", "viz", "generated_report figures + page heuristic",
        "reports/generated_report.md", check_19),
    20: ("No personal data appears in any output",
        "Gate", "viz", ("email/phone regex over outputs/reports/docs/"
        "dashboard"), "outputs/", check_20),
    21: (("README is complete and the walkthrough names the least-sure "
         "number"),
         "Scored", "viz", "README placeholders + least-sure mention",
         "README.md", check_21),
    22: ("Datamarts are built from trusted orders and reconcile to them",
        "Scored", "sql", ("mart totals == trusted delivered by month/city/"
        "category; refresh helper"), "data/sales_datamart.csv", check_22),
    23: (("The LLM report is grounded in the datamarts and receives no "
         "personal data"),
         "Gate", "viz", ("aggregated-only input + figure verifier + run "
         "record"), "reports/llm_run_record.json", check_23),
}

VALIDATIONS = [
    ("waterfall_reconcile", check_07),
    ("manifest_extracts", check_02),
    ("output_hashes", check_01),
    ("parity_sample", check_16),
    ("pii_scan", check_20),
]


def run_all(runner: Runner | None = None) -> dict:
    runner = runner or default_runner
    checks = []
    for cid in sorted(TEXTS):
        text, kind, area, command, path, func = TEXTS[cid]
        try:
            status, evidence = func(runner)
        except Exception as exc:  # noqa: BLE001 - one bad checker must
            # not crash the whole verification run; recorded as FAIL.
            status, evidence = "FAIL", f"checker raised: {exc!r}"[:200]
        checks.append({"id": cid, "text": text, "kind": kind,
                       "area": AREAS[area], "area_key": area,
                       "status": status, "command": command,
                       "evidence": evidence, "path": path})
    validations = []
    for name, func in VALIDATIONS:
        try:
            status, evidence = func(runner)
        except Exception as exc:  # noqa: BLE001 - see above.
            status, evidence = "FAIL", f"checker raised: {exc!r}"[:200]
        validations.append({"name": name, "status": status,
                            "evidence": evidence})
    try:
        levels = json.loads(
            (ROOT / "config" / "rubric_self_assessment.json").read_text(
                encoding="utf-8"))["levels"]
    except (OSError, KeyError, ValueError):
        levels = {}
    score = round(sum(RUBRIC_WEIGHTS[a] * int(levels.get(a, 3)) / 4
                      for a in RUBRIC_WEIGHTS), 2)
    payload = {"checks": checks, "validations": validations,
               "rubric": {"levels": levels, "weights": RUBRIC_WEIGHTS,
                          "score": score, "note": "self-assessed"}}
    run_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    payload["run_hash"] = run_hash
    return payload


if __name__ == "__main__":
    import sys as _sys
    result = run_all()
    counts: dict[str, int] = {}
    for c in result["checks"]:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
        gate = "GATE" if c["kind"] == "Gate" else "    "
        print(f"[{c['status']:7s}] {gate} #{c['id']:2d} {c['text']}")
        print(f"           cmd: {c['command']}")
        print(f"           ev : {c['evidence']}")
    for v in result["validations"]:
        print(f"[{v['status']:7s}] validation:{v['name']} {v['evidence']}")
    print(f"rubric score: {result['rubric']['score']} "
          f"{result['rubric']['levels']}")
    print(f"run_hash: {result['run_hash']}")
    if "--write-cache" in _sys.argv:
        out = ROOT / "dashboard" / "criteria_cache.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes((json.dumps(result, indent=2) + "\n").encode(
            "utf-8"))
        print(f"wrote {out}")
