"""Kiểm tra chất lượng 1 file dữ liệu giao dịch trước khi nạp vào kho.

Mức độ:
- error   -> DỪNG: không nạp file, không chạy báo cáo (tránh ra báo cáo sai)
- warning -> vẫn nạp, nhưng ghi lại để theo dõi
Ngưỡng được đặt sau khi kiểm tra dữ liệu thật 2019-2022 (dữ liệu sạch đạt 0 lỗi ở mọi check "error").
"""

import pandas as pd

REQUIRED_COLUMNS = [
    "ticket_id", "customer_id", "paying_method", "theater_name", "device_number", "original_price",
    "discount_value", "final_price", "time", "status_id", "campaign_id", "movie_name",
]
KEY_COLUMNS = ["ticket_id", "customer_id", "time", "status_id", "paying_method"]
KNOWN_PAYING_METHODS = {"money in app", "bank account", "credit card", "debit card", "other"}
PRICE_TOLERANCE = 0.01
# Số dòng/ngày dao động rất mạnh theo lịch chiếu phim (1 -> 1,268 dòng) nên chỉ cảnh báo khi lệch quá xa.
# Ngưỡng 0.1x-10x so với trung vị 28 ngày: cảnh báo ~5% số ngày (chủ yếu các đợt rạp mở lại sau COVID);
# ngưỡng 0.2x-5x cảnh báo tới ~11% số ngày -> quá nhiễu, người vận hành sẽ bỏ qua.
VOLUME_LOW, VOLUME_HIGH, VOLUME_WINDOW = 0.1, 10.0, 28


def _result(check, severity, failed_rows, detail=""):
    return {
        "check": check,
        "severity": severity,
        "status": "fail" if failed_rows else "pass",
        "failed_rows": int(failed_rows),
        "detail": detail,
    }


def check_batch(batch, refs, loaded_ids=frozenset(), expected_date=None, recent_daily_rows=()):
    """Trả về (batch_đã_làm_sạch, danh_sách_kết_quả).

    refs: dict các bảng tham chiếu {"status_detail", "customer", "campaign", "device_detail"}.
    loaded_ids: ticket_id đã có trong kho (chống nạp trùng).
    """
    results = []
    missing = [c for c in REQUIRED_COLUMNS if c not in batch.columns]
    results.append(_result("schema", "error", len(missing), f"thiếu cột: {missing}" if missing else ""))
    if missing:
        return batch, results
    results.append(_result("not_empty", "error", int(batch.empty), "file không có dòng nào" if batch.empty else ""))
    if batch.empty:
        return batch, results

    parsed_time = pd.to_datetime(batch["time"], errors="coerce", format="ISO8601")
    numeric = batch[["original_price", "discount_value", "final_price", "customer_id", "status_id", "campaign_id"]].apply(
        pd.to_numeric, errors="coerce")
    bad_types = (parsed_time.isna() & batch["time"].notna()) | (numeric.isna() & batch[numeric.columns].notna()).any(axis=1)
    results.append(_result("parse_types", "error", bad_types.sum(), "time/giá/id không đọc được"))

    nulls = batch[KEY_COLUMNS].isna().sum()
    results.append(_result("key_nulls", "error", batch[KEY_COLUMNS].isna().any(axis=1).sum(),
                           ", ".join(f"{c}: {n}" for c, n in nulls.items() if n)))

    exact_dup = batch.duplicated()
    results.append(_result("exact_duplicates", "warning", exact_dup.sum(), "dòng trùng hoàn toàn -> đã loại bỏ"))
    batch = batch[~exact_dup]
    parsed_time = parsed_time[~exact_dup]
    numeric = numeric[~exact_dup]

    conflict = batch["ticket_id"].duplicated(keep=False)
    results.append(_result("ticket_id_conflict", "error", conflict.sum(), "cùng ticket_id nhưng nội dung khác nhau"))
    already = batch["ticket_id"].isin(loaded_ids)
    results.append(_result("already_loaded", "error", already.sum(), "ticket_id đã có trong kho"))

    unknown_status = ~numeric["status_id"].isin(refs["status_detail"]["status_id"])
    results.append(_result("unknown_status", "error", unknown_status.sum(),
                           f"mã lạ: {sorted(numeric.loc[unknown_status, 'status_id'].dropna().unique().tolist())}"))
    unknown_customer = ~numeric["customer_id"].isin(refs["customer"]["customer_id"])
    results.append(_result("unknown_customer", "error", unknown_customer.sum(), "customer_id không có trong bảng customer"))
    unknown_campaign = (numeric["campaign_id"] != 0) & ~numeric["campaign_id"].isin(refs["campaign"]["campaign_id"])
    results.append(_result("unknown_campaign", "error", unknown_campaign.sum(), "campaign_id khác 0 nhưng không có trong bảng campaign"))
    unknown_device = ~batch["device_number"].isin(refs["device_detail"]["device_number"])
    results.append(_result("unknown_device", "warning", unknown_device.sum(), "device_number không có trong bảng device"))
    unknown_method = ~batch["paying_method"].isin(KNOWN_PAYING_METHODS)
    results.append(_result("unknown_paying_method", "warning", unknown_method.sum(),
                           f"giá trị lạ: {sorted(batch.loc[unknown_method, 'paying_method'].dropna().unique().tolist())}"))

    price_bad = (
        (numeric[["original_price", "discount_value", "final_price"]] < 0).any(axis=1)
        | (numeric["discount_value"] > numeric["original_price"] + PRICE_TOLERANCE)
        | ((numeric["original_price"] - numeric["discount_value"] - numeric["final_price"]).abs() > PRICE_TOLERANCE)
    )
    results.append(_result("price_rules", "error", price_bad.sum(), "giá âm / giảm giá > giá gốc / final ≠ gốc - giảm"))

    if expected_date is not None:
        wrong_day = parsed_time.dt.date != pd.Timestamp(expected_date).date()
        results.append(_result("date_matches_file", "error", wrong_day.sum(), f"có dòng không thuộc ngày {expected_date}"))

    recent = list(recent_daily_rows)[-VOLUME_WINDOW:]
    if len(recent) >= 7:
        median = pd.Series(recent).median()
        ratio = len(batch) / median if median else float("inf")
        off = ratio < VOLUME_LOW or ratio > VOLUME_HIGH
        results.append(_result("volume", "warning", int(off) * len(batch),
                               f"{len(batch)} dòng so với trung vị {median:.0f} dòng/ngày ({ratio:.1f} lần)"))
    return batch, results


# Bảng tham chiếu được cập nhật hằng ngày (khách mới, campaign mới...). domain = giá trị hợp lệ của cột phân loại.
REFERENCE_SPECS = {
    "customer": {"key": "customer_id", "required": ["customer_id", "usergender", "dob"],
                 "ints": ["customer_id"], "dates": ["dob"],
                 "domain": ("usergender", {"Male", "Female", "Not verify"}), "domain_severity": "warning"},
    "campaign": {"key": "campaign_id", "required": ["campaign_id", "campaign_type"], "ints": ["campaign_id"], "dates": [],
                 "domain": ("campaign_type", {"direct discount", "voucher", "reward point"}), "domain_severity": "warning"},
    "device_detail": {"key": "device_number", "required": ["device_number", "model", "platform"], "ints": [], "dates": [],
                      "domain": ("platform", {"mobile", "website"}), "domain_severity": "warning"},
    # Mã lỗi mới bắt buộc có nhóm lỗi hợp lệ - nếu không mọi báo cáo theo nhóm lỗi sẽ sai
    "status_detail": {"key": "status_id", "required": ["status_id", "description", "error_group"], "ints": ["status_id"],
                      "dates": [], "domain": ("error_group", {"customer", "external", "internal"}), "domain_severity": "error"},
}


def check_reference(table, batch, current):
    """Kiểm tra 1 file cập nhật bảng tham chiếu. Trả về (batch_đã_làm_sạch, kết quả)."""
    spec = REFERENCE_SPECS[table]
    key = spec["key"]
    results = []
    missing = [c for c in spec["required"] if c not in batch.columns]
    results.append(_result("schema", "error", len(missing), f"thiếu cột: {missing}" if missing else ""))
    if missing:
        return batch, results
    results.append(_result("not_empty", "error", int(batch.empty), "file không có dòng nào" if batch.empty else ""))
    if batch.empty:
        return batch, results

    bad = pd.Series(False, index=batch.index)
    for col in spec["ints"]:
        bad |= pd.to_numeric(batch[col], errors="coerce").isna() & batch[col].notna()
    for col in spec["dates"]:
        bad |= pd.to_datetime(batch[col], errors="coerce", format="mixed").isna() & batch[col].notna()
    results.append(_result("parse_types", "error", bad.sum(), f"{spec['ints'] + spec['dates']} không đọc được"))
    results.append(_result("key_nulls", "error", batch[key].isna().sum(), f"{key} bị trống"))
    if bad.any() or batch[key].isna().any():
        return batch, results  # khóa hỏng thì không so sánh tiếp được với bảng hiện tại

    exact_dup = batch.duplicated()
    results.append(_result("exact_duplicates", "warning", exact_dup.sum(), "dòng trùng hoàn toàn -> đã loại bỏ"))
    batch = batch[~exact_dup]
    conflict = batch[key].duplicated(keep=False)
    results.append(_result("key_conflict", "error", conflict.sum(), f"cùng {key} nhưng nội dung khác nhau"))

    col, allowed = spec["domain"]
    invalid = ~batch[col].isin(allowed)
    if table == "status_detail":
        invalid &= batch["status_id"] != 1  # mã 1 = thành công, không có nhóm lỗi
    results.append(_result(f"invalid_{col}", spec["domain_severity"], invalid.sum(),
                           f"giá trị không hợp lệ: {sorted(batch.loc[invalid, col].astype(str).unique().tolist())}"))

    # Cập nhật thông tin của bản ghi đã có (vd. khách đổi giới tính/ngày sinh) -> cho phép nhưng ghi lại
    existing = batch.merge(current, on=key, how="inner", suffixes=("", "_old"))
    cols = [c for c in spec["required"] if c != key]
    changed = (existing[cols].astype(str).values != existing[[f"{c}_old" for c in cols]].astype(str).values).any(axis=1) \
        if len(existing) else []
    n_changed = int(sum(changed))
    results.append(_result("updates_existing", "warning", n_changed, f"{n_changed} bản ghi đã có bị thay đổi thông tin"))
    return batch, results


def summarize(results):
    errors = [r for r in results if r["status"] == "fail" and r["severity"] == "error"]
    warnings = [r for r in results if r["status"] == "fail" and r["severity"] == "warning"]
    return {
        "status": "failed" if errors else "passed",
        "errors": [r["check"] for r in errors],
        "warnings": [r["check"] for r in warnings],
    }
