"""Bộ dataset sạch, dùng ngay cho analyst / product (không phải làm sạch lại) + từ điển dữ liệu tự sinh.

    python -m src.marts            # xuất data/marts/*.parquet, *.csv và data_dictionary.md / .csv
"""

import argparse
import os

import numpy as np
import pandas as pd

from src import ingest, marketing
from src import model as failure_model
from src.config import DATA_DIR
from src.data_prep import age_at_reference, age_generation, load_tickets

MARTS_DIR = DATA_DIR / "marts"

TABLES = {
    "fact_payment_attempts": {
        "grain": "1 dòng = 1 lần thanh toán (thành công hoặc lỗi)",
        "key": ["ticket_id"],
    },
    "dim_customer": {
        "grain": "1 dòng = 1 khách hàng trong bảng customer (kể cả khách chưa từng thanh toán)",
        "key": ["customer_id"],
    },
    "customer_features": {
        "grain": "1 dòng = 1 khách đã từng mua thành công, tính tại thời điểm as_of",
        "key": ["customer_id"],
    },
    "campaign_summary": {
        "grain": "1 dòng = 1 campaign_id (0 = không dùng khuyến mãi)",
        "key": ["campaign_id"],
    },
}

DESCRIPTIONS = {
    "ticket_id": "Mã giao dịch (duy nhất)",
    "customer_id": "Mã khách hàng",
    "time": "Thời điểm thanh toán",
    "date": "Ngày thanh toán",
    "week": "Thứ Hai đầu tuần của giao dịch",
    "year_month": "Tháng giao dịch (YYYY-MM)",
    "hour": "Giờ trong ngày (0-23)",
    "day_name": "Thứ trong tuần",
    "paying_method": "Phương thức thanh toán",
    "platform": "Nền tảng: mobile / website / Unknown",
    "os_version": "Hệ điều hành suy ra từ model thiết bị",
    "device_number": "Mã thiết bị",
    "theater_name": "Mã rạp",
    "movie_name": "Tên phim",
    "campaign_id": "Mã campaign (0 = không dùng khuyến mãi)",
    "campaign_type": "Loại khuyến mãi: direct discount / voucher / reward point / none",
    "is_promotion": "Giao dịch có dùng khuyến mãi",
    "original_price": "Giá gốc (đơn vị theo dataset)",
    "discount_value": "Số tiền giảm",
    "final_price": "Giá khách trả = original_price - discount_value",
    "discount_rate": "discount_value / original_price",
    "status_id": "1 = thành công; -1..-7 = mã lỗi",
    "status_description": "Mô tả trạng thái / lỗi",
    "error_group": "Nhóm lỗi: customer / external (ngân hàng) / internal / none",
    "is_success": "Thanh toán thành công",
    "attempt_number": "Lần thanh toán thứ mấy của khách (1 = lần đầu)",
    "is_first_attempt": "Là lần thanh toán đầu tiên của khách",
    "failure_risk_score": "Điểm rủi ro lỗi từ model notebook 03 (0-1, chỉ dùng thông tin trước giao dịch; model train trên 2019-2021 nên điểm của giai đoạn này là in-sample)",
    "usergender": "Giới tính (Not verify = chưa xác minh)",
    "dob": "Ngày sinh",
    "age": "Tuổi tại ngày cuối của dữ liệu",
    "age_generation": "Thế hệ: gen z / gen y / gen x / baby boomers",
    "is_verified_profile": "Có thông tin giới tính & ngày sinh thật (không phải Not verify / autofill 1970)",
    "has_activity": "Khách có ít nhất 1 lần thanh toán",
    "first_attempt_time": "Lần thanh toán đầu tiên",
    "first_success_time": "Lần mua thành công đầu tiên",
    "n_attempts": "Tổng số lần thanh toán",
    "n_success": "Số lần mua thành công",
    "n_failed": "Số lần thanh toán lỗi",
    "success_rate": "n_success / n_attempts",
    "total_spend": "Tổng final_price các giao dịch thành công",
    "total_discount": "Tổng tiền được giảm",
    "first_attempt_failed": "Lần thanh toán đầu tiên bị lỗi",
    "lost_at_first_payment": "Lỗi lần đầu VÀ chưa bao giờ mua thành công",
    "as_of": "Thời điểm tính đặc trưng",
    "recency_days": "Số ngày từ lần mua thành công gần nhất tới as_of",
    "tenure_days": "Số ngày từ lần mua thành công đầu tiên tới as_of",
    "frequency": "Số lần mua thành công trước as_of",
    "n_months": "Số tháng có mua",
    "monetary": "Tổng chi tiêu trước as_of",
    "avg_price": "Giá trung bình mỗi vé",
    "promo_share": "Tỷ lệ giao dịch có khuyến mãi",
    "wallet_share": "Tỷ lệ giao dịch dùng ví trong app",
    "mobile_share": "Tỷ lệ giao dịch qua mobile",
    "segment": "Nhóm khách (luật theo slide báo cáo)",
    "action": "Hướng xử lý đề xuất cho nhóm",
    "repurchase_score": "Xác suất mua lại trong 90 ngày sau as_of (model RFM, AUC backtest ~0.66)",
    "score_source": "Nguồn điểm: model hoặc luật recency (khi thiếu dữ liệu train)",
    "tickets": "Số lượt thanh toán",
    "success_tickets": "Số vé thành công",
    "customers": "Số khách khác nhau",
    "revenue": "Doanh thu (tổng final_price thành công)",
    "discount_spend": "Tổng tiền giảm giá",
    "failure_rate": "Tỷ lệ thanh toán lỗi",
    "new_customers": "Số khách có lần mua đầu tiên bằng campaign này (đủ 90 ngày quan sát)",
    "returned_90d": "Tỷ lệ khách mới mua lần 2 trong 90 ngày",
    "one_time_rate": "1 - returned_90d",
    "discount_per_returned": "Tiền giảm giá cho khách mới / số khách mới quay lại",
}


def fact_payment_attempts(df):
    out = df.rename(columns={"description": "status_description"}).copy()
    out["date"] = out["time"].dt.date
    out["is_promotion"] = out["type"].eq("promotion")
    out["attempt_number"] = out.groupby("customer_id").cumcount() + 1
    out["is_first_attempt"] = out["attempt_number"] == 1
    model_path = failure_model.MODEL_PATH
    if model_path.exists():
        X = failure_model.build_features(df)
        out["failure_risk_score"] = failure_model.load(model_path).predict(X.loc[out.index, failure_model.FEATURES])
    cols = [
        "ticket_id", "customer_id", "time", "date", "week", "year_month", "hour", "day_name",
        "paying_method", "platform", "os_version", "device_number", "theater_name", "movie_name",
        "campaign_id", "campaign_type", "is_promotion", "original_price", "discount_value", "final_price",
        "discount_rate", "status_id", "status_description", "error_group", "is_success",
        "attempt_number", "is_first_attempt", "failure_risk_score",
    ]
    out[["original_price", "discount_value", "final_price"]] = out[["original_price", "discount_value", "final_price"]].round(2)
    out["discount_rate"] = out["discount_rate"].round(4)
    if "failure_risk_score" in out:
        out["failure_risk_score"] = out["failure_risk_score"].round(4)
    return out[[c for c in cols if c in out.columns]].reset_index(drop=True)


def dim_customer(df, customers):
    c = customers.copy()
    c["dob"] = pd.to_datetime(c["dob"], format="mixed")
    c["age"] = age_at_reference(c["dob"], df["time"].max().normalize())
    c["age_generation"] = age_generation(c["dob"])
    g = df.groupby("customer_id")
    success = df[df["is_success"]].groupby("customer_id")
    activity = pd.DataFrame({
        "first_attempt_time": g["time"].min(),
        "first_success_time": success["time"].min(),
        "n_attempts": g.size(),
        "n_success": g["is_success"].sum(),
        "total_spend": success["final_price"].sum(),
        "total_discount": success["discount_value"].sum(),
        "first_attempt_failed": g["is_failed"].first(),
    })
    out = c.set_index("customer_id").join(activity)
    out["has_activity"] = out["n_attempts"].notna()
    for col in ["n_attempts", "n_success", "total_spend", "total_discount"]:
        out[col] = out[col].fillna(0)
    out["n_failed"] = out["n_attempts"] - out["n_success"]
    out["success_rate"] = out["n_success"] / out["n_attempts"].replace(0, np.nan)
    out["first_attempt_failed"] = out["first_attempt_failed"].astype("boolean")
    out["lost_at_first_payment"] = out["first_attempt_failed"].fillna(False) & out["first_success_time"].isna()
    out["is_verified_profile"] = out["usergender"].ne("Not verify") & out["dob"].dt.year.ne(1970)
    for col in ["n_attempts", "n_success", "n_failed"]:
        out[col] = out[col].astype(int)
    return out.reset_index()


def customer_features(df, as_of):
    targets = marketing.target_list(df, as_of)
    features = marketing.customer_features(df, as_of)
    out = features.join(targets[["segment", "action", "score", "score_source"]]).rename(columns={"score": "repurchase_score"})
    out.insert(0, "as_of", pd.Timestamp(as_of))
    return out.rename_axis("customer_id").reset_index()


def campaign_summary(df, campaigns):
    g = df.groupby("campaign_id")
    success = df[df["is_success"]].groupby("campaign_id")
    out = pd.DataFrame({
        "tickets": g.size(),
        "success_tickets": success.size(),
        "customers": success["customer_id"].nunique(),
        "revenue": success["final_price"].sum(),
        "discount_spend": success["discount_value"].sum(),
        "failure_rate": g["is_failed"].mean(),
    })
    effect = marketing.campaign_effectiveness(df, by="campaign_id", min_customers=1)
    out = out.join(effect[["new_customers", "returned_90d", "one_time_rate", "discount_per_returned"]])
    for col in ["success_tickets", "customers"]:
        out[col] = out[col].fillna(0).astype(int)
    out[["revenue", "discount_spend"]] = out[["revenue", "discount_spend"]].fillna(0).round(2)
    out = campaigns.set_index("campaign_id").reindex(out.index).join(out)
    out["campaign_type"] = out["campaign_type"].fillna("none")
    return out.rename_axis("campaign_id").reset_index().sort_values("tickets", ascending=False)


def _example(series):
    values = series.dropna().unique()[:3]
    return ", ".join(str(round(v, 4) if isinstance(v, float) else v)[:40] for v in values)


def data_dictionary(tables):
    rows = []
    for name, table in tables.items():
        for col in table.columns:
            s = table[col]
            numeric = pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)
            rows.append({
                "table": name,
                "column": col,
                "dtype": str(s.dtype),
                "description": DESCRIPTIONS.get(col, ""),
                "null_rate": round(float(s.isna().mean()), 4),
                "n_unique": int(s.nunique()),
                "min": s.min() if numeric or pd.api.types.is_datetime64_any_dtype(s) else "",
                "max": s.max() if numeric or pd.api.types.is_datetime64_any_dtype(s) else "",
                "examples": _example(s),
            })
    return pd.DataFrame(rows)


def dictionary_markdown(tables, dictionary, as_of):
    lines = [f"# Data dictionary - data marts (as_of {pd.Timestamp(as_of).date()})", "",
             "Sinh tự động bởi `python -m src.marts`. File `.parquet` giữ đúng kiểu dữ liệu; `.csv` để mở bằng Excel.", ""]
    for name, table in tables.items():
        meta = TABLES[name]
        lines += [f"## {name}", "", f"- **Grain:** {meta['grain']}", f"- **Khóa chính:** `{', '.join(meta['key'])}`",
                  f"- **Số dòng:** {len(table):,}", "",
                  "| Cột | Kiểu | Mô tả | Null | Unique | Ví dụ |", "|---|---|---|---|---|---|"]
        for _, r in dictionary[dictionary["table"] == name].iterrows():
            lines.append(f"| `{r['column']}` | {r['dtype']} | {r['description']} | {r['null_rate']:.1%} | "
                         f"{r['n_unique']:,} | {str(r['examples']).replace('|', '/')} |")
        lines.append("")
    return "\n".join(lines)


def build(df=None, as_of=None, out_dir=MARTS_DIR, refs=None):
    """refs: bảng tham chiếu đã cập nhật (src.ingest.load_refs) - mặc định là file gốc trong data/."""
    df = load_tickets() if df is None else df
    as_of = pd.Timestamp(as_of) if as_of else df["time"].max().normalize() + pd.Timedelta(days=1)
    customers = refs["customer"] if refs else pd.read_csv(DATA_DIR / "customer.csv")
    campaigns = refs["campaign"] if refs else pd.read_csv(DATA_DIR / "campaign.csv")
    tables = {
        "fact_payment_attempts": fact_payment_attempts(df),
        "dim_customer": dim_customer(df, customers),
        "customer_features": customer_features(df, as_of),
        "campaign_summary": campaign_summary(df, campaigns),
    }
    for name, table in tables.items():
        key = TABLES[name]["key"]
        if table.duplicated(key).any():
            raise ValueError(f"{name}: khóa chính {key} bị trùng")

    out_dir.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        table.to_parquet(out_dir / f"{name}.parquet", index=False)
        table.to_csv(out_dir / f"{name}.csv", index=False, encoding="utf-8-sig")
    dictionary = data_dictionary(tables)
    dictionary.to_csv(out_dir / "data_dictionary.csv", index=False, encoding="utf-8-sig")
    (out_dir / "data_dictionary.md").write_text(dictionary_markdown(tables, dictionary, as_of), encoding="utf-8")
    return tables, dictionary


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--as-of", help="Thời điểm tính customer_features (mặc định: sau ngày cuối dữ liệu)")
    parser.add_argument("--source", choices=["csv", "warehouse"], default="csv")
    args = parser.parse_args()
    os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")
    refs = ingest.load_refs(ingest.Paths()) if args.source == "warehouse" else None
    tables, _ = build(load_tickets(source=args.source), args.as_of, refs=refs)
    for name, table in tables.items():
        print(f"{name:24s} {len(table):>8,} dòng · {table.shape[1]} cột")
    print(f"Đã ghi vào {MARTS_DIR}")


if __name__ == "__main__":
    main()
