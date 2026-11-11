"""Dashboard gates: payload shape, chart==table, PII, URLs, size, determinism."""

import hashlib
import html as html_mod
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _payload() -> dict:
    return json.loads((ROOT / "dashboard" / "data.json").read_text(
        encoding="utf-8"))


def _html() -> str:
    return (ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")


def _chart_block(html_text: str, cid: str) -> object:
    pattern = (
        rf'<script type="application/json" id="{re.escape(cid)}">(.*?)</script>')
    m = re.search(pattern, html_text, re.DOTALL)
    assert m, f"chart block {cid} missing"
    return json.loads(html_mod.unescape(m.group(1)))


def test_payload_counts():
    data = _payload()
    assert len(data["questions"]) == 125
    assert len(data["criteria"]) == 23
    assert len(data["rules"]["rules"]) == 12
    assert len(data["problems"]) == 5


def test_insight_figures_in_payload():
    from src import llm_insights as li
    data = _payload()
    marts = li.load_marts()
    allowed = li.mart_values(marts)
    for ins in data["insights"]["insights"]:
        for fig in ins["figures"]:
            v = round(float(fig["value"]), 2)
            assert any(abs(v - a) <= 0.01 for a in allowed), (
                ins["title"], fig)
            assert str(fig["value"]) in _html()


def test_charts_equal_tables():
    data = _payload()
    html_text = _html()
    monthly = _chart_block(html_text, "chart-monthly")
    assert [(r["k"], r["v"]) for r in monthly] == [
        (r["month"], r["value"]) for r in data["series"]["monthly"]]
    for r in data["series"]["monthly"]:
        assert r["month"] in html_text
        assert f"{r['value']:,.2f}" in html_text
    rules = _chart_block(html_text, "chart-rules")
    assert [(r["k"], r["v"]) for r in rules] == [
        (x["id"], x["failing"]) for x in data["rules"]["rules"]]
    wfall = _chart_block(html_text, "chart-waterfall")
    assert wfall[0]["v"] == 6103
    assert wfall[-1]["v"] == data["headline"]["strict"]["rows"]


def test_pii_scan_dashboard_reports():
    from src.criteria_check import scan_text
    hits = []
    for folder in ("dashboard", "reports"):
        for path in sorted((ROOT / folder).rglob("*")):
            if not path.is_file() or path.suffix not in (
                    ".html", ".json", ".md"):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            found = scan_text(text)
            if found:
                hits.append(f"{path.relative_to(ROOT)}:{found[0]}")
    assert hits == [], hits


def test_no_external_urls():
    html_text = _html()
    stripped = re.sub(r"<!--.*?-->", "", html_text, flags=re.DOTALL)
    assert "http://" not in stripped
    assert "https://" not in stripped


def test_size_and_determinism():
    from src import dashboard as renderer
    first = (ROOT / "dashboard" / "index.html").read_bytes()
    assert len(first) < 3 * 1024 * 1024
    data = json.loads((ROOT / "dashboard" / "data.json").read_text(
        encoding="utf-8"))
    assert "timestamp" not in [k.lower() for k in data]
    blob = json.dumps(data, sort_keys=True)
    assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:", blob)
    page = renderer.render(data)
    canonical = json.dumps(data, sort_keys=True)
    page = page.replace("__PAYLOAD__", canonical.replace("</", "<\\/"))
    second = page.encode("utf-8")
    assert hashlib.sha256(first).hexdigest() == \
        hashlib.sha256(second).hexdigest()


def test_criteria_checks_are_executed():
    from src import criteria_check as cc
    called: list[int] = []
    originals = {cid: entry[5] for cid, entry in cc.TEXTS.items()}

    def spy(cid: int) -> object:
        func = originals[cid]

        def wrapper(runner: object) -> tuple[str, str]:
            called.append(cid)
            return func(runner)  # type: ignore[arg-type]

        return wrapper

    for cid, entry in cc.TEXTS.items():
        cc.TEXTS[cid] = (*entry[:5], spy(cid))
    try:
        result = cc.run_all(
            runner=lambda cmd: (0, "ok"))  # type: ignore[arg-type]
    finally:
        for cid, entry in cc.TEXTS.items():
            cc.TEXTS[cid] = (*entry[:5], originals[cid])
    assert sorted(called) == sorted(cc.TEXTS), (
        f"not every check ran: missing "
        f"{sorted(set(cc.TEXTS) - set(called))}")
    assert len(result["checks"]) == 23
    assert "run_hash" in result and len(result["run_hash"]) == 64
