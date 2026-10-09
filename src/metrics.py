"""Chỉ số nghiệp vụ dùng chung cho notebook, pipeline hằng tuần và Streamlit app."""

import pandas as pd


def first_attempts(df):
    """Mỗi khách 1 dòng: lần thanh toán đầu tiên + khách có từng mua thành công không.

    Bản gốc tính giá trị khách từ các giao dịch thành công rồi mới left join phần lỗi,
    nên khách chưa từng mua thành công bị loại khỏi phân tích. Hàm này giữ lại nhóm đó.
    """
    first = df.groupby("customer_id", sort=False).head(1).set_index("customer_id")
    first_success_time = df[df["is_success"]].groupby("customer_id")["time"].min()
    first = first.join(first_success_time.rename("first_success_time"))
    first["first_failed"] = first["is_failed"]
    first["ever_converted"] = first["first_success_time"].notna()
    hours = (first["first_success_time"] - first["time"]).dt.total_seconds() / 3600
    first["hours_to_convert"] = hours.where(first["first_failed"])
    return first


def lost_at_payment_summary(df):
    """Khách thất bại thanh toán ngay lần đầu và không bao giờ quay lại mua được."""
    first = first_attempts(df)
    failed_first = first[first["first_failed"]]
    lost = failed_first[~failed_first["ever_converted"]]
    return {
        "customers_total": int(len(first)),
        "failed_first_attempt": int(len(failed_first)),
        "failed_first_attempt_pct": len(failed_first) / len(first),
        "never_converted": int(len(lost)),
        "never_converted_pct_of_failed": len(lost) / len(failed_first),
        "recovered_within_1h": int((failed_first["hours_to_convert"] <= 1).sum()),
        "recovered_within_24h": int((failed_first["hours_to_convert"] <= 24).sum()),
        "lost_first_order_value": float(lost["final_price"].sum()),
        "avg_success_ticket_value": float(df.loc[df["is_success"], "final_price"].mean()),
    }


def failure_rate_by(df, col):
    out = df.groupby(col, observed=True).agg(
        n_tickets=("ticket_id", "count"), n_failed=("is_failed", "sum")
    )
    out["failure_rate"] = out["n_failed"] / out["n_tickets"]
    return out.sort_values("failure_rate", ascending=False)


def weekly_error_rates(df):
    """Bảng tuần x nhóm lỗi: số vé, số lỗi, tỷ lệ lỗi."""
    total = df.groupby("week").size().rename("n_tickets")
    errors = (
        df[df["is_failed"]]
        .pivot_table(index="week", columns="error_group", values="ticket_id", aggfunc="count")
        .fillna(0)
    )
    out = errors.join(total, how="right").fillna(0)
    for group in ["customer", "external", "internal"]:
        if group not in out:
            out[group] = 0
        out[f"{group}_rate"] = out[group] / out["n_tickets"]
    out["failure_rate"] = out[["customer", "external", "internal"]].sum(axis=1) / out["n_tickets"]
    return out.sort_index()


def recovery_rate(df, days=7):
    """Tỷ lệ giao dịch lỗi được chính khách đó mua thành công lại trong `days` ngày."""
    failed = df.loc[df["is_failed"], ["ticket_id", "customer_id", "time"]].sort_values("time")
    success = (
        df.loc[df["is_success"], ["customer_id", "time"]]
        .rename(columns={"time": "next_success"})
        .sort_values("next_success")
    )
    matched = pd.merge_asof(
        failed, success, left_on="time", right_on="next_success",
        by="customer_id", direction="forward",
    )
    # Bỏ các lỗi trong `days` ngày cuối dữ liệu vì chưa đủ thời gian quan sát
    matched = matched[matched["time"] <= df["time"].max() - pd.Timedelta(days=days)]
    within = (matched["next_success"] - matched["time"]) <= pd.Timedelta(days=days)
    return float(within.mean())
