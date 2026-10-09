"""Số liệu riêng cho từng phòng ban trong 1 tuần.

Mọi thứ chỉ tính trên dữ liệu TỚI HẾT tuần đang xét, để khi chạy lại tuần cũ (backtest)
bản tin không "nhìn thấy tương lai".
"""

import pandas as pd

from src import finance, kpis, marketing, product
from src.briefs import _fmt_int, _fmt_pct


def _last_valid(series):
    series = series.dropna()
    return (series.index[-1], series.iloc[-1]) if len(series) else (None, None)


def build(df, week_start):
    """Trả về (extra_facts đã format, tables) - tables dùng để xuất CSV / hiển thị trên app."""
    week_start = pd.Timestamp(week_start)
    hist = df[df["time"] < week_start + pd.Timedelta(days=7)]
    week = hist[hist["week"] == week_start]

    # Product / IT
    changes = product.breakdown_changes(hist, week_start)
    top = changes[changes["change_pp"] > 0].head(3)

    # Tài chính
    losses = finance.monthly_losses(hist)
    loss_month, unrecovered = _last_valid(losses["unrecovered_failed_value"])
    discount_month, one_time = _last_valid(losses["discount_one_time"])

    # Marketing
    targets = marketing.target_list(hist, week_start + pd.Timedelta(days=7))
    campaigns = marketing.campaign_effectiveness(hist)
    campaign_ids = marketing.campaign_effectiveness(hist, by="campaign_id", min_customers=300)
    promo_types = campaigns.drop(index="none", errors="ignore")
    segments = targets["segment"].value_counts()

    # Ban lãnh đạo: tháng đầy đủ gần nhất trước tuần này
    kpi_table = kpis.monthly_kpis(hist)
    kpi_table = kpi_table[kpi_table["tickets"] >= kpis.MIN_MONTHLY_TICKETS]
    week_end = week_start + pd.Timedelta(days=7)
    complete_months = [m for m in kpi_table.index if pd.Period(m).end_time < week_end]
    kpi_month = complete_months[-1] if complete_months else None

    errors = week[week["is_failed"]]["description"].value_counts()

    extra = {
        "customer_care": {
            "errors_by_code": {k: _fmt_int(v) for k, v in errors.items()},
        },
        "product_it": {
            "top_increases": [
                {
                    "error": r["description"], "platform": r["platform"], "paying_method": r["paying_method"],
                    "rate": _fmt_pct(r["rate"]), "baseline_rate": _fmt_pct(r["baseline_rate"]),
                    "change_pp": f"{r['change_pp']:.1f}", "excess_errors": _fmt_int(r["excess_errors"]),
                }
                for _, r in top.iterrows()
            ],
        },
        "finance": {
            "unrecovered_month": loss_month or "n/a",
            "failed_value": _fmt_int(losses.at[loss_month, "failed_value"]) if loss_month else "n/a",
            "unrecovered_failed_value": _fmt_int(unrecovered) if loss_month else "n/a",
            "unrecovered_share": _fmt_pct(losses.at[loss_month, "unrecovered_share"]) if loss_month else "n/a",
            "one_time_discount_month": discount_month or "n/a",
            "discount_total": _fmt_int(losses.at[discount_month, "discount_total"]) if discount_month else "n/a",
            "discount_one_time": _fmt_int(one_time) if discount_month else "n/a",
            "one_time_discount_share": _fmt_pct(losses.at[discount_month, "one_time_discount_share"]) if discount_month else "n/a",
        },
        "marketing": {
            "segments": {k: _fmt_int(v) for k, v in segments.items()},
            "segment_actions": marketing.SEGMENT_ACTIONS,
            "score_source": targets["score_source"].iloc[0] if len(targets) else "n/a",
            "campaign_types": {
                k: {"one_time_rate": _fmt_pct(r["one_time_rate"]),
                    "discount_per_returned": _fmt_int(r["discount_per_returned"]) if pd.notna(r["discount_per_returned"]) else "n/a"}
                for k, r in campaigns.iterrows()
            },
            "worst_campaign_type": promo_types.index[0] if len(promo_types) else "n/a",
            "best_campaign_type": promo_types.index[-1] if len(promo_types) else "n/a",
            "campaign_ids_one_time_95pct": _fmt_int((campaign_ids["one_time_rate"] >= 0.95).sum()),
        },
        "leadership": {
            "kpi_month": kpi_month or "n/a",
            "kpis": kpis.snapshot(kpi_table, kpi_month) if kpi_month else {},
        },
    }
    tables = {
        "product_breakdown": changes,
        "monthly_losses": losses,
        "marketing_targets": targets,
        "campaign_effectiveness": campaigns,
        "campaign_ids": campaign_ids,
        "kpis": kpi_table,
    }
    return extra, tables
