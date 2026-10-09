"""Model dự đoán rủi ro thanh toán lỗi TRƯỚC khi khách bấm thanh toán."""

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from src.config import MODELS_DIR, TEST_START

CATEGORICAL = ["paying_method", "platform", "os_version", "campaign_type", "usergender"]
NUMERIC = [
    "hour", "dow", "original_price", "discount_rate", "birth_year",
    "n_prev_attempts", "n_prev_failed", "n_prev_success", "last_attempt_failed",
    "minutes_since_prev",
]
FEATURES = CATEGORICAL + NUMERIC
TARGET = "is_failed"
MODEL_PATH = MODELS_DIR / "payment_failure_lgbm.txt"


def build_features(df):
    """Chỉ dùng thông tin có tại thời điểm giao dịch (lịch sử TRƯỚC giao dịch này).

    Mọi biến lịch sử đều trừ đi chính giao dịch hiện tại để tránh data leakage.
    """
    X = df.sort_values("time").copy()
    g = X.groupby("customer_id")
    failed = X["is_failed"].astype(int)
    X["n_prev_attempts"] = g.cumcount()
    X["n_prev_failed"] = failed.groupby(X["customer_id"]).cumsum() - failed
    X["n_prev_success"] = X["n_prev_attempts"] - X["n_prev_failed"]
    X["last_attempt_failed"] = failed.groupby(X["customer_id"]).shift(1).fillna(0)
    X["minutes_since_prev"] = (X["time"] - g["time"].shift(1)).dt.total_seconds().div(60).fillna(-1)
    X["dow"] = X["time"].dt.dayofweek
    X["birth_year"] = X["dob"].dt.year
    for col in CATEGORICAL:
        X[col] = X[col].fillna("unknown").astype("category")
    X[TARGET] = X[TARGET].astype(int)
    return X


def time_split(X, test_start=TEST_START):
    return X[X["time"] < test_start], X[X["time"] >= test_start]


def train(train_df):
    model = lgb.LGBMClassifier(
        n_estimators=400, learning_rate=0.05, num_leaves=31,
        min_child_samples=50, random_state=42, verbose=-1,
    )
    model.fit(train_df[FEATURES], train_df[TARGET])
    return model


def capture_at(y_true, score, top_frac):
    """Nếu chỉ can thiệp top_frac giao dịch rủi ro nhất thì bắt được bao nhiêu % ca lỗi."""
    n_top = int(len(score) * top_frac)
    top = np.argsort(-np.asarray(score))[:n_top]
    return float(np.asarray(y_true)[top].sum() / np.asarray(y_true).sum())


def rule_baseline_score(train_df, test_df, col="paying_method"):
    """Baseline 1 biến: tỷ lệ lỗi lịch sử của phương thức thanh toán."""
    rate = train_df.groupby(col, observed=True)[TARGET].mean()
    return test_df[col].map(rate).astype(float).fillna(train_df[TARGET].mean())


def evaluate(model, train_df, test_df, top_fracs=(0.1, 0.2, 0.3)):
    y = test_df[TARGET]
    model_score = model.predict_proba(test_df[FEATURES])[:, 1]
    # Phá hòa ngẫu nhiên cho baseline: baseline chỉ có vài giá trị nên nhiều vé bằng điểm nhau
    rng = np.random.default_rng(42)
    rule_score = rule_baseline_score(train_df, test_df).values + rng.uniform(0, 1e-6, len(test_df))
    rows = []
    for name, score in [("Rule: paying_method", rule_score), ("LightGBM", model_score)]:
        row = {"model": name, "AUC": roc_auc_score(y, score)}
        for frac in top_fracs:
            row[f"capture@{int(frac * 100)}%"] = capture_at(y, score, frac)
        rows.append(row)
    return pd.DataFrame(rows).set_index("model")


def explain(model, X):
    """Đóng góp SHAP của từng biến (LightGBM tự tính, không cần cài thư viện shap)."""
    contrib = model.booster_.predict(X[FEATURES], pred_contrib=True)
    return pd.DataFrame(contrib[:, :-1], columns=FEATURES, index=X.index)


def save(model, path=MODEL_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    model.booster_.save_model(str(path))


def load(path=MODEL_PATH):
    return lgb.Booster(model_file=str(path))
