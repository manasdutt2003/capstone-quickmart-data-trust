"""Tests for the Sprint 3 rule framework (stubs only, no rule bodies)."""

import pandas as pd

from src.validation_rules import (
    REGISTRY,
    RULE_DEFINITIONS,
    Context,
    Rule,
    RuleResult,
    build_registry,
    evaluate_all,
    evaluate_rule,
)


def _ctx():
    empty = pd.DataFrame()
    return Context(customers=empty, products=empty, city_map={}, cat_map={},
                   pay_map={}, status_map={})


def _orders():
    return pd.DataFrame([
        {"order_id": "O1", "_source_row": 1, "customer_id": "C1",
         "product_id": "P1", "order_date": "2024-02-01", "quantity": "2",
         "unit_price_paid": "100", "discount": "0", "payment_mode": "UPI",
         "order_status": "Delivered", "delivery_days": "3"},
        {"order_id": "O2", "_source_row": 2, "customer_id": "C1",
         "product_id": "P1", "order_date": "2024-02-01", "quantity": "2",
         "unit_price_paid": "100", "discount": "0", "payment_mode": "UPI",
         "order_status": "Delivered", "delivery_days": "3"},
        {"order_id": "O3", "_source_row": 3, "customer_id": "C1",
         "product_id": "P1", "order_date": "2024-02-01", "quantity": "2",
         "unit_price_paid": "100", "discount": "0", "payment_mode": "UPI",
         "order_status": "Delivered", "delivery_days": "3"},
    ])


def test_registry_has_all_rules_once():
    assert len(REGISTRY) == 12
    assert {r.rule_id for r in RULE_DEFINITIONS} == {f"R{i:02d}" for i in range(1, 13)}


def test_registry_rejects_duplicate_rule_id():
    dup = list(RULE_DEFINITIONS) + [RULE_DEFINITIONS[0]]
    try:
        build_registry(dup)
    except ValueError:
        return
    raise AssertionError("duplicate rule_id did not raise")


def test_rule_metadata_complete():
    for rule in RULE_DEFINITIONS:
        assert isinstance(rule, Rule)
        assert rule.rule_id and rule.name and rule.predicate_text
        assert rule.fields_used and rule.files_joined and rule.rationale
        assert rule.severity in ("FAIL", "WARNING")
        assert rule.treatment in ("set_aside", "flag", "correct")


def test_result_series_index_equals_input_index():
    orders = _orders()
    series = evaluate_rule(RULE_DEFINITIONS[0], orders, _ctx())
    assert series.index.equals(orders.index)
    assert set(series.unique()) <= {r.value for r in RuleResult}
    assert RuleResult.PASS.value == "PASS"


def test_evaluate_all_columns_and_sort():
    out = evaluate_all(_orders(), _ctx())
    assert list(out.columns) == ["source_row_number", "rule_id", "result",
                                 "failing_detail"]
    assert len(out) == 3 * 12
    assert out["source_row_number"].tolist() == sorted(out["source_row_number"].tolist())
    assert (out.groupby("source_row_number")["rule_id"].apply(list).apply(
        lambda ids: ids == sorted(ids)).all())


def test_evaluate_all_deterministic_under_shuffle():
    orders = _orders()
    ctx = _ctx()
    first = evaluate_all(orders, ctx)
    shuffled = orders.sample(frac=1, random_state=7)
    second = evaluate_all(shuffled, ctx)
    pd.testing.assert_frame_equal(first, second)
