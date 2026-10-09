"""Bộ kiểm tra chất lượng: dữ liệu sạch phải qua, mỗi loại lỗi phải bị đúng check bắt."""

import pandas as pd
import pytest

from src import quality


def failed(results, severity="error"):
    return {r["check"] for r in results if r["status"] == "fail" and r["severity"] == severity}


def test_clean_real_day_passes(one_day, refs):
    _, results = quality.check_batch(one_day, refs, expected_date="2022-03-05")
    assert failed(results) == set()


@pytest.mark.parametrize("mutate, check", [
    (lambda d: d.assign(status_id=d["status_id"].where(d.index > 0, 99)), "unknown_status"),
    (lambda d: d.assign(customer_id=d["customer_id"].astype("float").where(d.index > 0, None)), "key_nulls"),
    (lambda d: d.assign(final_price=d["final_price"].where(d.index > 0, d["original_price"] + 5)), "price_rules"),
    (lambda d: d.assign(discount_value=d["discount_value"].where(d.index > 0, -1.0)), "price_rules"),
    (lambda d: d.assign(customer_id=d["customer_id"].where(d.index > 0, 999999999)), "unknown_customer"),
    (lambda d: d.assign(campaign_id=d["campaign_id"].where(d.index > 0, 123456789)), "unknown_campaign"),
    (lambda d: d.assign(time=d["time"].where(d.index > 0, "2022-03-06 10:00:00.000")), "date_matches_file"),
    (lambda d: d.assign(time=d["time"].where(d.index > 0, "không phải ngày")), "parse_types"),
])
def test_each_error_is_caught(one_day, refs, mutate, check):
    _, results = quality.check_batch(mutate(one_day), refs, expected_date="2022-03-05")
    assert check in failed(results)


def test_missing_column_stops_immediately(one_day, refs):
    _, results = quality.check_batch(one_day.drop(columns=["status_id"]), refs)
    assert [r["check"] for r in results] == ["schema"] and results[0]["status"] == "fail"


def test_ticket_id_conflict_vs_exact_duplicate(one_day, refs):
    exact = pd.concat([one_day, one_day.head(2)], ignore_index=True)
    batch, results = quality.check_batch(exact, refs, expected_date="2022-03-05")
    assert "exact_duplicates" in failed(results, "warning") and failed(results) == set()
    assert len(batch) == len(one_day)  # dòng trùng hoàn toàn bị loại

    conflict = one_day.copy()
    conflict.loc[1, "ticket_id"] = conflict.loc[0, "ticket_id"]
    _, results = quality.check_batch(conflict, refs, expected_date="2022-03-05")
    assert "ticket_id_conflict" in failed(results)


def test_already_loaded_ids_are_blocked(one_day, refs):
    _, results = quality.check_batch(one_day, refs, loaded_ids={one_day.loc[0, "ticket_id"]})
    assert "already_loaded" in failed(results)


def test_volume_is_only_a_warning(one_day, refs):
    _, results = quality.check_batch(one_day, refs, recent_daily_rows=[10_000] * 28)
    assert "volume" in failed(results, "warning") and failed(results) == set()


def test_reference_new_customers_pass(refs):
    new = pd.DataFrame({"customer_id": [900001], "usergender": ["Female"], "dob": ["2001-04-12"]})
    _, results = quality.check_reference("customer", new, refs["customer"])
    assert failed(results) == set()


def test_reference_status_needs_valid_error_group(refs):
    bad = pd.DataFrame({"status_id": [-8], "description": ["3-D Secure timeout"], "error_group": ["bank"]})
    _, results = quality.check_reference("status_detail", bad, refs["status_detail"])
    assert "invalid_error_group" in failed(results)


def test_reference_key_conflict_and_changed_records(refs):
    conflict = pd.DataFrame({"campaign_id": [1, 1], "campaign_type": ["voucher", "reward point"]})
    _, results = quality.check_reference("campaign", conflict, refs["campaign"])
    assert "key_conflict" in failed(results)

    existing = refs["customer"].head(1).copy()
    existing["usergender"] = "Male" if existing["usergender"].iloc[0] != "Male" else "Female"
    _, results = quality.check_reference("customer", existing, refs["customer"])
    assert "updates_existing" in failed(results, "warning") and failed(results) == set()
