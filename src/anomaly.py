"""Phát hiện tỷ lệ lỗi thanh toán tăng bất thường theo tuần (robust z-score)."""

import numpy as np
import pandas as pd

from src.config import ANOMALY_MIN_WEEKLY_TICKETS, ANOMALY_WINDOW_WEEKS, ANOMALY_Z_THRESHOLD

ERROR_GROUPS = ["customer", "external", "internal"]
# MAD có thể = 0 khi các tuần trước gần như bằng nhau -> đặt sàn để z không nổ
MIN_SPREAD = 0.003


def robust_z(rate, window=ANOMALY_WINDOW_WEEKS):
    """So tuần hiện tại với median/MAD của `window` tuần TRƯỚC đó (không nhìn tương lai)."""
    past = rate.shift(1).rolling(window, min_periods=window - 2)
    median = past.median()
    mad = past.apply(lambda x: np.median(np.abs(x - np.median(x))), raw=True)
    spread = (1.4826 * mad).clip(lower=MIN_SPREAD)
    return (rate - median) / spread, median


def detect(weekly, z_threshold=ANOMALY_Z_THRESHOLD, min_tickets=ANOMALY_MIN_WEEKLY_TICKETS):
    """Trả về bảng dài: week, error_group, rate, baseline, z, is_alert.

    Chỉ cảnh báo chiều TĂNG và chỉ khi tuần đủ số vé (tuần quá ít vé -> tỷ lệ nhiễu).
    """
    weekly = weekly[weekly["n_tickets"] >= min_tickets]
    frames = []
    for group in ERROR_GROUPS:
        rate = weekly[f"{group}_rate"]
        z, baseline = robust_z(rate)
        frames.append(
            pd.DataFrame(
                {
                    "week": weekly.index,
                    "error_group": group,
                    "n_tickets": weekly["n_tickets"].values,
                    "n_errors": weekly[group].values,
                    "rate": rate.values,
                    "baseline": baseline.values,
                    "z": z.values,
                }
            )
        )
    out = pd.concat(frames, ignore_index=True)
    out["is_alert"] = out["z"] >= z_threshold
    # Số lỗi vượt mức bình thường = (tỷ lệ thực - tỷ lệ nền) x số vé
    out["excess_errors"] = ((out["rate"] - out["baseline"]) * out["n_tickets"]).clip(lower=0)
    return out.sort_values(["week", "error_group"]).reset_index(drop=True)
