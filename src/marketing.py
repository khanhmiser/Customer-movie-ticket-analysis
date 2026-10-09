"""Marketing: phân nhóm khách (theo slide "Phân nhóm khách hàng & chiến lược giữ chân"),
điểm khả năng quay lại trong 90 ngày, và hiệu quả từng loại campaign.
"""

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

HORIZON_DAYS = 90

SEGMENT_ACTIONS = {
    "Khách giá trị cao": "Membership, ưu đãi đặc quyền, đặt vé sớm phim hot",
    "Khách mua một lần (mới)": "Tặng coupon cho lần mua thứ hai trong vòng 7–14 ngày",
    "Khách lâu chưa quay lại": "Kéo lại bằng phim mới, voucher quay lại, thông báo cá nhân hóa",
    "Khách nhạy khuyến mãi": "Chuyển từ giảm giá trực tiếp sang tích điểm, voucher cá nhân hóa",
    "Khách thường xuyên": "Duy trì, không cần giảm giá sâu",
}

FEATURES = [
    "recency_days", "tenure_days", "frequency", "n_months", "monetary", "avg_price",
    "promo_share", "discount_rate", "wallet_share", "mobile_share", "n_failed",
]


def customer_features(df, cut):
    """Đặc trưng RFM của mọi khách đã từng mua thành công TRƯỚC thời điểm `cut`."""
    cut = pd.Timestamp(cut)
    hist = df[df["time"] < cut]
    success = hist[hist["is_success"]].assign(
        is_promo=lambda x: x["type"].eq("promotion"),
        is_wallet=lambda x: x["paying_method"].eq("money in app"),
        is_mobile=lambda x: x["platform"].eq("mobile"),
    )
    g = success.groupby("customer_id")
    X = pd.DataFrame({
        "recency_days": (cut - g["time"].max()).dt.days,
        "tenure_days": (cut - g["time"].min()).dt.days,
        "frequency": g.size(),
        "n_months": g["year_month"].nunique(),
        "monetary": g["final_price"].sum(),
        "avg_price": g["final_price"].mean(),
        "promo_share": g["is_promo"].mean(),
        "discount_rate": g["discount_rate"].mean(),
        "wallet_share": g["is_wallet"].mean(),
        "mobile_share": g["is_mobile"].mean(),
    })
    X["n_failed"] = X.index.map(hist[hist["is_failed"]].groupby("customer_id").size()).fillna(0)
    return X


def label(df, X, cut, horizon=HORIZON_DAYS):
    cut = pd.Timestamp(cut)
    future = df[df["is_success"] & (df["time"] >= cut) & (df["time"] < cut + pd.Timedelta(days=horizon))]
    return X.index.isin(future["customer_id"]).astype(int)


def segment(X):
    """Luật phân nhóm theo slide; mỗi khách thuộc đúng 1 nhóm (xét theo thứ tự ưu tiên)."""
    return pd.Series(
        np.select(
            [
                # giá trị cao nhưng đã lâu không mua -> xếp vào "lâu chưa quay lại" để kéo lại
                (X["frequency"] >= 3) & (X["recency_days"] <= 180),
                (X["frequency"] == 1) & (X["recency_days"] <= 30),
                X["recency_days"] > 90,
                X["promo_share"] >= 0.5,
            ],
            ["Khách giá trị cao", "Khách mua một lần (mới)", "Khách lâu chưa quay lại", "Khách nhạy khuyến mãi"],
            "Khách thường xuyên",
        ),
        index=X.index,
    )


def training_set(df, cuts):
    frames = []
    for cut in cuts:
        X = customer_features(df, cut)
        X["y"] = label(df, X, cut)
        frames.append(X)
    return pd.concat(frames)


def train_propensity(train):
    model = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=15,
                               min_child_samples=100, random_state=42, verbose=-1)
    return model.fit(train[FEATURES], train["y"])


def evaluate_propensity(model, test):
    score = model.predict_proba(test[FEATURES])[:, 1]
    top = np.argsort(-score)[: int(0.2 * len(score))]
    return {
        "AUC model": roc_auc_score(test["y"], score),
        "AUC rule: recency": roc_auc_score(test["y"], -test["recency_days"]),
        "base rate": test["y"].mean(),
        "precision top 20%": test["y"].values[top].mean(),
        "capture top 20%": test["y"].values[top].sum() / test["y"].sum(),
    }


def target_list(df, cut, n_train_cuts=3):
    """Danh sách khách cho Marketing tại thời điểm `cut`: nhóm, điểm quay lại, hành động đề xuất.

    Model train trên các mốc mà nhãn 90 ngày đã quan sát đủ TRƯỚC `cut` (không nhìn tương lai).
    Quá ít dữ liệu để train -> xếp hạng theo recency (mua gần đây hơn = điểm cao hơn).
    """
    cut = pd.Timestamp(cut)
    last_label_cut = cut - pd.Timedelta(days=HORIZON_DAYS)
    cuts = [last_label_cut - pd.DateOffset(months=k) for k in range(n_train_cuts)]
    train = training_set(df, cuts)
    X = customer_features(df, cut)
    if train["y"].sum() >= 200:
        X["score"] = train_propensity(train).predict_proba(X[FEATURES])[:, 1]
        X["score_source"] = "model"
    else:
        X["score"] = 1 / (1 + X["recency_days"])
        X["score_source"] = "rule: recency"
    X["segment"] = segment(X)
    X["action"] = X["segment"].map(SEGMENT_ACTIONS)
    cols = ["segment", "score", "score_source", "action", "recency_days", "frequency", "monetary", "promo_share"]
    return X[cols].sort_values("score", ascending=False).round(4)


def campaign_effectiveness(df, by="campaign_type", min_customers=100):
    """Khách mới đến từ mỗi campaign: bao nhiêu % mua lần 2 trong 90 ngày, tốn bao nhiêu giảm giá
    cho mỗi khách quay lại. Chỉ tính khách có lần mua đầu đủ 90 ngày quan sát.
    """
    data_end = df["time"].max()
    success = df[df["is_success"]]
    first = success.groupby("customer_id").head(1).set_index("customer_id")
    second = success.groupby("customer_id").nth(1).set_index("customer_id")["time"]
    first["returned_90d"] = (second.reindex(first.index) - first["time"]).dt.days <= HORIZON_DAYS
    first = first[first["time"] + pd.Timedelta(days=HORIZON_DAYS) <= data_end]
    out = first.groupby(by).agg(
        new_customers=("ticket_id", "count"),
        returned_90d=("returned_90d", "mean"),
        discount_spend=("discount_value", "sum"),
        n_returned=("returned_90d", "sum"),
    )
    out["one_time_rate"] = 1 - out["returned_90d"]
    out["discount_per_returned"] = out["discount_spend"] / out["n_returned"].replace(0, np.nan)
    out = out[out["new_customers"] >= min_customers]
    return out.sort_values("one_time_rate", ascending=False)
