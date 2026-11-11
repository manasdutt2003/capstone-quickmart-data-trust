import pandas as pd

from src.validation_rules import RULES, evaluate, validate_orders


def _setup(status="Delivered", pay="UPI", qty="2", date="2024-02-01", dd="3"):
    c = pd.DataFrame([{"customer_id": "C1", "signup_date": "2024-01-01"}])
    p = pd.DataFrame([{"product_id": "P1", "unit_price": "100"}])
    o = pd.DataFrame([{"order_id": "O1", "customer_id": "C1",
                       "product_id": "P1", "order_date": date,
                       "quantity": qty, "unit_price_paid": "100",
                       "discount": "0", "payment_mode": pay,
                       "order_status": status, "delivery_days": dd,
                       "notes": ""}])
    return o, c, p


def test_happy_path_passes():
    o, c, p = _setup()
    _v, fail, lv = evaluate(o, c, p, pd.Series(["Delivered"], index=o.index),
                            pd.Series(["UPI"], index=o.index), "2026-10-11")
    assert not bool(fail.iloc[0])
    assert float(lv.iloc[0]) == 200.0


def test_boundary_and_negative():
    o, c, p = _setup(qty="0")
    _, fail, _ = evaluate(o, c, p, pd.Series(["Delivered"], index=o.index),
                          pd.Series(["UPI"], index=o.index), "2026-10-11")
    assert bool(fail.iloc[0])
    o2, _, _ = _setup(qty="100")
    _, fail2, _ = evaluate(o2, c, p, pd.Series(["Delivered"], index=o2.index),
                           pd.Series(["UPI"], index=o2.index), "2026-10-11")
    assert not bool(fail2.iloc[0])


def test_referential_and_business_rules():
    o, c, p = _setup(date="2023-01-01")
    v, fail, _ = evaluate(o, c, p, pd.Series(["Delivered"], index=o.index),
                          pd.Series(["UPI"], index=o.index), "2026-10-11")
    assert v.loc[o.index[0], "R03"] == False
    assert bool(fail.iloc[0])


def test_all_rules_named_with_severity():
    names = [r["rule_id"] for r in RULES]
    assert len(names) == 11 and len(set(names)) == 11


def test_warning_does_not_fail():
    c = pd.DataFrame([{"customer_id": "C1", "signup_date": "2024-01-01"}])
    p = pd.DataFrame([{"product_id": "P1", "unit_price": "100"}])
    o = pd.DataFrame([{"order_id": "O1", "customer_id": "C1",
                       "product_id": "P1", "order_date": "2024-02-01",
                       "quantity": "1", "unit_price_paid": "1000",
                       "discount": "0", "payment_mode": "UPI",
                       "order_status": "Delivered", "delivery_days": "3",
                       "notes": ""}])
    v, fail, _ = evaluate(o, c, p, pd.Series(["Delivered"], index=o.index),
                          pd.Series(["UPI"], index=o.index), "2026-10-11")
    assert v.loc[o.index[0], "R10"] == False
    assert not bool(fail.iloc[0])


def test_validate_orders_structure():
    o, c, p = _setup()
    res = validate_orders(o, c, p, {}, {}, {}, {})
    for key in ["trusted_orders", "rejected_orders", "warning_orders",
                "rule_failure_log", "validation_datamart"]:
        assert key in res


def test_r01_customer_exists():
    o, c, p = _setup()
    o.loc[0, "customer_id"] = "GHOST"
    res = validate_orders(o, c, p, {}, {}, {}, {})
    assert len(res["rejected_orders"]) == 1


def test_r02_product_exists():
    o, c, p = _setup()
    o.loc[0, "product_id"] = "GHOST"
    res = validate_orders(o, c, p, {}, {}, {}, {})
    assert len(res["rejected_orders"]) == 1


def test_r04_valid_order_date():
    o, c, p = _setup(date="2027-01-01")
    res = validate_orders(o, c, p, {}, {}, {}, {})
    assert len(res["rejected_orders"]) == 1


def test_r05_valid_quantity():
    o, c, p = _setup(qty="-1")
    res = validate_orders(o, c, p, {}, {}, {}, {})
    assert len(res["rejected_orders"]) == 1


def test_r08_valid_status():
    o, c, p = _setup(status="MISSING")
    res = validate_orders(o, c, p, {}, {}, {}, {})
    assert len(res["rejected_orders"]) == 1


def test_r11_valid_payment():
    o, c, p = _setup(pay="UNMAPPED")
    res = validate_orders(o, c, p, {}, {}, {}, {})
    assert len(res["warning_orders"]) + len(res["trusted_orders"]) == 1
    assert len(res["rejected_orders"]) == 0


def test_rule_catalog_complete():
    assert {r["rule_id"] for r in RULES} == {"R01", "R02", "R03", "R04", "R05",
                                            "R06", "R07", "R08", "R09",
                                            "R10", "R11"}


def test_rule_severities():
    assert [r["rule_id"] for r in RULES if r["severity"] == "FAIL"] == \
        ["R01", "R02", "R03", "R04", "R05", "R06", "R08"]
    assert [r["rule_id"] for r in RULES if r["severity"] == "WARNING"] == \
        ["R07", "R09", "R10", "R11"]


def test_rule_failure_log_populated():
    o, c, p = _setup(date="2027-01-01")
    res = validate_orders(o, c, p, {}, {}, {}, {})
    log = res["rule_failure_log"]
    assert len(log) > 0
    assert "rule_id" in log.columns
    assert "rule_name" in log.columns
    assert "severity" in log.columns
    assert "description" in log.columns
    o = pd.DataFrame([{"order_id": "O1", "customer_id": "C1", "product_id": "P1",
                       "order_date": "2024-02-01", "quantity": "1", "unit_price_paid": "1000",
                       "discount": "0", "payment_mode": "UPI", "order_status": "Delivered",
                       "delivery_days": "3", "notes": ""}])
    v, fail, _ = evaluate(o, c, p, pd.Series(["Delivered"], index=o.index),
                          pd.Series(["UPI"], index=o.index), "2026-10-11")
    # R10 (price vs catalogue) is WARNING severity; high price (1000 vs 100) fails the check
    assert v.loc[o.index[0], "R10"] == False
    # WARNING-only failures don't make the overall fail_mask True
    assert not bool(fail.iloc[0])


def _ctx_for(customers, products):
    from src.validation_rules import Context
    return Context(customers=customers, products=products, city_map={},
                   cat_map={}, pay_map={}, status_map={})


def _orders_frame(rows):
    base = {"order_id": "O1", "customer_id": "C1", "product_id": "P1",
            "order_date": "2024-02-01", "quantity": "2",
            "unit_price_paid": "100", "discount": "0", "payment_mode": "UPI",
            "order_status": "Delivered", "delivery_days": "3", "notes": "",
            "_source_row": 1}
    return pd.DataFrame([dict(base, **r) for r in rows])


class TestR01Bodies:
    def test_exact_match_passes(self):
        from src.validation_rules import REGISTRY, evaluate_rule
        c = pd.DataFrame([{"customer_id": "C1", "signup_date": "2024-01-01"}])
        o = _orders_frame([{}])
        out = evaluate_rule(REGISTRY["R01"], o, _ctx_for(c, pd.DataFrame()))
        assert out.iloc[0] == "PASS"

    def test_normalised_rescue_passes(self):
        from src.validation_rules import _r01_customer_exists
        c = pd.DataFrame([{"customer_id": "C-1", "signup_date": "2024-01-01"}])
        o = _orders_frame([{"customer_id": "c 1"}])
        frame = _r01_customer_exists(o, _ctx_for(c, pd.DataFrame()))
        assert frame["result"].iloc[0] == "PASS"
        assert frame["failing_detail"].iloc[0] == "matched_normalised"

    def test_unmatched_fails(self):
        from src.validation_rules import REGISTRY, evaluate_rule
        c = pd.DataFrame([{"customer_id": "C1", "signup_date": "2024-01-01"}])
        o = _orders_frame([{"customer_id": "GHOST"}])
        out = evaluate_rule(REGISTRY["R01"], o, _ctx_for(c, pd.DataFrame()))
        assert out.iloc[0] == "FAIL"

    def test_empty_customer_fails(self):
        from src.validation_rules import _r01_customer_exists
        c = pd.DataFrame([{"customer_id": "", "signup_date": "2024-01-01"}])
        o = _orders_frame([{"customer_id": ""}])
        frame = _r01_customer_exists(o, _ctx_for(c, pd.DataFrame()))
        assert frame["result"].iloc[0] == "FAIL"

    def test_tie_rows_agree(self):
        from src.validation_rules import _r01_customer_exists
        c = pd.DataFrame([{"customer_id": "C1", "signup_date": "2024-01-01"}])
        o = _orders_frame([{"customer_id": "GHOST"}, {"customer_id": "GHOST"}])
        frame = _r01_customer_exists(o, _ctx_for(c, pd.DataFrame()))
        assert (frame["result"] == "FAIL").all()
        assert (frame["failing_detail"] == "unmatched_after_normalisation").all()


class TestR02Bodies:
    def test_exact_match_passes(self):
        from src.validation_rules import REGISTRY, evaluate_rule
        p = pd.DataFrame([{"product_id": "P1", "unit_price": "100"}])
        o = _orders_frame([{}])
        out = evaluate_rule(REGISTRY["R02"], o, _ctx_for(pd.DataFrame(), p))
        assert out.iloc[0] == "PASS"

    def test_normalised_rescue_passes(self):
        from src.validation_rules import _r02_product_exists
        p = pd.DataFrame([{"product_id": "p-01", "unit_price": "100"}])
        o = _orders_frame([{"product_id": "P01"}])
        frame = _r02_product_exists(o, _ctx_for(pd.DataFrame(), p))
        assert frame["result"].iloc[0] == "PASS"
        assert frame["failing_detail"].iloc[0] == "matched_normalised"

    def test_unmatched_fails(self):
        from src.validation_rules import REGISTRY, evaluate_rule
        p = pd.DataFrame([{"product_id": "P1", "unit_price": "100"}])
        o = _orders_frame([{"product_id": "GHOST"}])
        out = evaluate_rule(REGISTRY["R02"], o, _ctx_for(pd.DataFrame(), p))
        assert out.iloc[0] == "FAIL"

    def test_null_product_fails(self):
        from src.validation_rules import _r02_product_exists
        p = pd.DataFrame([{"product_id": "P1", "unit_price": "100"}])
        o = _orders_frame([{"product_id": ""}])
        frame = _r02_product_exists(o, _ctx_for(pd.DataFrame(), p))
        assert frame["result"].iloc[0] == "FAIL"


class TestR03Bodies:
    def test_same_day_passes(self):
        from src.validation_rules import REGISTRY, evaluate_rule
        c = pd.DataFrame([{"customer_id": "C1", "signup_date": "2024-02-01"}])
        o = _orders_frame([{"order_date": "2024-02-01"}])
        out = evaluate_rule(REGISTRY["R03"], o, _ctx_for(c, pd.DataFrame()))
        assert out.iloc[0] == "PASS"

    def test_before_signup_fails(self):
        from src.validation_rules import _r03_signup_before_order
        c = pd.DataFrame([{"customer_id": "C1", "signup_date": "2024-02-01"}])
        o = _orders_frame([{"order_date": "2024-01-01"}])
        frame = _r03_signup_before_order(o, _ctx_for(c, pd.DataFrame()))
        assert frame["result"].iloc[0] == "FAIL"
        assert frame["failing_detail"].iloc[0] == "order_before_signup"

    def test_unmatched_customer_skipped(self):
        from src.validation_rules import _r03_signup_before_order
        c = pd.DataFrame([{"customer_id": "C1", "signup_date": "2024-02-01"}])
        o = _orders_frame([{"customer_id": "GHOST"}])
        frame = _r03_signup_before_order(o, _ctx_for(c, pd.DataFrame()))
        assert frame["result"].iloc[0] == "PASS"
        assert frame["failing_detail"].iloc[0] == "skipped_due_to_R01"

    def test_normalised_rescue_is_evaluated(self):
        from src.validation_rules import _r03_signup_before_order
        c = pd.DataFrame([{"customer_id": "C-1", "signup_date": "2024-01-01"}])
        o = _orders_frame([{"customer_id": "c 1", "order_date": "2024-02-01"}])
        frame = _r03_signup_before_order(o, _ctx_for(c, pd.DataFrame()))
        assert frame["result"].iloc[0] == "PASS"
        assert frame["failing_detail"].iloc[0] == "signup_ok"

    def test_duplicate_customer_uses_earliest_signup(self):
        from src.validation_rules import _r03_signup_before_order
        c = pd.DataFrame([
            {"customer_id": "C1", "signup_date": "2024-06-01"},
            {"customer_id": "C1", "signup_date": "2024-01-01"},
        ])
        o = _orders_frame([{"order_date": "2024-02-01"}])
        frame = _r03_signup_before_order(o, _ctx_for(c, pd.DataFrame()))
        assert frame["result"].iloc[0] == "PASS"

    def test_null_order_date_fails(self):
        from src.validation_rules import _r03_signup_before_order
        c = pd.DataFrame([{"customer_id": "C1", "signup_date": "2024-01-01"}])
        o = _orders_frame([{"order_date": ""}])
        frame = _r03_signup_before_order(o, _ctx_for(c, pd.DataFrame()))
        assert frame["result"].iloc[0] == "FAIL"


class TestR04Bodies:
    def test_today_passes(self):
        from src.validation_rules import REGISTRY, evaluate_rule
        c = pd.DataFrame([{"customer_id": "C1", "signup_date": "2024-01-01"}])
        o = _orders_frame([{"order_date": "2026-10-11"}])
        out = evaluate_rule(REGISTRY["R04"], o, _ctx_for(c, pd.DataFrame()))
        assert out.iloc[0] == "PASS"

    def test_day_after_today_fails(self):
        from src.validation_rules import _r04_valid_order_date
        c = pd.DataFrame([{"customer_id": "C1", "signup_date": "2024-01-01"}])
        o = _orders_frame([{"order_date": "2026-10-12"}])
        frame = _r04_valid_order_date(o, _ctx_for(c, pd.DataFrame()))
        assert frame["result"].iloc[0] == "FAIL"
        assert frame["failing_detail"].iloc[0] == "after_today"

    def test_lower_bound_passes(self):
        from src.validation_rules import _r04_valid_order_date
        c = pd.DataFrame([{"customer_id": "C1", "signup_date": "2024-01-01"}])
        o = _orders_frame([{"order_date": "2024-01-01"}])
        frame = _r04_valid_order_date(o, _ctx_for(c, pd.DataFrame()))
        assert frame["result"].iloc[0] == "PASS"

    def test_day_before_lower_bound_fails(self):
        from src.validation_rules import _r04_valid_order_date
        c = pd.DataFrame([{"customer_id": "C1", "signup_date": "2024-01-01"}])
        o = _orders_frame([{"order_date": "2023-12-31"}])
        frame = _r04_valid_order_date(o, _ctx_for(c, pd.DataFrame()))
        assert frame["result"].iloc[0] == "FAIL"
        assert frame["failing_detail"].iloc[0] == "before_lower_bound"

    def test_unparseable_and_null_fail(self):
        from src.validation_rules import _r04_valid_order_date
        c = pd.DataFrame([{"customer_id": "C1", "signup_date": "2024-01-01"}])
        o = _orders_frame([{"order_date": "not-a-date"}, {"order_date": ""}])
        frame = _r04_valid_order_date(o, _ctx_for(c, pd.DataFrame()))
        assert (frame["result"] == "FAIL").all()


class TestR05Bodies:
    def test_happy_path_passes(self):
        from src.validation_rules import REGISTRY, evaluate_rule
        o = _orders_frame([{"quantity": "3"}])
        out = evaluate_rule(REGISTRY["R05"], o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert out.iloc[0] == "PASS"

    def test_word_decimal_zero_negative_reported_separately(self):
        from src.validation_rules import _r05_valid_quantity
        ctx = _ctx_for(pd.DataFrame(), pd.DataFrame())
        o = _orders_frame([{"quantity": "two", "raw_quantity": "two"},
                           {"quantity": "", "raw_quantity": "2.5"},
                           {"quantity": "0", "raw_quantity": "0"},
                           {"quantity": "-2", "raw_quantity": "-2"}])
        frame = _r05_valid_quantity(o, ctx)
        assert (frame["result"] == "FAIL").all()
        assert frame["failing_detail"].tolist() == [
            "invalid:word", "invalid:decimal_or_malformed",
            "not_positive:zero", "not_positive:negative"]

    def test_null_quantity_fails(self):
        from src.validation_rules import _r05_valid_quantity
        o = _orders_frame([{"quantity": ""}])
        frame = _r05_valid_quantity(o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert frame["result"].iloc[0] == "FAIL"

    def test_at_fence_passes_above_fails(self):
        # Eight 2s pin the fence at exactly 2.0 (Q1=Q3=2, IQR=0), so the
        # 2s exercise the ==fence boundary (passes) and 500 is above it.
        from src.validation_rules import _r05_fence, _r05_valid_quantity
        rows = [{"quantity": "2"}] * 8 + [{"quantity": "500"}]
        probe = pd.DataFrame(rows)
        assert _r05_fence(probe["quantity"]) == 2.0
        o = _orders_frame(rows)
        frame = _r05_valid_quantity(o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert (frame["result"].iloc[:8] == "PASS").all()
        assert frame["result"].iloc[8] == "FAIL"
        assert "above_fence" in frame["failing_detail"].iloc[8]

    def test_tie_rows_agree(self):
        from src.validation_rules import _r05_valid_quantity
        o = _orders_frame([{"quantity": "0"}, {"quantity": "0"}])
        frame = _r05_valid_quantity(o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert (frame["failing_detail"] == "not_positive:zero").all()


class TestR06Bodies:
    def _prod(self, price="100"):
        return pd.DataFrame([{"product_id": "P1", "unit_price": price}])

    def test_happy_path_passes(self):
        from src.validation_rules import REGISTRY, evaluate_rule
        o = _orders_frame([{}])
        out = evaluate_rule(REGISTRY["R06"], o, _ctx_for(pd.DataFrame(), self._prod()))
        assert out.iloc[0] == "PASS"

    def test_boundary_tolerance_passes(self):
        from src.validation_rules import _r06_valid_price
        o = _orders_frame([{"unit_price_paid": "90", "discount": "0"}])
        frame = _r06_valid_price(o, _ctx_for(pd.DataFrame(), self._prod("100")))
        assert frame["result"].iloc[0] == "PASS"

    def test_outside_tolerance_fails(self):
        from src.validation_rules import _r06_valid_price
        o = _orders_frame([{"unit_price_paid": "1000", "discount": "0"}])
        frame = _r06_valid_price(o, _ctx_for(pd.DataFrame(), self._prod("100")))
        assert frame["result"].iloc[0] == "FAIL"
        assert frame["failing_detail"].iloc[0] == "outside_tolerance"

    def test_no_catalogue_price_warns(self):
        from src.validation_rules import _r06_valid_price
        p = pd.DataFrame([{"product_id": "P9", "unit_price": "100"}])
        o = _orders_frame([{}])
        frame = _r06_valid_price(o, _ctx_for(pd.DataFrame(), p))
        assert frame["result"].iloc[0] == "WARNING"
        assert frame["failing_detail"].iloc[0] == "unverifiable:no_catalogue_price"

    def test_zero_and_null_price_fail(self):
        from src.validation_rules import _r06_valid_price
        ctx = _ctx_for(pd.DataFrame(), self._prod())
        o = _orders_frame([{"unit_price_paid": "0"}, {"unit_price_paid": ""}])
        frame = _r06_valid_price(o, ctx)
        assert (frame["result"] == "FAIL").all()

    def test_tie_rows_agree(self):
        from src.validation_rules import _r06_valid_price
        o = _orders_frame([{"unit_price_paid": "1000"}, {"unit_price_paid": "1000"}])
        frame = _r06_valid_price(o, _ctx_for(pd.DataFrame(), self._prod()))
        assert (frame["result"] == "FAIL").all()


class TestR07Bodies:
    def test_fraction_and_percent_pass(self):
        from src.validation_rules import _r07_valid_discount
        ctx = _ctx_for(pd.DataFrame(), pd.DataFrame())
        o = _orders_frame([{"discount": "0.1"}, {"discount": "10%"}])
        frame = _r07_valid_discount(o, ctx)
        assert (frame["result"] == "PASS").all()
        assert frame["failing_detail"].tolist() == ["fraction", "percentage"]

    def test_raw_mirror_percent_resolved(self):
        from src.validation_rules import _r07_valid_discount
        o = _orders_frame([{"discount": "0.15", "raw_discount": "15"}])
        frame = _r07_valid_discount(o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert frame["result"].iloc[0] == "PASS"
        assert frame["failing_detail"].iloc[0] == "percentage"

    def test_null_empty_and_zero(self):
        from src.validation_rules import _r07_valid_discount
        o = _orders_frame([{"discount": ""}, {"discount": "0"}])
        frame = _r07_valid_discount(o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert (frame["result"] == "PASS").all()
        assert frame["failing_detail"].tolist() == ["no_discount_claimed",
                                                   "fraction:zero"]

    def test_bare_one_counted_separately(self):
        from src.validation_rules import _r07_valid_discount
        o = _orders_frame([{"discount": "1"}])
        frame = _r07_valid_discount(o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert frame["result"].iloc[0] == "PASS"
        assert frame["failing_detail"].iloc[0] == "fraction:bare_one"

    def test_out_of_range_and_unparseable_fail(self):
        from src.validation_rules import _r07_valid_discount
        o = _orders_frame([{"discount": "150"}, {"discount": "NA"}])
        frame = _r07_valid_discount(o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert (frame["result"] == "FAIL").all()
        assert frame["failing_detail"].tolist() == ["invalid:out_of_range",
                                                   "invalid:unparseable"]

    def test_tie_rows_agree(self):
        from src.validation_rules import _r07_valid_discount
        o = _orders_frame([{"discount": "abc"}, {"discount": "abc"}])
        frame = _r07_valid_discount(o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert (frame["failing_detail"] == "invalid:unparseable").all()


class TestR08Bodies:
    def test_happy_path_passes(self):
        from src.validation_rules import REGISTRY, evaluate_rule
        o = _orders_frame([{}])
        out = evaluate_rule(REGISTRY["R08"], o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert out.iloc[0] == "PASS"

    def test_null_missing_fails(self):
        from src.validation_rules import _r08_valid_status
        o = _orders_frame([{"order_status": ""}])
        frame = _r08_valid_status(o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert frame["result"].iloc[0] == "FAIL"
        assert frame["failing_detail"].iloc[0] == "missing_status"

    def test_unmapped_fails_visibly(self):
        from src.validation_rules import _r08_valid_status
        o = _orders_frame([{"order_status": "UNMAPPED"}])
        frame = _r08_valid_status(o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert frame["result"].iloc[0] == "FAIL"
        assert frame["failing_detail"].iloc[0] == "unmapped_status"

    def test_unseen_raw_fails_visibly(self):
        from src.validation_rules import _r08_valid_status
        o = _orders_frame([{"order_status": "UNMAPPED",
                            "raw_order_status": "Shipped"}])
        frame = _r08_valid_status(o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert frame["result"].iloc[0] == "FAIL"

    def test_tie_rows_agree(self):
        from src.validation_rules import _r08_valid_status
        o = _orders_frame([{"order_status": ""}, {"order_status": ""}])
        frame = _r08_valid_status(o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert (frame["failing_detail"] == "missing_status").all()


class TestR09Bodies:
    def test_happy_path_passes(self):
        from src.validation_rules import REGISTRY, evaluate_rule
        o = _orders_frame([{}])
        out = evaluate_rule(REGISTRY["R09"], o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert out.iloc[0] == "PASS"

    def test_null_missing_warns(self):
        from src.validation_rules import _r09_valid_payment
        o = _orders_frame([{"payment_mode": ""}])
        frame = _r09_valid_payment(o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert frame["result"].iloc[0] == "WARNING"
        assert frame["failing_detail"].iloc[0] == "missing_payment"

    def test_unseen_raw_warns_visibly(self):
        from src.validation_rules import _r09_valid_payment
        o = _orders_frame([{"payment_mode": "UNMAPPED",
                            "raw_payment_mode": "Bitcoin"}])
        frame = _r09_valid_payment(o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert frame["result"].iloc[0] == "WARNING"
        assert frame["failing_detail"].iloc[0] == "unmapped_payment"

    def test_boundary_standard_passthrough(self):
        from src.validation_rules import _r09_valid_payment
        o = _orders_frame([{"payment_mode": "COD"}])
        frame = _r09_valid_payment(o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert frame["result"].iloc[0] == "PASS"

    def test_tie_rows_agree(self):
        from src.validation_rules import _r09_valid_payment
        o = _orders_frame([{"payment_mode": ""}, {"payment_mode": ""}])
        frame = _r09_valid_payment(o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert (frame["result"] == "WARNING").all()


class TestR10Bodies:
    def test_happy_path_passes(self):
        from src.validation_rules import REGISTRY, evaluate_rule
        o = _orders_frame([{}])
        out = evaluate_rule(REGISTRY["R10"], o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert out.iloc[0] == "PASS"

    def test_null_days_fail(self):
        from src.validation_rules import _r10_valid_delivery_days
        o = _orders_frame([{"delivery_days": ""}])
        frame = _r10_valid_delivery_days(o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert frame["result"].iloc[0] == "FAIL"
        assert frame["failing_detail"].iloc[0] == "missing_delivery_days"

    def test_boundary_upper_passes(self):
        from src.validation_rules import _r10_valid_delivery_days
        o = _orders_frame([{"delivery_days": "30"}, {"delivery_days": "31"}])
        frame = _r10_valid_delivery_days(o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert frame["result"].iloc[0] == "PASS"
        assert frame["result"].iloc[1] == "FAIL"
        assert frame["failing_detail"].iloc[1] == "above_upper_bound_30"

    def test_negative_and_non_integer_fail(self):
        from src.validation_rules import _r10_valid_delivery_days
        o = _orders_frame([{"delivery_days": "-1"}, {"delivery_days": "abc"}])
        frame = _r10_valid_delivery_days(o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert (frame["result"] == "FAIL").all()
        assert frame["failing_detail"].tolist() == ["negative_delivery_days",
                                                   "non_integer_delivery_days"]

    def test_cancelled_rules(self):
        from src.validation_rules import _r10_valid_delivery_days
        o = _orders_frame([{"order_status": "Cancelled", "delivery_days": ""},
                           {"order_status": "Cancelled", "delivery_days": "0"},
                           {"order_status": "Cancelled", "delivery_days": "5"}])
        frame = _r10_valid_delivery_days(o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert frame["result"].tolist() == ["PASS", "PASS", "WARNING"]
        assert frame["failing_detail"].iloc[2] == "cancelled_with_delivery_days"

    def test_other_status_passes(self):
        from src.validation_rules import _r10_valid_delivery_days
        o = _orders_frame([{"order_status": "Pending", "delivery_days": "45"}])
        frame = _r10_valid_delivery_days(o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert frame["result"].iloc[0] == "PASS"

    def test_tie_rows_agree(self):
        from src.validation_rules import _r10_valid_delivery_days
        o = _orders_frame([{"delivery_days": "-1"}, {"delivery_days": "-1"}])
        frame = _r10_valid_delivery_days(o, _ctx_for(pd.DataFrame(), pd.DataFrame()))
        assert (frame["failing_detail"] == "negative_delivery_days").all()


class TestR11Bodies:
    def _prod(self, stock="10"):
        return pd.DataFrame([{"product_id": "P1", "stock_qty": stock}])

    def test_happy_path_passes(self):
        from src.validation_rules import REGISTRY, evaluate_rule
        o = _orders_frame([{}])
        out = evaluate_rule(REGISTRY["R11"], o, _ctx_for(pd.DataFrame(), self._prod()))
        assert out.iloc[0] == "PASS"

    def test_null_quantity_skipped(self):
        from src.validation_rules import _r11_inventory_feasibility
        o = _orders_frame([{"quantity": ""}])
        frame = _r11_inventory_feasibility(o, _ctx_for(pd.DataFrame(), self._prod()))
        assert frame["result"].iloc[0] == "PASS"
        assert frame["failing_detail"].iloc[0] == "skipped_unparseable_quantity"

    def test_boundary_equal_stock_passes(self):
        from src.validation_rules import _r11_inventory_feasibility
        o = _orders_frame([{"quantity": "10"}, {"quantity": "11"}])
        frame = _r11_inventory_feasibility(o, _ctx_for(pd.DataFrame(), self._prod("10")))
        assert frame["result"].tolist() == ["PASS", "WARNING"]
        assert frame["failing_detail"].iloc[1] == "insufficient_stock"

    def test_unusable_stock_skipped(self):
        from src.validation_rules import _r11_inventory_feasibility
        ctx = _ctx_for(pd.DataFrame(), pd.DataFrame(
            [{"product_id": "P1", "stock_qty": "NA"},
             {"product_id": "P2", "stock_qty": "-5"}]))
        o = _orders_frame([{"product_id": "P1", "quantity": "99"},
                           {"product_id": "P2", "quantity": "99"},
                           {"product_id": "P9", "quantity": "99"}])
        frame = _r11_inventory_feasibility(o, ctx)
        assert (frame["result"] == "PASS").all()
        assert (frame["failing_detail"] == "skipped_unusable_stock").all()

    def test_tie_rows_agree(self):
        from src.validation_rules import _r11_inventory_feasibility
        o = _orders_frame([{"quantity": "99"}, {"quantity": "99"}])
        frame = _r11_inventory_feasibility(o, _ctx_for(pd.DataFrame(), self._prod("10")))
        assert (frame["failing_detail"] == "insufficient_stock").all()


class TestR12Bodies:
    def _cust(self, signup="2024-01-01"):
        return pd.DataFrame([{"customer_id": "C1", "signup_date": signup}])

    def test_happy_path_passes(self):
        from src.validation_rules import REGISTRY, evaluate_rule
        o = _orders_frame([{}])
        out = evaluate_rule(REGISTRY["R12"], o, _ctx_for(self._cust(), pd.DataFrame()))
        assert out.iloc[0] == "PASS"

    def test_r12a_future_delivered_fails(self):
        from src.validation_rules import _r12_cross_field
        o = _orders_frame([{"order_date": "2026-10-12"}])
        frame = _r12_cross_field(o, _ctx_for(self._cust(), pd.DataFrame()))
        assert frame["result"].iloc[0] == "FAIL"
        assert "R12a:future_delivered_date" in frame["failing_detail"].iloc[0]

    def test_r12a_boundary_today_passes(self):
        from src.validation_rules import _r12_cross_field
        o = _orders_frame([{"order_date": "2026-10-11"}])
        frame = _r12_cross_field(o, _ctx_for(self._cust(), pd.DataFrame()))
        assert frame["result"].iloc[0] == "PASS"

    def test_r12b_missing_days_fails(self):
        from src.validation_rules import _r12_cross_field
        o = _orders_frame([{"delivery_days": ""}])
        frame = _r12_cross_field(o, _ctx_for(self._cust(), pd.DataFrame()))
        assert frame["result"].iloc[0] == "FAIL"
        assert "R12b:delivered_missing_days" in frame["failing_detail"].iloc[0]

    def test_r12c_only_warns(self):
        from src.validation_rules import _r12_cross_field
        o = _orders_frame([{"order_status": "Cancelled", "delivery_days": "5"}])
        frame = _r12_cross_field(o, _ctx_for(self._cust(), pd.DataFrame()))
        assert frame["result"].iloc[0] == "WARNING"
        assert frame["failing_detail"].iloc[0] == "R12c:cancelled_positive_days"

    def test_r12d_signup_after_today_fails(self):
        from src.validation_rules import _r12_cross_field
        c = pd.DataFrame([{"customer_id": "C1", "signup_date": "2026-10-12"}])
        o = _orders_frame([{}])
        frame = _r12_cross_field(o, _ctx_for(c, pd.DataFrame()))
        assert frame["result"].iloc[0] == "FAIL"
        assert "R12d:signup_after_today" in frame["failing_detail"].iloc[0]

    def test_unmatched_customer_skips_r12d(self):
        from src.validation_rules import _r12_cross_field
        o = _orders_frame([{"customer_id": "GHOST"}])
        frame = _r12_cross_field(o, _ctx_for(self._cust(), pd.DataFrame()))
        assert frame["result"].iloc[0] == "PASS"

    def test_null_dates_contribute_no_tag(self):
        from src.validation_rules import _r12_cross_field
        o = _orders_frame([{"order_status": "Pending", "order_date": ""}])
        frame = _r12_cross_field(o, _ctx_for(self._cust(), pd.DataFrame()))
        assert frame["result"].iloc[0] == "PASS"

    def test_tie_rows_agree(self):
        from src.validation_rules import _r12_cross_field
        o = _orders_frame([{"order_date": "2026-10-12"}, {"order_date": "2026-10-12"}])
        frame = _r12_cross_field(o, _ctx_for(self._cust(), pd.DataFrame()))
        assert (frame["result"] == "FAIL").all()
        assert (frame["failing_detail"] == frame["failing_detail"].iloc[0]).all()