"""Tests for Segment 4 and 5 question functions."""

from pathlib import Path

import pandas as pd
import pytest

from src.data_loader import load_all_text
from src.mapping_gate import load_mapping
from src.questions.seg4_cross_file import (
    q30_unmatched_customers,
    q31_unmatched_products,
    q32_ghost_customer_value,
    q33_never_ordered_products,
    q34_price_gap_per_product,
    q35_price_closeness,
    q36_fuzzy_attribution,
    q37_every_month_vs_one_month,
    q38_orders_before_signup,
    q39_join_losses,
)
from src.questions.seg5_values import (
    q40_payment_spellings,
    q41_status_spellings,
    q42_category_pairs,
    q43_quantity_kinds,
    q44_high_quantities,
    q45_future_dates,
    q46_discount_forms,
    q47_delivery_extremes,
    q48_outside_cities,
    q49_three_unknowns,
)
from src.validation_rules import Context


@pytest.fixture(scope="module")
def data():
    # Source data is at repo root / Resources/Capstone Questions/Capstone 2/data
    # Test file is at: repo_root/Projects/Individual/Manas Dutt/Week 3/QuickMart/tests/test_questions_seg4_5.py
    # So repo_root = parents[6]
    repo_root = Path(__file__).resolve().parents[6]
    raw_dir = repo_root / "Resources" / "Capstone Questions" / "Capstone 2" / "data"
    raw = load_all_text(raw_dir)
    return {
        "orders": pd.DataFrame(raw["orders"]),
        "customers": pd.DataFrame(raw["customers"]),
        "products": pd.DataFrame(raw["products"]),
    }


@pytest.fixture(scope="module")
def ctx(data):
    city_map = load_mapping("city")
    cat_map = load_mapping("category")
    pay_map = load_mapping("payment")
    status_map = load_mapping("status")
    return Context(
        customers=data["customers"],
        products=data["products"],
        city_map=city_map,
        cat_map=cat_map,
        pay_map=pay_map,
        status_map=status_map,
        today="2026-10-11",
    )


class TestSeg4:
    def test_q30_unmatched_customers(self, data, ctx):
        result, expl = q30_unmatched_customers(data["orders"], data["customers"], ctx)
        assert isinstance(result, dict)
        assert result["exact_matched"] == 5620
        assert result["rescued_by_normalisation"] == 279
        assert result["unmatched"] == 204
        assert result["top_unmatched_value"] == "C9999"
        assert result["top_unmatched_count"] == 144
        assert "normalised match" in expl.lower()

    def test_q31_unmatched_products(self, data, ctx):
        result, _expl = q31_unmatched_products(data["orders"], data["products"], ctx)
        assert isinstance(result, dict)
        assert result["unmatched"] == 163
        assert result["typing_variants"] == 0
        assert result["nonexistent"] == 163
        assert result["top_missing"] == "P99"

    def test_q32_ghost_customer_value(self, data, ctx):
        result, expl = q32_ghost_customer_value(data["orders"], data["customers"], ctx)
        assert isinstance(result, dict)
        assert result["ghost_customers"] == 2
        assert result["ghost_orders"] == 204
        assert result["ghost_value"] == 671491.75
        assert "excluded from revenue" in expl.lower()

    def test_q33_never_ordered_products(self, data, ctx):
        result, _expl = q33_never_ordered_products(data["orders"], data["products"], ctx)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_q34_price_gap_per_product(self, data, ctx):
        result, _expl = q34_price_gap_per_product(data["orders"], data["products"], ctx)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 28
        assert "systematic" in result.columns
        systematic = result[result["systematic"] == True]
        assert len(systematic) == 5

    def test_q35_price_closeness(self, data, ctx):
        result, _expl = q35_price_closeness(data["orders"], data["products"], ctx)
        assert isinstance(result, dict)
        assert result["within_tolerance"] == 558
        assert result["outside_tolerance"] == 4453
        assert result["non_positive_price"] == 267
        assert result["unverifiable"] == 825

    def test_q36_fuzzy_attribution(self, data, ctx):
        result, _expl = q36_fuzzy_attribution(data["orders"], data["customers"], ctx)
        assert isinstance(result, dict)
        assert result["fuzzy_orders"] == 279
        assert result["fuzzy_value_share_pct"] == 13.49
        assert "held_back" in result

    def test_q37_every_month_vs_one_month(self, data, ctx):
        result, _expl = q37_every_month_vs_one_month(data["orders"], data["customers"], ctx)
        assert isinstance(result, dict)
        assert result["n_months"] == 87
        assert result["every_month"]["n"] == 0
        assert result["one_month"]["n"] == 161
        assert "months" in result

    def test_q38_orders_before_signup(self, data, ctx):
        result, _expl = q38_orders_before_signup(data["orders"], data["customers"], ctx)
        assert isinstance(result, dict)
        assert result["orders"] == 1338
        assert result["customers"] == 319
        assert result["future_signups_in_master"] == 110
        assert result["future_orders"] == 1381

    def test_q39_join_losses(self, data, ctx):
        result, _expl = q39_join_losses(data["orders"], data["customers"], data["products"], ctx)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 5
        assert result.iloc[0]["dropped"] == 483  # exact customer
        assert result.iloc[1]["dropped"] == 204  # normalised customer
        assert result.iloc[2]["dropped"] == 456  # exact product
        assert result.iloc[3]["dropped"] == 163  # normalised product
        assert result.iloc[4]["dropped"] == 204  # city


class TestSeg5:
    def test_q40_payment_spellings(self, data, ctx):
        result, _expl = q40_payment_spellings(data["orders"], ctx)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 10
        assert "assignable" in result.columns
        unassignable = result[result["assignable"] == False]
        assert len(unassignable) == 1  # only 'cod' is unassignable; empty maps to MISSING
        assert unassignable.iloc[0]["raw_value"] == "cod"

    def test_q41_status_spellings(self, data, ctx):
        result, _expl = q41_status_spellings(data["orders"], ctx)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 10
        delivered = result[result["raw_value"].str.strip().str.lower() == "delivered"]
        assert delivered["count"].sum() == 1803  # 617 (delivered) + 609 (Delivered) + 577 (Delivered with trailing space)

    def test_q42_category_pairs(self, data, ctx):
        result, _expl = q42_category_pairs(data["orders"], data["products"], ctx)
        assert isinstance(result, dict)
        assert "decisions" in result
        assert len(result["decisions"]) == 4
        merge_decisions = [d for d in result["decisions"] if d["decision"] == "merge"]
        assert len(merge_decisions) == 3

    def test_q43_quantity_kinds(self, data, ctx):
        result, _expl = q43_quantity_kinds(data["orders"], ctx)
        assert isinstance(result, dict)
        assert result["words"] == 57
        assert result["decimals"] == 62
        assert result["zero"] == 251
        assert result["negative"] == 111
        assert result["empty"] == 170
        assert result["bad_total"] == 651

    def test_q44_high_quantities(self, data, ctx):
        result, _expl = q44_high_quantities(data["orders"], ctx)
        assert isinstance(result, dict)
        assert result["fence"] == 10.0
        assert result["flagged_rows"] == 77
        assert result["flagged_values"] == ["500"]
        assert result["verdict"] == "error"

    def test_q45_future_dates(self, data, ctx):
        result, _expl = q45_future_dates(data["orders"], ctx)
        assert isinstance(result, dict)
        assert result["future_rows"] == 467
        assert "months" in result
        assert len(result["months"]) > 0

    def test_q46_discount_forms(self, data, ctx):
        result, _expl = q46_discount_forms(data["orders"], ctx)
        assert isinstance(result, dict)
        assert result["fraction"] == 529
        assert result["percentage"] == 2176
        assert result["zero"] == 2271
        assert result["empty"] == 551
        assert result["unparseable"] == 576

    def test_q47_delivery_extremes(self, data, ctx):
        result, _expl = q47_delivery_extremes(data["orders"], ctx)
        assert isinstance(result, dict)
        assert "by_status_detail" in result
        detail = result["by_status_detail"]
        assert "Delivered|negative_delivery_days" in detail
        assert "Delivered|above_upper_bound_30" in detail

    def test_q48_outside_cities(self, data, ctx):
        result, _expl = q48_outside_cities(data["orders"], data["customers"], ctx)
        assert isinstance(result, dict)
        assert result["served"] == ["Bengaluru", "Chennai", "Hyderabad", "Pune"]
        assert len(result["outside_values"]) == 8
        assert result["outside_orders"] == 3521
        assert result["outside_customers"] == 270

    def test_q49_three_unknowns(self, data, ctx):
        result, _expl = q49_three_unknowns(data["orders"], data["customers"], data["products"], ctx)
        assert isinstance(result, list)
        assert len(result) == 3
        for item in result:
            assert "unknown" in item
            assert "responsible" in item
            assert "rows_affected" in item
            assert "example_customer" in item
            assert "unsafe_decision" in item
            # Check masking (first char + asterisks)
            assert item["example_customer"][0].isalpha()
            assert "*" in item["example_customer"]