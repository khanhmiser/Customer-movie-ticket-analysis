"""Load, làm sạch và join 5 bảng - tái cấu trúc từ phần 1-2 của notebook gốc."""

from pathlib import Path

import numpy as np
import pandas as pd

from src.config import DATA_DIR, PROCESSED_DIR, REFERENCE_DATE

TABLES = ["customer", "ticket_history", "device_detail", "campaign", "status_detail"]


def calc_null_rate(df):
    """Số dòng null và tỷ lệ % của từng cột (giữ nguyên hàm của bản gốc)."""
    newdf = df.isnull().sum().to_frame("null_count")
    newdf["null_rate"] = newdf["null_count"] / len(df)
    return newdf.sort_values(by="null_rate", ascending=False)


def load_raw(data_dir=DATA_DIR):
    return {name: pd.read_csv(data_dir / f"{name}.csv") for name in TABLES}


def _os_version(model):
    # Giữ logic phân loại thiết bị của bản gốc
    return np.select(
        [
            model.str.contains("iPhone|iPod", regex=True),
            model.eq("browser"),
            model.str.contains("devicemodel|Unknown", regex=True),
        ],
        ["ios", "browser", "Unknown"],
        "android and other",
    )


def age_at_reference(dob, reference=REFERENCE_DATE):
    """Tuổi tại ngày `reference` (trừ 1 nếu chưa tới sinh nhật trong năm)."""
    reference = pd.Timestamp(reference)
    before_birthday = (dob.dt.month > reference.month) | (
        (dob.dt.month == reference.month) & (dob.dt.day > reference.day))
    return reference.year - dob.dt.year - before_birthday.astype(int)


def age_generation(dob):
    year = dob.dt.year
    return np.select(
        [year < 1965, year < 1981, year < 1997],
        ["baby boomers", "gen x", "gen y"],
        "gen z",
    )


def clean_and_join(raw):
    """Trả về bảng giao dịch đã làm sạch, mỗi dòng = 1 lần thanh toán (thành công hoặc lỗi)."""
    customer = raw["customer"].copy()
    customer["dob"] = pd.to_datetime(customer["dob"], format="mixed")

    device = raw["device_detail"].copy()
    # model null -> "Unknown"; device_number null -> drop vì là khóa join
    device["model"] = device["model"].fillna("Unknown")
    device = device.dropna(subset=["device_number"])

    ticket = raw["ticket_history"].copy()
    ticket["time"] = pd.to_datetime(ticket["time"])
    # 102 dòng trùng hoàn toàn (đã kiểm tra bằng duplicated(keep=False) ở bản gốc)
    ticket = ticket.drop_duplicates()

    df = (
        ticket.merge(customer, on="customer_id", how="left")
        .merge(raw["campaign"], on="campaign_id", how="left")
        .merge(raw["status_detail"], on="status_id", how="left")
        .merge(device, on="device_number", how="left")
    )

    df["is_success"] = df["status_id"].eq(1)
    df["is_failed"] = ~df["is_success"]
    df["error_group"] = df["error_group"].fillna("none")
    df["campaign_type"] = df["campaign_type"].fillna("none")
    df["type"] = np.where(df["campaign_type"].eq("none"), "non-promotion", "promotion")
    df["model"] = df["model"].fillna("Unknown")
    df["platform"] = df["platform"].fillna("Unknown")
    df["os_version"] = _os_version(df["model"])

    # Tuổi tính tại ngày cuối của dữ liệu đang có -> dữ liệu mới về thì tuổi tự cập nhật
    df["age"] = age_at_reference(df["dob"], df["time"].max().normalize())
    df["age_generation"] = age_generation(df["dob"])
    df["discount_rate"] = df["discount_value"] / df["original_price"].replace(0, np.nan)

    df["year"] = df["time"].dt.year
    df["year_month"] = df["time"].dt.strftime("%Y-%m")
    df["week"] = df["time"].dt.to_period("W-SUN").dt.start_time
    df["hour"] = df["time"].dt.hour
    df["day_name"] = df["time"].dt.day_name()

    return df.sort_values("time").reset_index(drop=True)


def load_tickets(use_cache=True, source="csv", warehouse_dir=None):
    """Bảng giao dịch đã xử lý.

    source="csv"       -> đọc file lịch sử gốc, cache ra parquet để notebook/pipeline/app đọc nhanh
    source="warehouse" -> đọc kho dữ liệu đã nạp theo ngày (src/ingest.py), không cache vì kho thay đổi mỗi ngày
    """
    if source == "warehouse":
        warehouse_dir = Path(warehouse_dir or DATA_DIR / "warehouse" / "ticket_history")
        raw = load_raw()
        raw["ticket_history"] = pd.read_parquet(warehouse_dir)
        # Bảng tham chiếu đã được cập nhật theo ngày (khách mới, campaign mới...) nằm cạnh kho giao dịch
        for name in ["customer", "campaign", "device_detail", "status_detail"]:
            updated = warehouse_dir.parent / "refs" / f"{name}.parquet"
            if updated.exists():
                raw[name] = pd.read_parquet(updated)
        return clean_and_join(raw)
    cache = PROCESSED_DIR / "tickets.parquet"
    if use_cache and cache.exists():
        return pd.read_parquet(cache)
    df = clean_and_join(load_raw())
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache, index=False)
    return df
