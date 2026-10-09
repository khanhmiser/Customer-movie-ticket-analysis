"""Tài chính: giá trị mất do giao dịch lỗi không được mua lại, và tiền giảm giá cho khách chỉ mua 1 lần."""

import pandas as pd

RECOVERY_DAYS = 7
ONE_TIME_DAYS = 90


def _next_success_gap(df, rows):
    """Số ngày từ mỗi dòng trong `rows` tới lần mua thành công KẾ TIẾP của cùng khách (NaN nếu không có)."""
    success = (
        df.loc[df["is_success"], ["customer_id", "time"]]
        .rename(columns={"time": "next_success"})
        .sort_values("next_success")
    )
    left = rows[["ticket_id", "customer_id", "time"]].sort_values("time")
    # allow_exact_matches=False: không tính chính giao dịch đang xét
    matched = pd.merge_asof(left, success, left_on="time", right_on="next_success", by="customer_id",
                            direction="forward", allow_exact_matches=False)
    gap = (matched["next_success"] - matched["time"]).dt.total_seconds() / 86400
    return pd.Series(gap.values, index=matched["ticket_id"].values)


def monthly_losses(df):
    """Theo tháng: giá trị đơn lỗi không được mua lại trong 7 ngày, và giảm giá cho khách KM không quay lại trong 90 ngày.

    Tháng cuối chưa đủ cửa sổ quan sát -> NaN (tránh báo thiệt hại cao giả tạo).
    """
    data_end = df["time"].max()

    failed = df[df["is_failed"]].copy()
    failed["gap"] = failed["ticket_id"].map(_next_success_gap(df, failed))
    failed["unrecovered"] = ~(failed["gap"] <= RECOVERY_DAYS)

    promo = df[df["is_success"] & (df["type"] == "promotion")].copy()
    promo["gap"] = promo["ticket_id"].map(_next_success_gap(df, promo))
    promo["one_time"] = ~(promo["gap"] <= ONE_TIME_DAYS)

    out = pd.DataFrame({
        "failed_value": failed.groupby("year_month")["final_price"].sum(),
        "unrecovered_failed_value": failed[failed["unrecovered"]].groupby("year_month")["final_price"].sum(),
        "discount_total": promo.groupby("year_month")["discount_value"].sum(),
        "discount_one_time": promo[promo["one_time"]].groupby("year_month")["discount_value"].sum(),
    })
    # Cả tháng phải có đủ cửa sổ quan sát, nếu không thì ẩn cả tháng (không lấy nửa tháng)
    month_end = pd.to_datetime(out.index) + pd.offsets.MonthEnd(0) + pd.Timedelta(hours=23, minutes=59)
    out.loc[month_end + pd.Timedelta(days=RECOVERY_DAYS) > data_end, ["unrecovered_failed_value"]] = None
    out.loc[month_end + pd.Timedelta(days=ONE_TIME_DAYS) > data_end, ["discount_one_time"]] = None
    out["unrecovered_share"] = out["unrecovered_failed_value"] / out["failed_value"]
    out["one_time_discount_share"] = out["discount_one_time"] / out["discount_total"]
    return out.sort_index()
