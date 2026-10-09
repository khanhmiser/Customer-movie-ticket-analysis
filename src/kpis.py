"""6 nhóm KPI theo tháng - theo đúng slide "Kế hoạch đo lường KPI" của báo cáo.

Dữ liệu không có lượt truy cập/giỏ hàng, nên "tỷ lệ chuyển đổi" được định nghĩa ở mức khách hàng:
trong số khách có thanh toán trong tháng, bao nhiêu % mua thành công ít nhất 1 vé.
"""

import numpy as np
import pandas as pd

# (nhóm KPI, mã chỉ số, tên hiển thị, định dạng, chiều tốt: +1 tăng là tốt / -1 giảm là tốt)
KPI_DEFINITIONS = [
    ("1. Tăng số giao dịch thành công", "success_tickets", "Vé đặt thành công", "int", 1),
    ("1. Tăng số giao dịch thành công", "conversion", "Tỷ lệ chuyển đổi (khách)", "pct", 1),
    ("1. Tăng số giao dịch thành công", "revenue", "Doanh thu", "money", 1),
    ("2. Tăng tỷ lệ khách quay lại", "repeat_90d", "Khách mới mua lần 2 trong 90 ngày", "pct", 1),
    ("2. Tăng tỷ lệ khách quay lại", "retention_30d", "Giữ chân sau 30 ngày", "pct", 1),
    ("3. Giảm phụ thuộc khuyến mãi", "repeat_no_promo_share", "Mua lại không dùng khuyến mãi", "pct", 1),
    ("3. Giảm phụ thuộc khuyến mãi", "discount_per_retained", "Chi phí giảm giá / 1 khách KM quay lại", "money", -1),
    ("4. Cải thiện thanh toán", "payment_success_rate", "Tỷ lệ thanh toán thành công", "pct", 1),
    ("4. Cải thiện thanh toán", "payment_failure_rate", "Tỷ lệ lỗi thanh toán", "pct", -1),
    ("5. Tối ưu mobile", "mobile_conversion", "Tỷ lệ chuyển đổi trên mobile", "pct", 1),
    ("5. Tối ưu mobile", "app_completion_rate", "Tỷ lệ hoàn tất thanh toán trên app", "pct", 1),
    ("6. Nâng cao giá trị khách hàng", "frequency", "Tần suất mua (vé / khách)", "float", 1),
    ("6. Nâng cao giá trị khách hàng", "spend_per_customer", "Chi tiêu TB / khách", "money", 1),
    ("6. Nâng cao giá trị khách hàng", "ltv_to_date", "Giá trị tích lũy TB / khách", "money", 1),
]

MIN_MONTHLY_TICKETS = 500  # tháng quá ít giao dịch (COVID) -> chỉ số nhiễu, ẩn khỏi dashboard


def _first_success(df):
    success = df[df["is_success"]]
    first = success.groupby("customer_id").head(1)[["customer_id", "time", "year_month", "type", "discount_value"]]
    second = success.groupby("customer_id").nth(1)[["customer_id", "time"]].rename(columns={"time": "second_time"})
    first = first.merge(second, on="customer_id", how="left")
    first["gap_days"] = (first["second_time"] - first["time"]).dt.days
    return first


def monthly_kpis(df):
    """Bảng tháng x 14 chỉ số. Chỉ số cần cửa sổ tương lai (30/90 ngày) = NaN nếu chưa đủ dữ liệu."""
    data_end = df["time"].max()
    success = df[df["is_success"]].copy()
    success["is_repeat"] = success.groupby("customer_id").cumcount() > 0
    mobile = df[df["platform"] == "mobile"]

    by_month = df.groupby("year_month")
    out = pd.DataFrame({
        "tickets": by_month.size(),
        "payment_success_rate": by_month["is_success"].mean(),
    })
    out["payment_failure_rate"] = 1 - out["payment_success_rate"]
    out["success_tickets"] = success.groupby("year_month").size()
    out["revenue"] = success.groupby("year_month")["final_price"].sum()

    customer_month = df.groupby(["year_month", "customer_id"])["is_success"].max()
    out["conversion"] = customer_month.groupby("year_month").mean()
    mobile_customer = mobile.groupby(["year_month", "customer_id"])["is_success"].max()
    out["mobile_conversion"] = mobile_customer.groupby("year_month").mean()
    out["app_completion_rate"] = mobile.groupby("year_month")["is_success"].mean()

    first = _first_success(df)
    first["month_end"] = pd.to_datetime(first["year_month"]) + pd.offsets.MonthEnd(0)
    for days, col in [(90, "repeat_90d"), (30, "retention_30d")]:
        rate = first.groupby("year_month")["gap_days"].apply(lambda g, d=days: (g <= d).mean())
        complete = first.groupby("year_month")["month_end"].first() + pd.Timedelta(days=days) <= data_end
        out[col] = rate.where(complete)

    repeat = success[success["is_repeat"]]
    out["repeat_no_promo_share"] = repeat.groupby("year_month")["type"].apply(lambda t: (t == "non-promotion").mean())

    promo_first = first[first["type"] == "promotion"]
    promo = promo_first.groupby("year_month").agg(
        discount=("discount_value", "sum"), retained=("gap_days", lambda g: (g <= 90).sum()))
    complete = promo_first.groupby("year_month")["month_end"].first() + pd.Timedelta(days=90) <= data_end
    out["discount_per_retained"] = (promo["discount"] / promo["retained"].replace(0, np.nan)).where(complete)

    active = success.groupby("year_month")["customer_id"].nunique()
    out["frequency"] = out["success_tickets"] / active
    out["spend_per_customer"] = out["revenue"] / active
    cumulative_customers = first.groupby("year_month").size().reindex(out.index).fillna(0).cumsum()
    out["ltv_to_date"] = out["revenue"].fillna(0).cumsum() / cumulative_customers

    return out.sort_index()


def format_value(value, fmt):
    if pd.isna(value):
        return "n/a"
    if fmt == "money":
        # giá vé ~ vài đơn vị -> giữ 2 số lẻ cho giá trị nhỏ, tổng lớn thì làm tròn
        return f"{value:,.2f}" if abs(value) < 1000 else f"{value:,.0f}"
    return {"int": f"{value:,.0f}", "pct": f"{value * 100:.1f}%", "float": f"{value:.2f}"}[fmt]


def snapshot(kpis, month):
    """Giá trị 14 chỉ số của `month` so với tháng trước (đã format sẵn để đưa vào FACTS)."""
    months = kpis.index.tolist()
    prev = months[months.index(month) - 1] if months.index(month) > 0 else None
    rows = {}
    for group, key, label, fmt, _ in KPI_DEFINITIONS:
        rows.setdefault(group, {})[label] = {
            "value": format_value(kpis.at[month, key], fmt),
            "previous_month": format_value(kpis.at[prev, key], fmt) if prev else "n/a",
        }
    return rows
