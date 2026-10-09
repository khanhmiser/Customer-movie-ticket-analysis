"""Sinh lại 6 notebook trong notebooks/ từ nội dung định nghĩa ở đây (không sửa tay JSON của notebook).

Chạy:  python scripts/build_notebooks.py            # ghi đè notebooks/0*.ipynb (chưa có output)
        python -m nbconvert --to notebook --execute --inplace notebooks/0X_*.ipynb   # chạy để có output
"""
import sys
from pathlib import Path

import nbformat as nbf

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "notebooks"

SETUP = """import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd().parent))  # để import được thư mục src/

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import seaborn as sns

pd.set_option("display.max_columns", None)
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False})
BLUE, RED, GREY = "#2f6db5", "#d1495b", "#9aa5b1\""""


def nb(cells):
    book = nbf.v4.new_notebook()
    book.metadata["kernelspec"] = {"display_name": "analyst", "language": "python", "name": "python3"}
    book.cells = [nbf.v4.new_markdown_cell(c[3:]) if c.startswith("MD:") else nbf.v4.new_code_cell(c) for c in cells]
    return book


# ---------------------------------------------------------------- 01
NB1 = [
"""MD:# 01 · Chuẩn bị dữ liệu & phân tích hành vi đặt vé (2019–2022)

Notebook này **dựng lại phần phân tích gốc** (`file analyst.ipynb`, 195 cell) gọn hơn, dùng chung code trong `src/` để notebook, pipeline và app cho cùng một kết quả.

**Những điểm đã sửa so với bản gốc** (ghi rõ để minh bạch):

| # | Bản gốc | Sửa lại |
|---|---|---|
| 1 | Cohort "2022" lọc `time < "2020-01-01"` → thực ra vẽ lại dữ liệu 2019 | Lọc đúng năm 2022 (mục 3.6) |
| 2 | Bảng giá trị khách chỉ tính khách có ≥1 giao dịch thành công → **13,701 khách chưa mua được vé bị loại khỏi phân tích** | Tính trên toàn bộ khách (mục 3.5) |
| 3 | Phần "khách có success rate thấp bị lỗi gì" vẽ nhầm `df_error` (toàn bộ khách) thay vì `df_error_0` | So sánh đúng: khách chưa từng mua được vs khách bị lỗi nhưng vẫn mua được (mục 3.7) |
| 4 | Chỉ vẽ 6 mã lỗi, bỏ sót *Payment overdue* | Đủ **7 mã lỗi** |
| 5 | Tuổi tính theo `date.today()` → mỗi lần chạy ra kết quả khác | Tính tại ngày cuối dữ liệu 2022-12-31 |
| 6 | Biểu đồ miền 100% truyền `bank account_pct` hai lần | Mỗi phương thức một lần |""",
SETUP,
"""from src.data_prep import calc_null_rate, clean_and_join, load_raw, load_tickets
from src import metrics""",
"""MD:## 1. Load & kiểm tra dữ liệu""",
"""raw = load_raw()
pd.DataFrame({name: tbl.shape for name, tbl in raw.items()}, index=["rows", "cols"]).T""",
"""calc_null_rate(raw["device_detail"])""",
"""ticket = raw["ticket_history"]
print("ticket_id trùng:", ticket["ticket_id"].count() - ticket["ticket_id"].nunique())
print("dòng trùng hoàn toàn (keep=False):", ticket.duplicated(keep=False).sum())""",
"""MD:- `device_detail`: 5.1% `model` null → điền `"Unknown"`; 1 dòng `device_number` null → drop vì là khóa join.
- `ticket_history`: 102 `ticket_id` lặp và đều là **dòng trùng hoàn toàn** → `drop_duplicates()`.

## 2. Làm sạch & join
`ticket_history` là bảng gốc, LEFT JOIN lần lượt `customer → campaign → status → device` (logic trong `src/data_prep.py`).""",
"""df = load_tickets(use_cache=False)  # chạy lại toàn bộ làm sạch + lưu cache parquet cho các notebook sau
print(f"{len(df):,} lượt thanh toán | {df['is_success'].sum():,} thành công | {df['customer_id'].nunique():,} khách")
print("Khoảng thời gian:", df["time"].min().date(), "→", df["time"].max().date())""",
"""raw["status_detail"]""",
"""MD:Dữ liệu có **7 mã lỗi** chia 3 nhóm: `customer` (lỗi phía khách), `external` (ngân hàng/bên thứ ba), `internal` (hệ thống).

## 3. Phân tích
### 3.1 Chân dung khách hàng""",
"""customers = df.drop_duplicates("customer_id")
gender = customers["usergender"].value_counts()
not_verify = customers[customers["usergender"] == "Not verify"]
print(gender.to_frame("customers").assign(share=lambda x: (x["customers"] / x["customers"].sum()).round(3)))
print(f"\\n'Not verify' có năm sinh 1970: {(not_verify['dob'].dt.year == 1970).mean():.1%}")""",
"""MD:Nhóm **Not verify (~11%)** gần như đều có năm sinh 1970 → hệ thống tự điền khi khách không nhập ngày sinh. Nhóm này bị loại khi phân tích tuổi/thế hệ để không làm lệch phân bổ.""",
"""verified = customers[customers["usergender"] != "Not verify"]
fig, ax = plt.subplots(1, 2, figsize=(13, 4))
ax[0].hist(verified["age"], bins=30, color=BLUE)
ax[0].set(title="Phân bổ độ tuổi (tại 2022-12-31)", xlabel="Tuổi", ylabel="Số khách")
gen = verified["age_generation"].value_counts()
ax[1].pie(gen, labels=gen.index, autopct="%1.1f%%", startangle=90, colors=[BLUE, "#7fa7d9", GREY, "#cfd6de"])
ax[1].set_title("Tỷ trọng thế hệ")
plt.tight_layout()
print(f"Khách 26–35 tuổi: {verified['age'].between(26, 35).mean():.1%}")""",
"""MD:> ⚠️ README trên GitHub ghi *"75% khách 26–35 tuổi"* — tính lại trên dữ liệu chỉ ra **~54%** (tuổi tại ngày cuối dữ liệu). Cần sửa README cho khớp. Gen Y là nhóm chính (~59%), Gen Z ~36%.

### 3.2 Khách mua vé khi nào
Tạo `dim_time` đủ 48 tháng rồi LEFT JOIN để **lộ ra các tháng không có giao dịch (COVID)** thay vì bị ẩn đi.""",
"""dim_time = pd.DataFrame({"year_month": pd.date_range("2019-01-01", "2022-12-31", freq="MS").strftime("%Y-%m")})
monthly = dim_time.merge(df.groupby("year_month").size().rename("tickets").reset_index(), how="left").fillna(0)
week_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
weekday = df["day_name"].value_counts().reindex(week_order)
hourly = df["hour"].value_counts().sort_index()

fig = plt.figure(figsize=(14, 7))
ax1 = plt.subplot(2, 1, 1)
ax1.fill_between(monthly["year_month"], monthly["tickets"], color=BLUE)
ax1.set_title("Lượt thanh toán theo tháng (tháng trống = giai đoạn COVID)")
ax1.tick_params(axis="x", rotation=90)
ax2 = plt.subplot(2, 2, 3); ax2.bar(weekday.index, weekday, color=BLUE); ax2.set_title("Theo thứ trong tuần")
ax2.tick_params(axis="x", rotation=45)
ax3 = plt.subplot(2, 2, 4); ax3.bar(hourly.index, hourly, color=BLUE); ax3.set_title("Theo giờ"); ax3.set_xticks(range(24))
plt.tight_layout()

daily = df.groupby(df["time"].dt.date).size()
dow = pd.to_datetime(pd.Series(daily.index)).dt.dayofweek.values
print("Tháng không có giao dịch:", int((monthly["tickets"] == 0).sum()))
print(f"TB vé/ngày thứ 7–CN so với thứ 2–5: {daily[dow >= 5].mean() / daily[dow <= 3].mean():.2f} lần")""",
"""MD:- **3 tháng không có giao dịch nào** (04/2020, 08–09/2021) và nhiều tháng chỉ vài vé đến vài chục vé (rạp đóng cửa vì COVID). Không có `dim_time` thì biểu đồ sẽ nối liền các tháng và che mất khoảng trống.
- Cuối tuần (thứ 7–CN) trung bình **~1.8 lần** ngày thường (thứ 2–5); README ghi 1.5 lần → nên cập nhật.

### 3.3 Nền tảng, thiết bị, phương thức thanh toán""",
"""platform = df["platform"].value_counts(normalize=True)
mobile = df[df["platform"] == "mobile"]
os_share = mobile["os_version"].value_counts(normalize=True)
print("Nền tảng:", platform.round(3).to_dict())
print("Hệ điều hành trong giao dịch mobile:", os_share.round(3).to_dict())""",
"""MD:- **89% giao dịch qua mobile app.**
- iOS chiếm **37%** giao dịch mobile, nhưng **47.5% không xác định được hệ điều hành** (`devicemodel`/`Unknown`) → con số "55% dùng iOS" trong README không tái lập được; nên ghi kèm hạn chế dữ liệu thiết bị.""",
"""method = metrics.failure_rate_by(df[df["paying_method"] != "other"], "paying_method")
fig, ax = plt.subplots(1, 2, figsize=(13, 4))
share = df.loc[df["is_success"] & (df["paying_method"] != "other"), "paying_method"].value_counts(normalize=True)
ax[0].barh(share.index, share, color=BLUE); ax[0].set_title("Tỷ trọng vé thành công theo phương thức")
ax[0].xaxis.set_major_formatter(mtick.PercentFormatter(1))
ax[1].barh(method.index, method["failure_rate"], color=[RED if r > 0.1 else BLUE for r in method["failure_rate"]])
ax[1].set_title("Tỷ lệ thanh toán LỖI theo phương thức")
ax[1].xaxis.set_major_formatter(mtick.PercentFormatter(1))
for i, r in enumerate(method["failure_rate"]):
    ax[1].text(r, i, f" {r:.1%}", va="center")
plt.tight_layout()
method""",
"""MD:**Phát hiện mới (bản gốc chưa có):** tỷ lệ lỗi chênh nhau rất lớn theo phương thức — *money in app* chỉ **2.6%**, trong khi *debit card* **27.3%**, *credit card* 22.3%, *bank account* 20.1%. Đây là **tương quan**, chưa phải nhân quả (ví trong app không phải gọi sang ngân hàng) — sẽ phân tích tiếp ở notebook 02–03.

### 3.4 Khuyến mãi""",
"""success = df[df["is_success"]]
promo_per_customer = success[success["type"] == "promotion"].groupby("customer_id").size()
print(f"Vé thành công có khuyến mãi: {success['type'].eq('promotion').mean():.1%}")
print(f"Khách (có mua thành công) từng dùng khuyến mãi: {len(promo_per_customer) / success['customer_id'].nunique():.1%}")
print(f"... trong đó chỉ dùng đúng 1 lần: {(promo_per_customer == 1).mean():.1%}")
print(f"Vé khuyến mãi thuộc 'direct discount': {(success.loc[success['type'] == 'promotion', 'campaign_type'] == 'direct discount').mean():.1%}")""",
"""MD:Khớp với bản gốc: **~65% khách từng dùng khuyến mãi, ~89% trong số đó chỉ dùng 1 lần**, và khuyến mãi chủ yếu là *direct discount* (~87%).

### 3.5 Giá trị khách hàng — tính trên TOÀN BỘ khách
Bản gốc tính chỉ số từ giao dịch thành công rồi mới ghép phần lỗi, nên khách **chưa từng mua thành công** biến mất khỏi bảng. Sửa lại: gom trên mọi lượt thanh toán.""",
"""customer_value = (
    df.assign(
        money_success=df["original_price"].where(df["is_success"], 0),
        discount_success=df["discount_value"].where(df["is_success"], 0),
    )
    .groupby("customer_id")
    .agg(
        n_total=("ticket_id", "count"),
        n_success=("is_success", "sum"),
        s_money=("money_success", "sum"),
        s_discount=("discount_success", "sum"),
    )
)
customer_value["success_rate"] = customer_value["n_success"] / customer_value["n_total"]
print(f"Khách có success_rate = 0 (chưa từng mua được vé): {(customer_value['success_rate'] == 0).sum():,}")
customer_value["n_success"].clip(upper=10).value_counts().sort_index().rename("customers").to_frame().T""",
"""MD:**13,701 khách (11.5% tổng khách) chưa từng mua được vé nào** — nhóm này không xuất hiện trong phân tích gốc. Đây là điểm xuất phát của notebook 02.

### 3.6 Cohort retention — 2019 vs 2022 (đã sửa bộ lọc năm)""",
"""from operator import attrgetter


def cohort_matrix(data, year):
    x = data[data["is_success"] & (data["year"] == year)].copy()
    x["first_month"] = x.groupby("customer_id")["time"].transform("min").dt.to_period("M")
    x["k"] = (x["time"].dt.to_period("M") - x["first_month"]).apply(attrgetter("n"))
    counts = x.groupby(["first_month", "k"])["customer_id"].nunique().unstack()
    return counts.div(counts[0], axis=0), counts[0]


fig, axes = plt.subplots(1, 2, figsize=(15, 5))
for ax, year in zip(axes, [2019, 2022]):
    matrix, size = cohort_matrix(df, year)
    sns.heatmap(matrix.iloc[:, 1:], annot=True, fmt=".0%", cmap="Blues", cbar=False, ax=ax, annot_kws={"size": 7})
    ax.set(title=f"Retention theo cohort {year} (tháng 1+)", xlabel="Số tháng sau lần mua đầu", ylabel="")
    print(f"{year}: retention tháng 1 trung bình = {matrix[1].mean():.1%}, tháng 3 = {matrix[3].mean():.1%}")
plt.tight_layout()""",
"""MD:Sau khi sửa bộ lọc, retention tháng 1 là **4.3% (2019)** và **3.7% (2022)**: thấp ở cả hai năm, và 2022 còn thấp hơn một chút **dù 2022 chạy khuyến mãi nhiều hơn**. Kết luận "retention không cải thiện" của bản gốc vẫn đúng hướng, nhưng giờ đã dựa trên dữ liệu 2022 thật.

### 3.7 Tỷ lệ thanh toán thành công & lỗi""",
"""sr = df.groupby("year_month").agg(tickets=("ticket_id", "count"), success_rate=("is_success", "mean"))
fig, ax1 = plt.subplots(figsize=(15, 4))
ax1.bar(sr.index, sr["tickets"], color="#c9d8ee")
ax1.tick_params(axis="x", rotation=90)
ax2 = ax1.twinx()
ax2.plot(sr.index, sr["success_rate"], color=RED, marker="o", ms=3)
ax2.yaxis.set_major_formatter(mtick.PercentFormatter(1))
ax1.set_title("Số lượt thanh toán (cột) và tỷ lệ thành công (đường) theo tháng")
plt.tight_layout()""",
"""errors = df[df["is_failed"]].pivot_table(index="year_month", columns="description", values="ticket_id", aggfunc="count")
errors.loc["2021-12":].plot(figsize=(15, 4), marker="o", ms=3, title="Số lỗi theo mã lỗi (đủ 7 mã) — từ 12/2021")
plt.legend(bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8)
plt.tight_layout()""",
"""never = customer_value[customer_value["success_rate"] == 0].index
recovered = customer_value[customer_value["success_rate"].between(0, 1, inclusive="neither")].index
failed_tx = df[df["is_failed"]]
compare = {}
for label, ids in [(f"chưa từng mua được ({len(never):,} khách)", never), (f"lỗi nhưng vẫn mua được ({len(recovered):,} khách)", recovered)]:
    group = failed_tx[failed_tx["customer_id"].isin(ids)]
    compare[label] = pd.concat([group["error_group"].value_counts(normalize=True), group["paying_method"].value_counts(normalize=True)])
pd.DataFrame(compare).round(3)""",
"""MD:- Lỗi **external (ngân hàng)** chiếm ~3/4 số lỗi và tăng vọt từ tháng 3/2022 — khách không tự khắc phục được.
- Khách *bỏ đi hẳn* và khách *vẫn mua được* gặp **cùng loại lỗi** với tỷ trọng gần như nhau (external 73% vs 78%). Khác biệt không nằm ở loại lỗi, mà ở việc **có thử lại hay không** → cần chủ động liên hệ lại khách bị lỗi. Notebook 04 dựng hệ thống cảnh báo sớm cho đúng loại sự cố này.

## Tóm tắt
| Chủ đề | Kết quả |
|---|---|
| Quy mô | 154,725 lượt thanh toán · 133,679 thành công · 119,477 khách · 2019–2022 |
| Kênh | 89% qua mobile app |
| Thời gian | Cuối tuần ~1.8 lần ngày thường; nhiều tháng trống do COVID |
| Khuyến mãi | ~65% khách dùng khuyến mãi, ~89% chỉ dùng 1 lần; retention tháng 1 chỉ 3.7–4.3% |
| Thanh toán | Tỷ lệ lỗi: money in app 2.6% vs thẻ/ngân hàng 20–27% |
| **Bị bỏ sót ở bản gốc** | **13,701 khách chưa từng mua được vé** → notebook 02 |""",
]

# ---------------------------------------------------------------- 02
NB2 = [
"""MD:# 02 · Tìm ra vấn đề: khách hàng bị mất ở bước thanh toán

**Câu hỏi kinh doanh:** công ty đang chi tiền khuyến mãi để kéo khách mới — vậy có bao nhiêu khách đã muốn mua nhưng **không mua được**, và mất ở đâu?

Quy trình: đặt giả thuyết → kiểm tra → bác bỏ / điều chỉnh → định lượng tác động → xác định ai chịu trách nhiệm.""",
SETUP,
"""from src.data_prep import load_tickets
from src import metrics

df = load_tickets()
first = metrics.first_attempts(df)""",
"""MD:## 1. Giả thuyết ban đầu: "khách bị lỗi thanh toán lần đầu thì ít quay lại hơn"
So sánh: khách lỗi lần đầu có giao dịch thành công sau đó không, với khách thành công lần đầu có mua tiếp không.""",
"""failed_first = first[first["first_failed"]]
ok_first = first[~first["first_failed"]]
later_success = df[df["is_success"]].groupby("customer_id").size()
print(f"Khách lỗi lần đầu, sau đó có mua thành công: {failed_first['ever_converted'].mean():.1%}")
print(f"Khách thành công lần đầu, sau đó mua thêm: {(ok_first.index.map(later_success) > 1).mean():.1%}")""",
"""MD:**Giả thuyết không được ủng hộ** — và hai con số trên thật ra đo hai thứ khác nhau (với nhóm lỗi, "mua thành công sau đó" phần lớn là *thử lại ngay*, chưa phải "quay lại"). Câu hỏi đúng hơn là: **khách lỗi lần đầu có bao giờ trở thành khách hàng không?**

## 2. Phễu: từ lần thanh toán đầu tiên đến khách bị mất""",
"""s = metrics.lost_at_payment_summary(df)
funnel = pd.Series({
    "Khách có thanh toán": s["customers_total"],
    "Lỗi ngay lần đầu": s["failed_first_attempt"],
    "Không bao giờ mua được": s["never_converted"],
})
fig, ax = plt.subplots(figsize=(10, 3))
ax.barh(funnel.index[::-1], funnel.values[::-1], color=[RED, "#e89aa5", BLUE])
for i, v in enumerate(funnel.values[::-1]):
    ax.text(v, i, f" {v:,}", va="center")
ax.set_title("Phễu khách hàng ở bước thanh toán đầu tiên")
plt.tight_layout()
print(f"Lỗi lần đầu: {s['failed_first_attempt_pct']:.1%} tổng khách")
print(f"Không bao giờ mua được: {s['never_converted_pct_of_failed']:.1%} số khách lỗi lần đầu")
print(f"Thử lại thành công trong 1 giờ: {s['recovered_within_1h']:,} | trong 24 giờ: {s['recovered_within_24h']:,}")
print(f"Tỷ lệ MỌI giao dịch lỗi được mua lại trong 7 ngày: {metrics.recovery_rate(df, 7):.1%}")""",
"""MD:> 🔴 **16,802 khách (14.1%) lỗi thanh toán ngay lần đầu, và 13,701 người (81.5%) trong số đó không bao giờ mua được vé.**
> Chỉ khoảng 1,000 khách tự thử lại thành công trong 24 giờ; tính trên mọi giao dịch lỗi, chỉ **7.1%** được mua lại trong 7 ngày.

Hiện **không có quy trình nào liên hệ lại** những khách này — họ đến (thường nhờ khuyến mãi), gặp lỗi và rời đi.

## 3. Khách bị mất vì lỗi gì, qua phương thức nào, khi nào?""",
"""lost = first[first["first_failed"] & ~first["ever_converted"]]
fig, ax = plt.subplots(1, 3, figsize=(16, 4))
by_error = lost["description"].str.slice(0, 32).value_counts()
ax[0].barh(by_error.index[::-1], by_error.values[::-1], color=BLUE); ax[0].set_title("Theo mã lỗi")
by_method = lost["paying_method"].value_counts(normalize=True)
ax[1].bar(by_method.index, by_method, color=BLUE); ax[1].set_title("Theo phương thức thanh toán")
ax[1].yaxis.set_major_formatter(mtick.PercentFormatter(1)); ax[1].tick_params(axis="x", rotation=20)
by_year = lost["year"].value_counts().sort_index()
ax[2].bar(by_year.index.astype(str), by_year, color=BLUE); ax[2].set_title("Theo năm")
plt.tight_layout()
lost["error_group"].value_counts(normalize=True).round(3)""",
"""MD:- **2 mã lỗi phía ngân hàng** (*Payment failed from bank* 7,775 + *No response from your bank* 2,312) gây mất ~74% số khách này → khách **không tự sửa được**.
- **52.5% khách bị mất dùng bank account**; chỉ 8.9% dùng ví trong app.
- 2022 là năm mất nhiều nhất (7,436 khách) — trùng với đợt lỗi ngân hàng tăng vọt và giai đoạn chạy khuyến mãi mạnh.

## 4. Định lượng tác động
> Đơn vị tiền theo đúng cột `final_price` của dataset. Các kịch bản dưới đây là **ước tính**, không phải kết quả đã xảy ra.""",
"""value_lost = s["lost_first_order_value"]
scenarios = pd.DataFrame({"tỷ lệ cứu được": [0.10, 0.20, 0.30]})
scenarios["khách cứu được"] = (scenarios["tỷ lệ cứu được"] * s["never_converted"]).round().astype(int)
scenarios["giá trị đơn đầu cứu được"] = (scenarios["tỷ lệ cứu được"] * value_lost).round()
print(f"Giá trị đơn đầu tiên của 13,701 khách bị mất: {value_lost:,.0f}")
print(f"Giá vé thành công trung bình: {s['avg_success_ticket_value']:.2f}")
scenarios.style.format({"tỷ lệ cứu được": "{:.0%}", "giá trị đơn đầu cứu được": "{:,.0f}"})""",
"""MD:Con số trên **chỉ tính đơn đầu tiên** — chưa tính chi phí khuyến mãi/quảng cáo đã bỏ ra để kéo khách đó vào, và các lần mua sau nếu khách ở lại. Vì vậy đây là **cận dưới** của thiệt hại.

## 5. Ai chịu ảnh hưởng — vấn đề xuyên phòng ban

| Phòng ban | Họ đang thấy gì | Thực chất |
|---|---|---|
| **Marketing** | Chi khuyến mãi, khách mới tăng nhưng giữ chân kém | Một phần khách mới **chưa bao giờ mua được** vì lỗi thanh toán |
| **CSKH** | Nhận phàn nàn rời rạc | Không có danh sách khách lỗi để chủ động liên hệ lại |
| **Product / IT** | Lỗi ngân hàng "không phải lỗi của mình" | 3/4 khách bị mất là do lỗi external; ví trong app lỗi chỉ 2.6% |
| **Tài chính** | Doanh thu thấp hơn kỳ vọng | Đơn lỗi không được cứu = doanh thu mất ngay ở bước cuối |

## 6. Từ vấn đề → giải pháp (các notebook tiếp theo)
1. **Phòng ngừa** (notebook 03): model dự đoán giao dịch có rủi ro lỗi cao → gợi ý phương thức an toàn hơn trước khi thanh toán.
2. **Phát hiện sớm** (notebook 04): cảnh báo khi tỷ lệ lỗi một nhóm tăng bất thường trong tuần.
3. **Cứu đơn tự động** (notebook 04): danh sách khách lỗi + tin nhắn theo mã lỗi gửi cho CSKH mỗi tuần.
4. **Bản tin & dữ liệu cho từng phòng ban** (notebook 04–05): LLM viết bản tin từ số liệu đã tính sẵn, có kiểm tra chống bịa số.""",
]

# ---------------------------------------------------------------- 03
NB3 = [
"""MD:# 03 · Model dự đoán rủi ro thanh toán lỗi

**Mục tiêu:** trước khi khách bấm thanh toán, ước lượng xác suất giao dịch bị lỗi → với giao dịch rủi ro cao, gợi ý phương thức an toàn hơn (ví trong app) hoặc hướng dẫn trước.

**Nguyên tắc:**
- Chỉ dùng thông tin **có tại thời điểm thanh toán** (lịch sử *trước* giao dịch đó) → tránh data leakage.
- Chia **theo thời gian**: train 2019–2021, test 2022 — mô phỏng đúng cách model được dùng thật.
- So với **baseline đơn giản** trước khi kết luận model có giá trị.""",
SETUP,
"""import os
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")
from sklearn.metrics import roc_auc_score
from src.data_prep import load_tickets
from src import model as fm

df = load_tickets()
X = fm.build_features(df)
train_df, test_df = fm.time_split(X)
print(f"Train: {len(train_df):,} (tỷ lệ lỗi {train_df['is_failed'].mean():.1%}) | Test 2022: {len(test_df):,} (tỷ lệ lỗi {test_df['is_failed'].mean():.1%})")
print("Features:", fm.FEATURES)""",
"""MD:## 1. Train & so với baseline
Baseline = tỷ lệ lỗi lịch sử của **phương thức thanh toán** (một biến duy nhất).
`capture@20%`: nếu chỉ can thiệp 20% giao dịch rủi ro nhất thì bắt được bao nhiêu % ca lỗi (chọn ngẫu nhiên thì = 20%).""",
"""lgbm = fm.train(train_df)
results = fm.evaluate(lgbm, train_df, test_df)
results.style.format("{:.3f}")""",
"""MD:**Đọc kết quả một cách trung thực:**
- LightGBM tốt hơn ngẫu nhiên rõ rệt: nhắm 20% giao dịch rủi ro nhất bắt được **~43% ca lỗi** (≈2.2 lần so với chọn ngẫu nhiên).
- Nhưng LightGBM **chỉ nhỉnh hơn một chút** so với baseline một biến (AUC ~0.77 vs ~0.75; capture@20% ~43% vs ~42%) → **phần lớn tín hiệu nằm ở phương thức thanh toán**. Hệ quả kinh doanh: đòn bẩy lớn nhất không phải "model phức tạp" mà là **khuyến khích khách dùng phương thức ít lỗi**.
- Model vẫn có ích ở chỗ xếp hạng chi tiết hơn *bên trong* từng phương thức (giờ, giá vé, lịch sử lỗi của khách…).

## 2. Model đang dựa vào đâu? (SHAP)""",
"""contrib = fm.explain(lgbm, test_df)
importance = contrib.abs().mean().sort_values()
fig, ax = plt.subplots(figsize=(8, 5))
ax.barh(importance.index, importance, color=BLUE)
ax.set_title("Mức ảnh hưởng trung bình |SHAP| lên dự đoán (test 2022)")
plt.tight_layout()""",
"""MD:## 3. Tỷ lệ lỗi thực tế theo nhóm rủi ro""",
"""test_scored = test_df.assign(risk=lgbm.predict_proba(test_df[fm.FEATURES])[:, 1])
test_scored["risk_decile"] = pd.qcut(test_scored["risk"].rank(method="first"), 10, labels=range(1, 11))
deciles = test_scored.groupby("risk_decile", observed=True).agg(
    predicted=("risk", "mean"), actual=("is_failed", "mean"), tickets=("ticket_id", "count"))
fig, ax = plt.subplots(figsize=(9, 4))
ax.bar(deciles.index.astype(str), deciles["actual"], color=BLUE, label="Tỷ lệ lỗi thực tế")
ax.plot(deciles.index.astype(str), deciles["predicted"], color=RED, marker="o", label="Model dự đoán")
ax.yaxis.set_major_formatter(mtick.PercentFormatter(1))
ax.set(title="Tỷ lệ lỗi theo nhóm rủi ro (1 = thấp nhất, 10 = cao nhất)", xlabel="Nhóm rủi ro (decile)")
ax.legend()
plt.tight_layout()
deciles.round(3)""",
"""MD:Thứ tự xếp hạng tốt (nhóm 10 lỗi nhiều gấp ~30 lần nhóm 1), nhưng model **dự đoán cao hơn thực tế** ở các nhóm rủi ro cao — vì tỷ lệ lỗi giai đoạn train (16.7%) cao hơn năm 2022 (11.6%). Nếu dùng *xác suất* (không chỉ thứ hạng) để ra quyết định thì cần hiệu chỉnh lại (calibration) trên dữ liệu gần nhất.

## 4. Những gì ĐÃ THỬ nhưng KHÔNG hiệu quả
Ghi lại kết quả âm cũng quan trọng như kết quả dương — nó cho biết **không nên đầu tư vào đâu**.

**(a) Dự đoán khách mua lại trong 90 ngày sau lần mua đầu** (để Marketing chọn khách nên chăm sóc):""",
"""s = X[X["is_failed"] == 0].copy()
s["k"] = s.groupby("customer_id").cumcount()
first_buy = s[s["k"] == 0].merge(
    s[s["k"] == 1][["customer_id", "time"]].rename(columns={"time": "t2"}), on="customer_id", how="left")
first_buy["repeat_90d"] = ((first_buy["t2"] - first_buy["time"]).dt.days <= 90).astype(int)
first_buy = first_buy[first_buy["time"] < "2022-10-01"]  # cần đủ 90 ngày quan sát
first_buy["had_failed_before"] = (first_buy["n_prev_failed"] > 0).astype(int)
F_REPEAT = fm.CATEGORICAL + ["hour", "dow", "original_price", "discount_rate", "birth_year", "had_failed_before"]
tr, te = first_buy[first_buy["time"] < "2022-01-01"], first_buy[first_buy["time"] >= "2022-01-01"]
import lightgbm as lgb
m_repeat = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, random_state=42, verbose=-1).fit(tr[F_REPEAT], tr["repeat_90d"])
print(f"Tỷ lệ mua lại 90 ngày: {te['repeat_90d'].mean():.1%} | AUC = {roc_auc_score(te['repeat_90d'], m_repeat.predict_proba(te[F_REPEAT])[:, 1]):.3f}")""",
"""MD:AUC ≈ 0.5 = **không tốt hơn đoán ngẫu nhiên**. Thông tin lúc mua vé đầu (kênh, khuyến mãi, giờ, giá…) không cho biết khách có quay lại không → khớp với phát hiện ở notebook 01: khuyến mãi không làm khách quay lại nhiều hơn. Muốn dự đoán được cần dữ liệu hành vi khác (xem phim gì, đánh giá, tương tác app…).

**(b) Dự đoán giao dịch lỗi nào sẽ được khách tự mua lại trong 7 ngày** (để CSKH ưu tiên):""",
"""failed = X[X["is_failed"] == 1].sort_values("time")
succ = X.loc[X["is_failed"] == 0, ["customer_id", "time"]].rename(columns={"time": "next_ok"}).sort_values("next_ok")
failed = pd.merge_asof(failed, succ, left_on="time", right_on="next_ok", by="customer_id", direction="forward")
failed["recovered_7d"] = ((failed["next_ok"] - failed["time"]) <= pd.Timedelta(days=7)).astype(int)
failed = failed[failed["time"] < "2022-12-24"]
failed["status_id"] = failed["status_id"].astype("category")
F_REC = fm.FEATURES + ["status_id"]
tr, te = failed[failed["time"] < "2022-01-01"], failed[failed["time"] >= "2022-01-01"]
m_rec = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=15, min_child_samples=50,
                           random_state=42, verbose=-1).fit(tr[F_REC], tr["recovered_7d"])
print(f"Tỷ lệ tự mua lại: {te['recovered_7d'].mean():.1%} | AUC = {roc_auc_score(te['recovered_7d'], m_rec.predict_proba(te[F_REC])[:, 1]):.3f}")""",
"""MD:Cũng ≈ ngẫu nhiên, và chỉ ~7% giao dịch lỗi được tự mua lại. **Kết luận:** không cần model để chọn ai cần cứu — **liên hệ lại toàn bộ khách bị lỗi** (rẻ, đơn giản, tự động hóa được) là phương án hợp lý hơn. Đây là lý do pipeline ở notebook 04 tạo danh sách cứu đơn cho *tất cả* giao dịch lỗi chưa được mua lại.

## 5. Lưu model & đề xuất triển khai""",
"""fm.save(lgbm)
print("Đã lưu:", fm.MODEL_PATH.relative_to(fm.MODEL_PATH.parents[1]))""",
"""MD:**Cách dùng đề xuất:** tại màn hình checkout, nếu điểm rủi ro thuộc top 20% → hiển thị gợi ý *"Thanh toán bằng Ví trong app để giảm rủi ro lỗi"*.

⚠️ **Model chỉ cho thấy tương quan.** Chưa chắc khách đổi sang ví thì sẽ hết lỗi (có thể khách dùng ví vốn đã khác khách dùng thẻ). Trước khi triển khai rộng cần **A/B test**:
- Nhóm A: checkout như cũ · Nhóm B: hiện gợi ý cho giao dịch rủi ro cao
- Chỉ số chính: tỷ lệ thanh toán thành công · Chỉ số phụ: tỷ lệ bỏ giỏ, tỷ lệ chọn ví
- Thời gian: tối thiểu 2–4 tuần để đủ mẫu và qua nhiều ngày trong tuần.""",
]

# ---------------------------------------------------------------- 04
NB4 = [
"""MD:# 04 · Giám sát tự động, bản tin AI cho từng phòng ban & hỏi dữ liệu bằng tiếng Việt

Notebook này chứng minh 3 thành phần tự động hóa (code nằm trong `src/`, chạy hằng tuần bằng `python -m src.pipeline`):

1. **Cảnh báo sớm** tỷ lệ lỗi thanh toán tăng bất thường theo tuần — kiểm chứng lại (backtest) trên đợt lỗi ngân hàng 2022.
2. **Bản tin tuần cho 5 phòng ban** (Marketing, CSKH, Product/IT, Tài chính, Ban lãnh đạo — chi tiết từng phòng ở notebook 05) do LLM viết từ số liệu Python tính sẵn, có **bộ kiểm tra chống bịa số**; không có API key → tự dùng template.
3. **Hỏi dữ liệu bằng tiếng Việt** (Text-to-SQL, dùng **Gemini**) có bộ 12 câu hỏi đáp án chuẩn để đo độ chính xác.""",
SETUP,
"""import os
os.environ.setdefault("LLM_MODE", "off")  # đổi thành "on" (và cài `anthropic`, cấu hình API key) để dùng LLM thật

from src.data_prep import load_tickets
from src import anomaly, ask_data, briefs, metrics, pipeline

df = load_tickets()
weekly = metrics.weekly_error_rates(df)
alerts = anomaly.detect(weekly)""",
"""MD:## 1. Cảnh báo sớm theo tuần
Mỗi tuần, so tỷ lệ lỗi của từng nhóm với **median 8 tuần trước** (robust z-score dùng MAD — ít bị ảnh hưởng bởi tuần cực đoan). Cảnh báo khi z ≥ 3 và tuần có ≥ 100 lượt thanh toán. Chỉ dùng dữ liệu quá khứ nên có thể chạy lại cho bất kỳ tuần nào trong lịch sử (backtest).""",
"""ext = alerts[(alerts["error_group"] == "external") & (alerts["week"] >= "2021-12-01")]
fig, ax = plt.subplots(figsize=(15, 4.5))
ax.plot(ext["week"], ext["rate"], color=BLUE, marker="o", ms=3, label="Tỷ lệ lỗi external (tuần)")
ax.plot(ext["week"], ext["baseline"], color=GREY, ls="--", label="Mức nền (median 8 tuần trước)")
hits = ext[ext["is_alert"]]
ax.scatter(hits["week"], hits["rate"], color=RED, s=80, zorder=3, label="Cảnh báo (z ≥ 3)")
ax.yaxis.set_major_formatter(mtick.PercentFormatter(1))
ax.set_title("Lỗi phía ngân hàng (external) theo tuần — 12/2021 → 12/2022")
ax.legend()
plt.tight_layout()
alerts[alerts["is_alert"] & (alerts["week"].dt.year == 2022)][["week", "error_group", "n_tickets", "rate", "baseline", "z", "excess_errors"]].round(3)""",
"""monthly = df[df["year"] == 2022].groupby("year_month").agg(
    tickets=("ticket_id", "count"), external_rate=("error_group", lambda s: (s == "external").mean()))
monthly.round(3).T""",
"""MD:**Backtest trên đợt lỗi ngân hàng 2022:**
- Tín hiệu đầu tiên: tuần **31/01/2022** lỗi external 10.7% so với mức nền 7.3% (z = 4.7).
- Tuần **28/02 → 06/03/2022**: tỷ lệ lỗi external **17.8%**, gấp đôi mức nền **8.7%** (z = 5.0) → hệ thống cảnh báo ngay **thứ Hai 07/03/2022**.
- Nếu chỉ xem báo cáo tháng: tháng 3/2022 (16.2%) chỉ được thấy khi chốt số **đầu tháng 4** → cảnh báo tuần đi trước khoảng **3–4 tuần**.
- Tỷ lệ lỗi external còn ở mức cao (12–14%) suốt tháng 4–6/2022 — đủ lâu để một cảnh báo sớm tạo ra khác biệt.
- **Không hoàn hảo:** năm 2022 có 6 cảnh báo, 3 cái thuộc đợt lỗi ngân hàng; 3 cái còn lại ở nhóm `internal`/`customer` (trong đó tuần 03/01 chỉ có 195 vé và tỷ lệ 1.5% → gần như chắc chắn là nhiễu). Cách cải thiện: nâng ngưỡng số vé tối thiểu cho nhóm lỗi hiếm, hoặc yêu cầu 2 tuần liên tiếp mới báo đỏ.

## 2. Pipeline hằng tuần: bản tin + danh sách cứu đơn
Chạy lại pipeline cho đúng tuần xảy ra sự cố:""",
"""out_dir, summary = pipeline.run("2022-02-28")
print("Thư mục kết quả:", out_dir.relative_to(out_dir.parents[2]))
print("Nguồn bản tin:", summary["brief_sources"])
print(f"Danh sách cứu đơn: {summary['recovery_list_size']} khách")""",
"""from IPython.display import Markdown
Markdown((out_dir / "brief_product_it.md").read_text(encoding="utf-8"))""",
"""pd.read_csv(out_dir / "recovery_list.csv").head()""",
"""MD:## 3. Chống "AI bịa số"
LLM chỉ được nhận **FACTS** (mọi con số đã được Python tính và format sẵn). Sau khi LLM viết xong, `validate_numbers` rút mọi con số trong bản tin ra và đối chiếu với FACTS — có số lạ thì **bỏ bản LLM, dùng template**. Thử với một bản tin cố tình chèn số bịa:""",
"""facts = briefs.weekly_facts(df, alerts, "2022-02-28")
honest = briefs.template_brief(facts, "finance")
fake = dict(honest, summary=honest["summary"] + " Ước tính mất 25,000 doanh thu, tỷ lệ lỗi tăng 9.1%.")
print("Bản tin đúng  ->", briefs.validate_numbers(honest, facts) or "hợp lệ")
print("Bản tin có số bịa ->", briefs.validate_numbers(fake, facts))""",
"""MD:## 4. Hỏi dữ liệu bằng tiếng Việt (Text-to-SQL)
LLM nhận mô tả schema và sinh **một câu SELECT**; câu lệnh được kiểm tra (chỉ SELECT, một câu, không từ khóa sửa dữ liệu) và chạy trên SQLite **chỉ-đọc**.

Để đo độ chính xác, `eval/ask_data_eval.json` có 12 câu hỏi kèm **SQL đáp án chuẩn**. Đáp án chuẩn:""",
"""conn = ask_data.build_connection(df)
gold = [(q["id"], q["question"], ask_data.run_sql(conn, q["gold_sql"]).iloc[0].tolist()) for q in ask_data.load_eval()]
pd.DataFrame(gold, columns=["id", "câu hỏi", "đáp án chuẩn (dòng đầu)"]).set_index("id")""",
"""try:
    ask_data.run_sql(conn, "DELETE FROM tickets")
except ValueError as exc:
    print("Chặn câu lệnh nguy hiểm:", exc)""",
"""MD:Chạy đánh giá với Gemini thật (mỗi câu ít nhất 1 lần gọi API — tốn hạn mức gói miễn phí, nên mặc định tắt).

Lần chạy ngày 2026-10-09 (chạy bằng script ngoài notebook, cùng hàm `ask_data.run_eval`): **12/12 câu đúng**, khoảng 146 giây.
Các câu do nhiều model khác nhau trả lời (`gemini-3.7-flash`, `gemini-3-flash-preview`, `gemini-3.6-flash`) vì model chính
`gemini-3.5-flash` đã hết hạn mức trong ngày → chuỗi model dự phòng tự chuyển.""",
"""RUN_LLM_EVAL = False  # đổi thành True khi đã có GEMINI_API_KEY trong .env

if RUN_LLM_EVAL:
    result = ask_data.run_eval(conn)
    print(f"Độ chính xác: {result['correct'].sum()}/{result['correct'].notna().sum()}")
    display(result[["id", "question", "sql", "correct"]])
else:
    print("Bỏ qua đánh giá LLM (RUN_LLM_EVAL = False)")""",
"""MD:## 5. Tự động hóa
- `python -m src.pipeline` — chạy tuần gần nhất; `--week YYYY-MM-DD` để chạy lại một tuần bất kỳ; `--notify` gửi tóm tắt qua Telegram.
- `.github/workflows/weekly_pipeline.yml` — GitHub Actions chạy pipeline mỗi sáng thứ Hai, lưu báo cáo thành artifact. API key và Telegram token để trong **GitHub Secrets**, không nằm trong code.
- `app/streamlit_app.py` — giao diện cho quản lý: tổng quan, cảnh báo, bản tin theo tuần, hỏi dữ liệu.""",
]

# ---------------------------------------------------------------- 05
NB5 = [
"""MD:# 05 · Mỗi phòng ban nhận được gì

Notebook này kiểm chứng từng dòng của bảng "trước / sau khi có hệ thống" bằng số liệu thật, và nói rõ **mức độ tin cậy** của từng phần.

| Phòng ban | Trước đây | Sau khi có hệ thống | Code |
|---|---|---|---|
| **Ban lãnh đạo** | Đọc nhiều báo cáo rời rạc | Bản tin tóm tắt hằng tuần + dashboard **6 nhóm KPI** (đúng slide "Kế hoạch đo lường KPI") | `src/kpis.py` |
| **Marketing** | Phát voucher đại trà | Phân nhóm khách theo slide "Phân nhóm khách hàng & chiến lược giữ chân" + **điểm khả năng quay lại** + biết **campaign nào chỉ hút khách một lần** | `src/marketing.py` |
| **CSKH** | Gặp lỗi mới đi hỏi IT | Cảnh báo sớm + danh sách cứu đơn + **mẫu trả lời theo mã lỗi** | `src/pipeline.py`, `src/briefs.py` |
| **Product / IT** | Chờ khách phàn nàn mới biết | Cảnh báo tuần: **mã lỗi nào, nền tảng nào, phương thức nào, tăng bao nhiêu** | `src/anomaly.py`, `src/product.py` |
| **Tài chính** | Không biết lỗi thanh toán làm mất bao nhiêu | Giá trị **đơn lỗi không được mua lại** + **tiền giảm giá cho khách chỉ mua một lần** | `src/finance.py` |

Ví dụ xuyên suốt: tuần **28/02/2022** (tuần có đợt lỗi ngân hàng).""",
SETUP,
"""import os
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")
os.environ.setdefault("LLM_MODE", "off")
from IPython.display import Markdown
from src.data_prep import load_tickets
from src import anomaly, briefs, departments, finance, kpis, marketing, metrics, pipeline

df = load_tickets()
WEEK = "2022-02-28"
extra, tables = departments.build(df, WEEK)""",
"""MD:## 1. Ban lãnh đạo — dashboard 6 nhóm KPI
Định nghĩa theo slide (dữ liệu không có lượt truy cập, nên "chuyển đổi" tính ở mức khách: khách có thanh toán trong tháng → bao nhiêu % mua thành công):""",
"""pd.DataFrame(kpis.KPI_DEFINITIONS, columns=["nhóm KPI", "mã", "chỉ số", "định dạng", "chiều tốt (+1 tăng / -1 giảm)"])""",
"""kpi_all = kpis.monthly_kpis(df)
kpi_2022 = kpi_all.loc["2022-01":"2022-12"]
show = {key: label for _, key, label, _, _ in kpis.KPI_DEFINITIONS}
kpi_2022[list(show)].rename(columns=show).T.round(3)""",
"""picks = [("success_tickets", "1. Vé thành công"), ("repeat_90d", "2. Mua lần 2 trong 90 ngày"),
         ("repeat_no_promo_share", "3. Mua lại không dùng KM"), ("payment_success_rate", "4. Thanh toán thành công"),
         ("app_completion_rate", "5. Hoàn tất thanh toán trên app"), ("spend_per_customer", "6. Chi tiêu TB / khách")]
fig, axes = plt.subplots(2, 3, figsize=(16, 7))
for ax, (key, title) in zip(axes.flat, picks):
    ax.plot(kpi_2022.index, kpi_2022[key], marker="o", color=BLUE)
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=60, labelsize=7)
    if kpi_2022[key].max() <= 1:
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(1))
plt.suptitle("6 nhóm KPI năm 2022 (mỗi nhóm 1 chỉ số đại diện)", y=1.01)
plt.tight_layout()""",
"""alerts = anomaly.detect(metrics.weekly_error_rates(df))
facts = {**briefs.weekly_facts(df, alerts, WEEK), **extra}
brief, source = briefs.generate_brief(facts, "leadership")
Markdown(briefs.to_markdown(brief, "leadership", facts, source))""",
"""MD:## 2. Marketing
### 2a. Phân nhóm khách — luật lấy đúng từ slide của báo cáo
Thứ tự ưu tiên: giá trị cao (≥ 3 lần mua và còn hoạt động trong 180 ngày) → mua một lần & mới (≤ 30 ngày) → lâu chưa quay lại (> 90 ngày) → nhạy khuyến mãi (≥ 50% giao dịch có KM) → thường xuyên.""",
"""targets = tables["marketing_targets"]
seg = targets.groupby("segment").agg(customers=("score", "size"), avg_score=("score", "mean"),
                                     avg_frequency=("frequency", "mean"), avg_recency_days=("recency_days", "mean"))
seg["action"] = seg.index.map(marketing.SEGMENT_ACTIONS)
seg.sort_values("customers", ascending=False).round(3)""",
"""MD:### 2b. Điểm khả năng quay lại trong 90 ngày — có đáng tin không?
Backtest: train trên 3 mốc (01/03, 01/04, 01/05/2022 — nhãn = có mua trong 90 ngày sau mốc), test trên mốc **01/08/2022** (chưa từng thấy).
So với luật đơn giản "mua gần đây nhất = điểm cao nhất".""",
"""train = marketing.training_set(df, ["2022-03-01", "2022-04-01", "2022-05-01"])
test = marketing.training_set(df, ["2022-08-01"])
propensity = marketing.train_propensity(train)
evaluation = marketing.evaluate_propensity(propensity, test)
pd.Series(evaluation).round(3).to_frame("giá trị")""",
"""test_scored = test.assign(score=propensity.predict_proba(test[marketing.FEATURES])[:, 1])
test_scored["decile"] = pd.qcut(test_scored["score"].rank(method="first"), 10, labels=range(1, 11))
lift = test_scored.groupby("decile", observed=True)["y"].mean()
fig, ax = plt.subplots(figsize=(9, 3.5))
ax.bar(lift.index.astype(str), lift, color=BLUE)
ax.axhline(test["y"].mean(), color=RED, ls="--", label="trung bình")
ax.yaxis.set_major_formatter(mtick.PercentFormatter(1))
ax.set(title="Tỷ lệ thực sự mua lại trong 90 ngày theo nhóm điểm (10 = điểm cao nhất)", xlabel="decile")
ax.legend()
plt.tight_layout()""",
"""MD:**Đọc trung thực:** model tốt hơn luật recency nhưng **tín hiệu vừa phải** (AUC ~0.66). Giá trị thực tế: nhóm điểm cao nhất mua lại nhiều hơn hẳn trung bình, nên Marketing **ưu tiên ngân sách** cho nhóm này thay vì phát voucher đại trà. Không nên hứa "biết chắc ai sẽ quay lại".

Khác với model ở notebook 03 (AUC 0.53 — chỉ dùng thông tin lần mua đầu): ở đây dùng **lịch sử mua** (recency, frequency, monetary…), và chính recency/frequency mang tín hiệu.

### 2c. Campaign nào chỉ hút khách một lần?
Khách mới đến từ mỗi loại campaign (lần mua đầu), tỷ lệ mua lần 2 trong 90 ngày, và **tiền giảm giá cho mỗi khách thực sự quay lại**:""",
"""tables["campaign_effectiveness"].round(3)""",
"""tables_full = departments.build(df, "2022-12-19")[1]
print("Dữ liệu tới hết 2022:")
display(tables_full["campaign_effectiveness"].round(3))
tables_full["campaign_ids"].head(8).round(3)""",
"""MD:- **reward point** gần như chỉ hút khách một lần, và tốn nhiều giảm giá nhất cho mỗi khách quay lại; **voucher** giữ chân tốt nhất trong các loại khuyến mãi.
- Khách **không dùng khuyến mãi** (`none`) quay lại ngang hoặc hơn khách đến từ direct discount → khớp kết luận ở notebook 01: khuyến mãi kéo khách mới nhưng không tạo thói quen.
- Ở mức từng campaign, có những campaign gần như **không giữ được ai** → ứng viên đầu tiên để cắt ngân sách.

⚠️ So sánh này là quan sát, chưa phải nhân quả (mỗi loại campaign có thể nhắm tệp khách khác nhau).

## 3. CSKH — cảnh báo sớm + mẫu trả lời theo mã lỗi""",
"""recovery = pipeline.recovery_list(df, pd.Timestamp(WEEK))
print(f"Tuần {WEEK}: {len(recovery)} khách cần liên hệ lại")
display(pd.Series(extra["customer_care"]["errors_by_code"], name="số lỗi trong tuần"))
pd.Series(briefs.RECOVERY_MESSAGES, name="mẫu tin nhắn").rename_axis("status_id").to_frame()""",
"""MD:## 4. Product / IT — mã lỗi nào, nền tảng nào, tăng bao nhiêu
Cảnh báo theo nhóm lỗi (notebook 04) cho biết **có sự cố**; bảng dưới khoanh vùng **ở đâu**: tỷ lệ lỗi của từng tổ hợp mã lỗi × nền tảng × phương thức tuần này so với 8 tuần trước.""",
"""tables["product_breakdown"].head(10).round(3)""",
"""MD:Tuần 28/02/2022 khoanh được đúng điểm nghẽn: **"Payment failed from bank" trên mobile qua bank account** tăng từ 4.6% lên 21.1% — đây là thông tin đội IT cần để làm việc với đúng ngân hàng / cổng thanh toán, thay vì "lỗi tăng chung chung".

## 5. Tài chính — mất bao nhiêu
- **Đơn lỗi không được mua lại**: giá trị các giao dịch lỗi mà khách không mua thành công trong 7 ngày sau đó.
- **Giảm giá cho khách chỉ mua một lần**: tiền giảm giá của giao dịch khuyến mãi mà khách không mua thêm trong 90 ngày.
Tháng chưa đủ cửa sổ quan sát để trống (không báo số thiếu).""",
"""losses = finance.monthly_losses(df).loc["2022-01":"2022-12"]
fig, ax = plt.subplots(figsize=(14, 4))
x = np.arange(len(losses))
ax.bar(x - 0.2, losses["unrecovered_failed_value"], 0.4, color=RED, label="Đơn lỗi không được mua lại (7 ngày)")
ax.bar(x + 0.2, losses["discount_one_time"], 0.4, color=BLUE, label="Giảm giá cho khách không quay lại (90 ngày)")
ax.set_xticks(x, losses.index, rotation=45)
ax.set_title("Thất thoát theo tháng năm 2022 (đơn vị tiền theo dataset)")
ax.legend()
plt.tight_layout()
complete = losses.dropna()
print(f"Các tháng đủ dữ liệu ({complete.index[0]} → {complete.index[-1]}):")
print(f"  Đơn lỗi không được mua lại: {complete['unrecovered_failed_value'].sum():,.0f} "
      f"/ tổng đơn lỗi {complete['failed_value'].sum():,.0f} ({complete['unrecovered_failed_value'].sum() / complete['failed_value'].sum():.1%})")
print(f"  Giảm giá cho khách không quay lại: {complete['discount_one_time'].sum():,.0f} "
      f"/ tổng giảm giá {complete['discount_total'].sum():,.0f} ({complete['discount_one_time'].sum() / complete['discount_total'].sum():.1%})")""",
"""MD:## 6. Tất cả chạy tự động mỗi tuần
`python -m src.pipeline` tạo cho mỗi tuần một thư mục `reports/weekly/<tuần>/`:""",
"""out_dir, summary = pipeline.run(WEEK)
pd.DataFrame(
    [(p.name, {"brief_leadership.md": "Ban lãnh đạo", "kpis_monthly.csv": "Ban lãnh đạo",
               "brief_marketing.md": "Marketing", "marketing_targets.csv": "Marketing",
               "campaign_effectiveness.csv": "Marketing", "campaign_ids_effectiveness.csv": "Marketing",
               "brief_customer_care.md": "CSKH", "recovery_list.csv": "CSKH",
               "brief_product_it.md": "Product / IT", "product_breakdown.csv": "Product / IT",
               "brief_finance.md": "Tài chính", "finance_monthly_losses.csv": "Tài chính"}.get(p.name, "Chung"))
     for p in sorted(out_dir.iterdir())],
    columns=["file", "phòng ban"],
)""",
"""MD:## Tóm tắt — mức độ tin cậy của từng phần

| Phòng ban | Đã làm | Mức độ tin cậy |
|---|---|---|
| Ban lãnh đạo | 14 chỉ số / 6 nhóm KPI theo tháng + bản tin tuần | Cao — tính thẳng từ dữ liệu; chỉ số cần cửa sổ tương lai để `n/a` khi chưa đủ dữ liệu |
| Marketing | Phân nhóm theo slide + điểm quay lại + hiệu quả campaign | Phân nhóm & campaign: cao (mô tả). Điểm quay lại: **vừa phải** (AUC ~0.66) — dùng để ưu tiên |
| CSKH | Danh sách cứu đơn + mẫu tin nhắn theo 7 mã lỗi + cảnh báo | Cao — quy tắc rõ ràng; hiệu quả cứu đơn thực tế cần đo sau triển khai |
| Product / IT | Cảnh báo tuần + khoanh vùng mã lỗi × nền tảng × phương thức | Cao — backtest bắt đúng đợt lỗi 2022; có cảnh báo nhiễu ở nhóm lỗi hiếm |
| Tài chính | Thất thoát do đơn lỗi + giảm giá cho khách một lần | Cao cho phần đo được; là **cận dưới** vì chưa có chi phí quảng cáo / giá trị vòng đời |""",
]

# ---------------------------------------------------------------- 06
NB6 = [
"""MD:# 06 · Tự động hóa vận hành: nạp dữ liệu hằng ngày, báo cáo Excel, dataset cho analyst

| Yêu cầu công việc | Phần trong project |
|---|---|
| *Automate repetitive reporting using Python, SQL, Excel or AI tools* | Pipeline tuần tự sinh **file Excel 7 sheet** (tóm tắt + 5 phòng ban + chất lượng dữ liệu) — `src/excel_report.py` |
| *Support data extraction and operational reporting for production teams* | **Nạp file dữ liệu mỗi ngày** + **12 kiểm tra chất lượng**, lỗi thì dừng & cách ly; log vận hành theo ngày — `src/ingest.py`, `src/quality.py` |
| *Prepare datasets for analysts and product teams* | **4 bảng dữ liệu sạch** + **từ điển dữ liệu tự sinh** — `src/marts.py` |

Notebook chạy trên thư mục demo riêng (`data/_demo/`) để không ảnh hưởng kho chính.""",
SETUP,
"""import os
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")
os.environ.setdefault("LLM_MODE", "off")
from src import ingest, marts, pipeline, quality
from src.config import DATA_DIR

demo = ingest.Paths(root=DATA_DIR / "_demo", reports=DATA_DIR / "_demo" / "reports")
ingest.reset(demo)""",
"""MD:## 1. Nạp dữ liệu hằng ngày có kiểm tra chất lượng
### 1a. Mô phỏng hệ thống đổ file mỗi ngày
Chia `ticket_history.csv` thành 1 file / ngày (giữ nguyên dữ liệu gốc, kể cả dòng trùng) — giả lập "hôm nay là 07/03/2022" nên chỉ để lại file tới 06/03/2022.""",
"""n_files = ingest.simulate_drops(demo)
for f in demo.incoming.glob("*.csv"):
    if ingest.file_date(f) > "2022-03-06":
        f.unlink()
print(f"Đã tạo {n_files} file; còn {len(list(demo.incoming.glob('*.csv')))} file tới 06/03/2022")""",
"""MD:### 1b. 12 kiểm tra trước khi nạp
`error` = dừng, không nạp, không chạy báo cáo · `warning` = vẫn nạp, ghi lại để theo dõi.""",
"""checks = pd.DataFrame([
    ("schema", "error", "Đủ 12 cột bắt buộc"),
    ("not_empty", "error", "File có dữ liệu"),
    ("parse_types", "error", "time / giá / id đọc được đúng kiểu"),
    ("key_nulls", "error", "Không thiếu ticket_id, customer_id, time, status_id, paying_method"),
    ("exact_duplicates", "warning", "Dòng trùng hoàn toàn → tự loại bỏ"),
    ("ticket_id_conflict", "error", "Cùng ticket_id nhưng nội dung khác nhau"),
    ("already_loaded", "error", "ticket_id đã có trong kho (chống nạp 2 lần)"),
    ("unknown_status / customer / campaign", "error", "Mã không có trong bảng tham chiếu"),
    ("unknown_device / paying_method", "warning", "Giá trị lạ nhưng không làm sai chỉ số chính"),
    ("price_rules", "error", "Giá không âm, giảm giá ≤ giá gốc, final = gốc − giảm"),
    ("date_matches_file", "error", "Mọi dòng đúng ngày của file"),
    ("volume", "warning", f"Số dòng trong khoảng {quality.VOLUME_LOW}–{quality.VOLUME_HIGH} lần trung vị 28 ngày"),
], columns=["check", "mức độ", "ý nghĩa"])
checks""",
"""MD:File cập nhật bảng tham chiếu (khách hàng, campaign, thiết bị, mã lỗi — mục 1e) có bộ kiểm tra riêng: đủ cột, khóa không trống, đọc được kiểu dữ liệu, không trùng khóa mâu thuẫn, giá trị phân loại hợp lệ, và ghi lại bản ghi cũ bị đổi thông tin.

Các ngưỡng được đặt **sau khi kiểm tra dữ liệu thật**: dữ liệu 2019–2022 đạt 0 vi phạm ở mọi check `error`. Riêng `volume`: số dòng/ngày dao động 1 → 1,268 theo lịch chiếu phim; ngưỡng 0.2–5 lần cảnh báo tới ~11% số ngày (quá nhiễu), nên chọn 0.1–10 lần (~5%, chủ yếu các đợt rạp mở lại sau COVID).

### 1c. Chạy nạp — chỉ đọc file MỚI""",
"""result = ingest.run(demo)
print({k: v for k, v in result.items() if k != "warnings"})
print("Chạy lại lần 2 (không có file mới):", ingest.run(demo)["loaded"], "file")""",
"""log = pd.read_csv(demo.dq_dir / "dq_log.csv")
warning_counts = log["warnings"].dropna().str.split(";").explode().value_counts()
print(f"{len(log)} file đã kiểm tra · {(log['status'] == 'failed').sum()} file bị chặn · {log['warnings'].notna().sum()} file có cảnh báo")
warning_counts.rename("số file có cảnh báo").to_frame()""",
"""MD:Log vận hành theo ngày (đội vận hành mở mỗi sáng):""",
"""pd.read_csv(demo.daily_ops).tail(7)""",
"""MD:### 1d. File lỗi → pipeline DỪNG, không ra báo cáo sai
Tạo file ngày 07/03/2022 có 4 loại lỗi thường gặp: mã trạng thái lạ, thiếu customer_id, giá sai công thức, trùng ticket_id.""",
"""bad = ingest.inject_bad_file(demo)
try:
    pipeline.run(ingest_first=True, paths=demo)
except pipeline.DataQualityError as exc:
    print("⛔", exc)""",
"""import json
report = json.loads((demo.dq_dir / f"{bad.stem}.json").read_text(encoding="utf-8"))
pd.DataFrame(report["checks"]).query("status == 'fail'")[["check", "severity", "failed_rows", "detail"]]""",
"""print("Thư mục cách ly:", [f.name for f in demo.quarantine.iterdir()])
print("Trạng thái kho:", json.dumps({k: v for k, v in ingest.read_state(demo).items() if k == "failed"}, ensure_ascii=False))""",
"""MD:File lỗi bị chuyển sang `quarantine/`, kho vẫn giữ nguyên dữ liệu sạch tới 06/03. Khi nguồn gửi lại file đã sửa vào `incoming/`, lần chạy sau sẽ tự nạp tiếp. (File nạp thành công được chuyển sang `archive/`, nên `incoming/` chỉ còn file đang chờ.)

### 1e. Dữ liệu mới ngoài đời: khách mới, campaign mới, mã lỗi mới, file xuất nhiều ngày
Ngày nào cũng có khách mới đăng ký, campaign mới… nên ngoài file giao dịch, nguồn gửi kèm **file cập nhật bảng tham chiếu** cùng quy ước tên: `customer_YYYY-MM-DD.csv`, `campaign_…`, `device_detail_…`, `status_detail_…`. Trong cùng 1 ngày, bảng tham chiếu được kiểm tra & cập nhật **trước**, rồi mới kiểm tra giao dịch → khách đăng ký và mua vé cùng ngày vẫn qua.

Bỏ file lỗi ở trên (coi như nguồn đã gửi bản đúng), rồi thử lần lượt:""",
"""(demo.quarantine / bad.name).unlink()
state = ingest.read_state(demo)
state["failed"].clear()
ingest.write_state(demo, state)

template = pd.read_parquet(demo.warehouse / "2022-03-05.parquet")


def new_day(date, n=200, new_customers=(), campaign=None, status=None, tag=""):
    d = template.head(n).copy()
    d["ticket_id"] = [f"n{date.replace('-', '')}{tag}{i:05d}" for i in range(len(d))]
    d["time"] = date + pd.to_datetime(d["time"]).dt.strftime(" %H:%M:%S.%f").str[:-3]
    for i, cid in enumerate(new_customers):
        d.loc[d.index[i], "customer_id"] = cid
    if campaign:
        d.loc[d.index[:3], "campaign_id"] = campaign
    if status:
        d.loc[d.index[:2], "status_id"] = status
    return d


steps = []
def step(label):
    r = ingest.run(demo)
    days = r["split_exports"][0]["days"] if r["split_exports"] else ""
    steps.append((label, r["loaded"], r["reference_updates"] or "", days, r["failed"] or "", ", ".join(r["failed_checks"])))

new_ids = [900001, 900002, 900003]
new_day("2022-03-07", new_customers=new_ids).to_csv(demo.incoming / "ticket_history_2022-03-07.csv", index=False)
step("07/03: có 3 khách mới, nguồn QUÊN gửi file customer")

pd.DataFrame({"customer_id": new_ids, "usergender": ["Female", "Male", "Female"],
              "dob": ["2001-04-12", "1998-11-30", "2003-01-05"]}).to_csv(demo.incoming / "customer_2022-03-07.csv", index=False)
(demo.quarantine / "ticket_history_2022-03-07.csv").rename(demo.incoming / "ticket_history_2022-03-07.csv")
step("07/03: gửi bổ sung customer_2022-03-07.csv")

new_day("2022-03-08", campaign=555555, status=-8).to_csv(demo.incoming / "ticket_history_2022-03-08.csv", index=False)
pd.DataFrame({"campaign_id": [555555], "campaign_type": ["voucher"]}).to_csv(demo.incoming / "campaign_2022-03-08.csv", index=False)
pd.DataFrame({"status_id": [-8], "description": ["3-D Secure timeout"], "error_group": ["bank"]}).to_csv(
    demo.incoming / "status_detail_2022-03-08.csv", index=False)
step("08/03: campaign mới + mã lỗi mới -8 khai nhóm lỗi 'bank' (sai)")

pd.DataFrame({"status_id": [-8], "description": ["3-D Secure timeout"], "error_group": ["external"]}).to_csv(
    demo.incoming / "status_detail_2022-03-08__fixed.csv", index=False)
step("08/03: gửi lại status_detail đã sửa nhóm lỗi = external")

pd.concat([new_day(d, n=60, tag="x") for d in ["2022-03-09", "2022-03-10"]]).to_csv(
    demo.incoming / "ticket_history_export_09-10.csv", index=False)
step("09-10/03: nhận 1 file xuất 2 ngày")

pd.DataFrame(steps, columns=["tình huống", "file giao dịch nạp", "cập nhật tham chiếu", "tách thành (ngày)",
                             "file bị chặn", "lý do"])""",
"""from src.data_prep import load_tickets

fresh = load_tickets(source="warehouse", warehouse_dir=demo.warehouse)
print("Dữ liệu tới:", fresh["time"].max().date(), "| tuổi tính tại ngày này")
display(fresh[fresh["customer_id"].isin(new_ids)][["customer_id", "usergender", "dob", "age", "age_generation"]].drop_duplicates())
fresh.loc[fresh["status_id"] == -8, ["status_id", "description", "error_group"]].drop_duplicates()""",
"""MD:- Thiếu file khách hàng → **chặn** (không đoán thông tin khách); có file → qua, và khách mới **có đủ giới tính/tuổi** trong báo cáo.
- Mã lỗi mới phải khai **nhóm lỗi hợp lệ** (customer / external / internal), nếu không mọi báo cáo theo nhóm lỗi sẽ sai → chặn tới khi sửa. Bản sửa nạp xong thì lỗi cũ tự được đánh dấu đã xử lý.
- File xuất nhiều ngày được **tự tách** theo ngày rồi kiểm tra từng ngày như bình thường.
- Nguồn gửi lại 1 file đã nạp nhưng **khác nội dung** → chặn (`file_resent_with_different_content`), không tự ghi đè dữ liệu đã báo cáo.

## 2. Báo cáo Excel tự động
Pipeline đọc **kho dữ liệu đã nạp** và sinh file Excel cho tuần 28/02/2022:""",
"""out_dir, summary = pipeline.run("2022-02-28", source="warehouse", paths=demo)
excel_path = out_dir / summary["excel_report"]
print("File:", excel_path.relative_to(DATA_DIR.parent))
print("Cảnh báo tuần:", summary["alerts"])""",
"""from openpyxl import load_workbook
wb = load_workbook(excel_path)
pd.DataFrame([(ws.title, ws.max_row, len(ws._charts), len(ws.conditional_formatting),
               sum(1 for row in ws.iter_rows() for c in row if c.hyperlink)) for ws in wb.worksheets],
             columns=["sheet", "số dòng", "biểu đồ Excel", "quy tắc tô màu", "liên kết"])""",
"""pd.read_excel(excel_path, sheet_name="Tóm tắt", header=None).dropna(how="all").head(20)""",
"""MD:Thiết kế cho người nhận không chuyên dữ liệu:
- **Tóm tắt** ở sheet đầu, mỗi phòng ban 1 dòng tiêu điểm + **link** sang sheet của họ.
- Ô cảnh báo tô đỏ; KPI tốt/xấu hơn tháng trước tô xanh/đỏ theo **chiều tốt của từng chỉ số** (tỷ lệ lỗi giảm là tốt).
- Biểu đồ là **biểu đồ Excel gốc** (không phải ảnh) → người nhận tự lọc, sửa, copy sang slide.
- Danh sách CSKH có bộ lọc, tô đỏ các lỗi phía ngân hàng (khách không tự sửa được → ưu tiên gọi).
- Sheet **Chất lượng dữ liệu** cho biết báo cáo dựa trên dữ liệu đã qua kiểm tra. Nếu file mới nhất bị chặn, sheet Tóm tắt ghi *"Chất lượng dữ liệu: LỖI"* → người nhận biết dữ liệu mới nhất **chưa** vào báo cáo.

## 3. Dataset sạch cho analyst / product""",
"""tables, dictionary = marts.build()
pd.DataFrame([(name, f"{len(t):,}", t.shape[1], ", ".join(marts.TABLES[name]["key"]), marts.TABLES[name]["grain"])
              for name, t in tables.items()], columns=["bảng", "số dòng", "số cột", "khóa chính", "grain"])""",
"""dictionary[dictionary["table"] == "dim_customer"][["column", "dtype", "description", "null_rate", "n_unique", "examples"]]""",
"""MD:Ví dụ analyst dùng ngay, không phải làm sạch lại — *"khách bị mất ở lần thanh toán đầu thuộc thế hệ nào?"* và *"nhóm khách nào có điểm quay lại cao nhất?"*:""",
"""dim = tables["dim_customer"]
active = dim[dim["has_activity"] & dim["is_verified_profile"]]
lost_by_gen = active.groupby("age_generation")["lost_at_first_payment"].mean().sort_values(ascending=False)
print("Tỷ lệ khách bị mất ở lần thanh toán đầu, theo thế hệ (khách có hồ sơ xác minh):")
print(lost_by_gen.map("{:.1%}".format).to_string())
tables["customer_features"].groupby("segment")["repurchase_score"].describe()[["count", "mean", "50%", "max"]].round(3)""",
"""MD:File xuất ra `data/marts/`: mỗi bảng có `.parquet` (giữ đúng kiểu, cho Python/BI) và `.csv` (mở bằng Excel), kèm `data_dictionary.md` / `.csv`. Khóa chính được kiểm tra không trùng trước khi ghi.

**Chạy lại toàn bộ bằng lệnh:**
```bash
python -m src.ingest simulate          # (1 lần) tạo file theo ngày
python -m src.ingest run               # nạp file mới + kiểm tra chất lượng
python -m src.pipeline --ingest        # nạp rồi ra báo cáo tuần (Excel + bản tin + CSV); lỗi dữ liệu -> dừng
python -m src.marts                    # làm mới dataset cho analyst
```""",
]

for name, cells in [
    ("01_data_preparation_and_eda.ipynb", NB1),
    ("02_problem_discovery.ipynb", NB2),
    ("03_payment_failure_model.ipynb", NB3),
    ("04_monitoring_automation_llm.ipynb", NB4),
    ("05_department_deliverables.ipynb", NB5),
    ("06_automation_data_ops.ipynb", NB6),
]:
    nbf.write(nb(cells), OUT / name)
    print("wrote", name)
