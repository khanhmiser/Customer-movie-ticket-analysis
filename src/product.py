"""Product / IT: tuần này mã lỗi nào, nền tảng nào, phương thức nào tăng bao nhiêu so với mức nền."""

import pandas as pd

from src.config import ANOMALY_WINDOW_WEEKS


def breakdown_changes(df, week_start, dims=("description", "platform", "paying_method"),
                      window=ANOMALY_WINDOW_WEEKS, min_tickets=30):
    """Tỷ lệ lỗi tuần này vs trung bình `window` tuần trước, cho từng tổ hợp mã lỗi x nền tảng x phương thức.

    Tỷ lệ = số lỗi của mã đó / số lượt thanh toán của nền tảng x phương thức đó trong tuần.
    """
    week_start = pd.Timestamp(week_start)
    segment = list(dims[1:])
    week = df[df["week"] == week_start]
    past = df[(df["week"] < week_start) & (df["week"] >= week_start - pd.Timedelta(weeks=window))]

    def rates(data):
        attempts = data.groupby(segment).size().rename("attempts")
        errors = data[data["is_failed"]].groupby(list(dims)).size().rename("errors").reset_index()
        merged = errors.merge(attempts.reset_index(), on=segment)
        merged["rate"] = merged["errors"] / merged["attempts"]
        return merged.set_index(list(dims))

    now, base = rates(week), rates(past)
    out = now.join(base[["rate"]].rename(columns={"rate": "baseline_rate"}), how="left").fillna({"baseline_rate": 0})
    out["change_pp"] = (out["rate"] - out["baseline_rate"]) * 100
    out["excess_errors"] = ((out["rate"] - out["baseline_rate"]) * out["attempts"]).clip(lower=0)
    out = out[out["attempts"] >= min_tickets]
    return out.sort_values("excess_errors", ascending=False).reset_index()
