"""LLM insights: aggregated-only input, verifier catches inventions."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_model_input_has_no_pii():
    from src import llm_insights as li
    marts = li.load_marts()
    payload = li.build_model_input(marts)
    li.assert_no_pii(payload)
    low = payload.lower()
    for word in ("customer_name", "phone", "email", "notes"):
        assert f'"{word}"' not in low and f"{word}:" not in low


def test_verifier_catches_invented_figure():
    from src import llm_insights as li
    marts = li.load_marts()
    allowed = li.mart_values(marts)
    bad = {"title": "Planted", "claim": "Sales hit Rs 9,999,999.99.",
           "so_what": "Trap.",
           "figures": [{"value": 9999999.99, "mart": "sales_datamart",
                         "row_key": "grand_total"}],
           "confidence": "high"}
    status, reason = li.verify_insight(bad, allowed)
    assert status == "UNVERIFIED"
    assert "matches no mart value" in reason


def test_rule_based_insights_all_verified_and_deterministic():
    from src import llm_insights as li
    marts = li.load_marts()
    first = li.rule_based_insights(marts)
    second = li.rule_based_insights(marts)
    assert (li.sha256_text(json.dumps(first, sort_keys=True))
            == li.sha256_text(json.dumps(second, sort_keys=True)))
    allowed = li.mart_values(marts)
    assert 8 <= len(first) <= 10
    for ins in first:
        status, _ = li.verify_insight(ins, allowed)
        assert status == "VERIFIED", ins["title"]


def test_committed_insights_verify():
    from src import llm_insights as li
    doc = json.loads((ROOT / "reports" / "llm_insights.json").read_text(
        encoding="utf-8"))
    assert len(doc["insights"]) >= 8
    assert doc.get("rejected", []) == [] or isinstance(
        doc.get("rejected"), list)
    marts = li.load_marts()
    allowed = li.mart_values(marts)
    for ins in doc["insights"]:
        status, _ = li.verify_insight(ins, allowed)
        assert status == "VERIFIED", ins["title"]
    rec = json.loads((ROOT / "reports" / "llm_run_record.json").read_text(
        encoding="utf-8"))
    for key in ("model", "temperature", "seed", "prompt_sha256",
                "input_sha256"):
        assert key in rec


def test_model_run_refuses_without_go():
    import pytest

    from src import llm_insights as li

    with pytest.raises(RuntimeError, match="go"):
        li.run_model("{}")
