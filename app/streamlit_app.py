"""Dashboard cho 5 phòng ban: Ban lãnh đạo, Marketing, CSKH, Product/IT, Tài chính + dữ liệu + hỏi dữ liệu.

Chạy:  streamlit run app/streamlit_app.py
"""

import io
import os
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ui  # noqa: E402
from ui import C  # noqa: E402
from src import (anomaly, ask_data, briefs, departments, excel_report, gemini, ingest, kpis,  # noqa: E402
                 marketing, metrics, rag)
from src.data_prep import load_tickets  # noqa: E402
from src.llm import LLMUnavailable  # noqa: E402
from src.marts import MARTS_DIR  # noqa: E402
from src.pipeline import latest_full_week, recovery_list  # noqa: E402

st.set_page_config(page_title="Booking Health Monitor", page_icon="🎬", layout="wide")
ui.inject_css()

# Tên lỗi tiếng Việt ngắn cho biểu đồ / thẻ (mô tả gốc tiếng Anh vẫn giữ trong bảng chi tiết)
ERROR_VI = {
    "Payment failed from bank": "Ngân hàng từ chối",
    "No response from your bank": "Ngân hàng không phản hồi",
    "Insufficient funds in customer account. Please add more funds and try the transaction again.": "Không đủ số dư",
    "Password locked due to multiple incorrect attempts. Choose Forgot Password to unlock.": "Khóa do sai mật khẩu",
    "Need verify your account to continue": "Cần xác minh tài khoản",
    "Payment overdue": "Quá hạn thanh toán",
    "Transaction temporarily limited": "Giao dịch bị giới hạn",
}
STATUS_VI = {-1: "Quá hạn thanh toán", -2: "Không đủ số dư", -3: "Ngân hàng không phản hồi", -4: "Khóa do sai mật khẩu",
             -5: "Ngân hàng từ chối", -6: "Cần xác minh tài khoản", -7: "Giao dịch bị giới hạn"}
GROUP_LABELS = {"external": "Ngân hàng (external)", "customer": "Phía khách (customer)", "internal": "Hệ thống (internal)"}
NUM = st.column_config.NumberColumn
TXT = st.column_config.TextColumn


@st.cache_data
def load():
    df = load_tickets()
    weekly = metrics.weekly_error_rates(df)
    return df, weekly, anomaly.detect(weekly)


@st.cache_data
def week_data(week):
    """Số liệu của tuần đã chọn - chỉ dùng dữ liệu tới hết tuần đó."""
    df, _, alerts = load()
    facts = briefs.weekly_facts(df, alerts, week)
    extra, tables = departments.build(df, week)
    facts.update(extra)
    return facts, tables, recovery_list(df, week)


@st.cache_resource
def sql_connection():
    return ask_data.build_connection(load()[0])


@st.cache_data
def dq_log():
    path = ingest.Paths().dq_dir / "dq_log.csv"
    return pd.read_csv(path) if path.exists() else None


def show_brief(facts, dept):
    with st.expander(f"Bản tin tuần cho {briefs.DEPARTMENTS[dept]}"):
        if st.button("Tạo bản tin", key=f"brief_{dept}"):
            brief, source = briefs.generate_brief(facts, dept)
            st.markdown(briefs.to_markdown(brief, dept, facts, source))


def download(table, name, label="Tải CSV", index=False):
    st.download_button(label, table.to_csv(index=index).encode("utf-8-sig"), file_name=name, key=name)


def short(text, n=34):
    return text if len(text) <= n else text[: n - 1] + "…"


def pct100(frame, cols):
    """Tỷ lệ 0-1 -> 0-100 để hiển thị "12.3%" (định dạng % có sẵn của bảng đổi dấu theo ngôn ngữ trình duyệt)."""
    out = frame.copy()
    out[cols] = out[cols] * 100
    return out


PCT = "%.1f%%"


def month_vi(month):
    return pd.Period(month).strftime("%m/%Y") if month and month != "n/a" else "n/a"


def error_vi(text):
    return ERROR_VI.get(text, short(text, 30))


def month_axis(series):
    """Đủ mọi tháng từ đầu tới cuối: tháng bị ẩn (COVID) để TRỐNG thay vì nối thẳng qua."""
    full = pd.period_range(pd.Period(series.index[0]), pd.Period(series.index[-1]), freq="M").strftime("%Y-%m")
    s = series.reindex(full)
    return [pd.Period(m).to_timestamp() for m in s.index], s.values


df, weekly, alerts = load()

# ------------------------------------------------------------------ Sidebar: chỉ những gì cần
with st.sidebar:
    st.markdown('<div class="side-title">🎬 Booking Health Monitor</div>'
                '<div class="side-sub">Báo cáo vận hành tuần cho 5 phòng ban</div>', unsafe_allow_html=True)
    weeks = sorted(weekly[weekly["n_tickets"] >= 100].index, reverse=True)
    default_week = latest_full_week(df)
    week = st.selectbox("Tuần báo cáo", weeks, index=weeks.index(default_week) if default_week in weeks else 0,
                        format_func=lambda w: f"{w:%d/%m/%Y} → {w + pd.Timedelta(days=6):%d/%m/%Y}")
    st.caption("Tuần có sự cố mẫu: 28/02/2022")
    with st.expander("Cài đặt"):
        use_llm = st.toggle("Dùng LLM viết bản tin", value=False, help="Cần API key. Tắt = bản tin mẫu, số liệu như nhau.")
    os.environ["LLM_MODE"] = "on" if use_llm else "off"

facts, tables, recovery = week_data(week)
ext = facts["error_groups"].get("external", {})
log = dq_log()

with st.sidebar:
    st.divider()
    if st.button("Tạo báo cáo Excel tuần này", width="stretch"):
        generated = {dept: briefs.generate_brief(facts, dept) for dept in briefs.DEPARTMENTS}
        buffer = io.BytesIO()
        excel_report.build(buffer, facts, generated, tables, recovery, alerts, log)
        st.download_button("⬇ Tải file .xlsx", buffer.getvalue(), width="stretch",
                           file_name=f"weekly_report_{facts['week_start']}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ------------------------------------------------------------------ Header chung
alert_badge = (ui.badge(f"Cảnh báo lỗi ngân hàng {ext['rate']}", "critical") if ext.get("alert")
               else ui.badge("Thanh toán ổn định", "good"))
if log is None or log.empty:
    dq_badge = ui.badge("Chất lượng dữ liệu: chưa có log", "neutral")
elif log.iloc[-1]["status"] == "failed":
    dq_badge = ui.badge("Dữ liệu mới nhất bị chặn", "warning")
else:
    dq_badge = ui.badge(f"Dữ liệu đã kiểm tra · {len(log):,} file", "good")
st.markdown(
    f'<div class="page-head"><div><div class="page-title">Báo cáo vận hành tuần</div>'
    f'<div class="page-sub">{pd.Timestamp(facts["week_start"]):%d/%m/%Y} → {pd.Timestamp(facts["week_end"]):%d/%m/%Y}'
    f' · số liệu tính tới hết tuần này</div></div><div class="badges">{alert_badge}{dq_badge}</div></div>',
    unsafe_allow_html=True,
)

tabs = st.tabs(["Ban lãnh đạo", "Marketing", "CSKH", "Product / IT", "Tài chính", "Dữ liệu", "Hỏi dữ liệu"])

# ------------------------------------------------------------------ Ban lãnh đạo
with tabs[0]:
    now, before = ui.pct(facts["success_rate"]), ui.pct(facts["success_rate_prev_8_weeks"])
    ui.tiles([
        ui.tile("Lượt thanh toán tuần này", facts["tickets"]),
        ui.tile("Tỷ lệ thanh toán thành công", facts["success_rate"],
                extra=ui.chip(now - before if now is not None and before is not None else None, "pct", +1),
                note="so với trung bình 8 tuần trước"),
        ui.tile("Khách mới mất ở bước thanh toán", facts["new_customers_lost_at_payment"],
                note=f"trên {facts['new_customers']} khách mới trong tuần"),
        ui.tile("Lỗi phía ngân hàng", ext.get("rate", "n/a"), alert=bool(ext.get("alert")),
                extra=ui.badge("Có cảnh báo", "critical") if ext.get("alert") else ui.badge("Bình thường", "good"),
                note=f"mức nền 8 tuần: {ext.get('baseline_rate', 'n/a')}"),
    ])

    kpi_table = tables["kpis"]
    month = facts["leadership"]["kpi_month"]
    ui.section(f"6 nhóm KPI · tháng {pd.Period(month).strftime('%m/%Y')}" if month in kpi_table.index else "6 nhóm KPI",
               "So với tháng trước. Xanh = tốt hơn, đỏ = xấu hơn, theo chiều tốt của từng chỉ số "
               "(vd. tỷ lệ lỗi giảm là xanh).")
    if month in kpi_table.index:
        months = kpi_table.index.tolist()
        prev = months[months.index(month) - 1] if months.index(month) > 0 else None
        groups = {}
        for group, key, label, fmt, direction in kpis.KPI_DEFINITIONS:
            value = kpi_table.at[month, key]
            if pd.isna(value):
                cell = '<span class="val na">Chưa đủ dữ liệu</span>'
            else:
                diff = value - kpi_table.at[prev, key] if prev and pd.notna(kpi_table.at[prev, key]) else None
                cell = f'<span class="val">{ui.esc(kpis.format_value(value, fmt))}</span>{ui.chip(diff, fmt, direction)}'
            groups.setdefault(group, []).append(
                f'<div class="kpi-row"><span class="name">{ui.esc(label)}</span><span class="right">{cell}</span></div>')
        cards = "".join(f'<div class="kpi-card"><div class="title">{ui.esc(g)}</div>{"".join(rows)}</div>'
                        for g, rows in groups.items())
        st.markdown(f'<div class="kpi-grid">{cards}</div>', unsafe_allow_html=True)
        st.caption("“Chưa đủ dữ liệu”: chỉ số cần theo dõi thêm 30/90 ngày sau tháng đó. "
                   "Tháng dưới 500 lượt thanh toán (giai đoạn COVID) không hiển thị.")

    ui.section("Xu hướng theo tháng")
    labels = {key: (label, fmt) for _, key, label, fmt, _ in kpis.KPI_DEFINITIONS}
    pick = st.selectbox("Chỉ số", list(labels), format_func=lambda k: labels[k][0], label_visibility="collapsed")
    series = kpi_table[pick].dropna().tail(18)
    fmt = labels[pick][1]
    xs, ys = month_axis(series) if len(series) else ([], [])
    fig = go.Figure(go.Scatter(
        x=xs, y=ys, mode="lines+markers", connectgaps=False,
        line={"color": C["s1"], "width": 2}, marker={"size": 8, "color": C["s1"], "line": {"color": C["surface"], "width": 2}},
        name=labels[pick][0], hovertemplate="%{x|%m/%Y}: %{y}<extra></extra>"))
    if len(series):
        fig.add_annotation(x=pd.Period(series.index[-1]).to_timestamp(), y=series.values[-1],
                           text=kpis.format_value(series.values[-1], fmt), showarrow=False, yshift=16,
                           font={"color": C["ink"], "size": 13})
    ui.style_figure(fig, height=300, legend=False)
    fig.update_xaxes(tickformat="%m/%y", dtick="M2")
    fig.update_yaxes(tickformat=".0%" if fmt == "pct" else ",")
    st.caption("Khoảng trống trên đường = tháng dưới 500 lượt thanh toán (rạp đóng cửa giai đoạn COVID), không có dữ liệu đáng tin.")
    st.plotly_chart(fig, width="stretch", config=ui.CHART_CONFIG)
    show_brief(facts, "leadership")

# ------------------------------------------------------------------ Marketing
with tabs[1]:
    mk = tables["marketing_targets"]
    camp = tables["campaign_effectiveness"]
    seg_counts = mk["segment"].value_counts()
    promo = camp.drop(index="none", errors="ignore")
    worst = promo["discount_per_returned"].idxmax() if len(promo) else None
    ui.tiles([
        ui.tile("Khách đã từng mua", f"{len(mk):,}"),
        ui.tile("Khách mua một lần (mới)", f"{seg_counts.get('Khách mua một lần (mới)', 0):,}",
                note="ưu tiên coupon lần mua thứ 2 trong 7–14 ngày"),
        ui.tile("Khách giá trị cao", f"{seg_counts.get('Khách giá trị cao', 0):,}", note="≥ 3 lần mua, còn hoạt động"),
        ui.tile("Campaign giữ chân kém nhất", worst or "n/a",
                note=f"{camp.at[worst, 'one_time_rate']:.0%} khách chỉ mua 1 lần" if worst else ""),
    ])

    ui.section("Phân nhóm khách", "Luật theo slide “Phân nhóm khách hàng & chiến lược giữ chân”.")
    seg = mk.groupby("segment").agg(customers=("score", "size"), avg_score=("score", "mean"))
    seg["action"] = seg.index.map(marketing.SEGMENT_ACTIONS)
    seg = seg.sort_values("customers", ascending=False).rename_axis("segment").reset_index()
    st.dataframe(pct100(seg, ["avg_score"]), hide_index=True, width="stretch", column_config={
        "segment": TXT("Nhóm khách"),
        "customers": st.column_config.ProgressColumn("Số khách", format="%d", min_value=0, max_value=int(seg["customers"].max())),
        "avg_score": NUM("Khả năng quay lại TB", format=PCT),
        "action": TXT("Hướng xử lý", width="large"),
    })

    ui.section("Campaign nào chỉ hút khách một lần?",
               "Tiền giảm giá phải bỏ ra để giữ được 1 khách mới quay lại trong 90 ngày (chỉ tính campaign khuyến mãi).")
    promo_sorted = promo.sort_values("discount_per_returned")
    fig = go.Figure(go.Bar(
        x=promo_sorted["discount_per_returned"], y=promo_sorted.index, orientation="h",
        marker={"color": [C["s1"] if i == worst else C["axis"] for i in promo_sorted.index]},
        text=[f"{v:,.0f}" for v in promo_sorted["discount_per_returned"]], textposition="outside",
        textfont={"color": C["ink"]}, hovertemplate="%{y}: %{x:,.1f}<extra></extra>"))
    ui.style_figure(fig, height=200, hover="closest", legend=False)
    fig.update_xaxes(showgrid=False, showticklabels=False, range=[0, promo_sorted["discount_per_returned"].max() * 1.12])
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(fig, width="stretch", config=ui.CHART_CONFIG)
    camp_view = pct100(camp[["new_customers", "returned_90d", "one_time_rate", "discount_per_returned"]],
                       ["returned_90d", "one_time_rate"]).rename_axis("type").reset_index()
    st.dataframe(camp_view, hide_index=True, width="stretch", column_config={
        "type": TXT("Loại campaign"), "new_customers": NUM("Khách mới", format="%d"),
        "returned_90d": NUM("Mua lại 90 ngày", format=PCT),
        "one_time_rate": NUM("Chỉ mua 1 lần", format=PCT),
        "discount_per_returned": NUM("Giảm giá / khách quay lại", format="%.1f"),
    })
    with st.expander("Từng mã campaign (≥ 300 khách mới), xếp theo tỷ lệ chỉ mua 1 lần"):
        ids = pct100(tables["campaign_ids"][["new_customers", "returned_90d", "one_time_rate", "discount_per_returned"]],
                     ["returned_90d", "one_time_rate"])
        st.dataframe(ids.rename_axis("campaign_id").reset_index(), hide_index=True, width="stretch", column_config={
            "campaign_id": TXT("Mã campaign"), "new_customers": NUM("Khách mới", format="%d"),
            "returned_90d": NUM("Mua lại 90 ngày", format=PCT),
            "one_time_rate": NUM("Chỉ mua 1 lần", format=PCT),
            "discount_per_returned": NUM("Giảm giá / khách quay lại", format="%.1f"),
        })
    st.caption("So sánh giữa các campaign là quan sát, chưa phải nhân quả - mỗi campaign có thể nhắm tệp khách khác nhau.")

    ui.section("Danh sách khách ưu tiên chăm sóc",
               "Điểm = khả năng mua lại trong 90 ngày (model, backtest AUC ~0.66): nhóm điểm cao mua lại ~1.8 lần "
               "trung bình. Dùng để ưu tiên ngân sách, không phải dự đoán chắc chắn.")
    pick = st.multiselect("Lọc nhóm", seg["segment"].tolist(), default=["Khách mua một lần (mới)"])
    shown = (mk[mk["segment"].isin(pick)] if pick else mk).rename_axis("customer_id").reset_index()
    st.dataframe(pct100(shown.head(500)[["customer_id", "segment", "score", "action", "recency_days", "frequency", "monetary"]], ["score"]),
                 hide_index=True, width="stretch", column_config={
                     "customer_id": TXT("Mã khách"), "segment": TXT("Nhóm"),
                     "score": st.column_config.ProgressColumn("Khả năng quay lại", format=PCT, min_value=0, max_value=100),
                     "action": TXT("Hướng xử lý", width="large"),
                     "recency_days": NUM("Ngày từ lần mua gần nhất", format="%d"),
                     "frequency": NUM("Số lần mua", format="%d"), "monetary": NUM("Tổng chi tiêu", format="%.2f"),
                 })
    download(shown, "marketing_targets.csv", f"Tải danh sách ({len(shown):,} khách)")
    show_brief(facts, "marketing")

# ------------------------------------------------------------------ CSKH
with tabs[2]:
    if ext.get("alert"):
        ui.callout(f"<b>⚠ Đang có cảnh báo lỗi phía ngân hàng: {ui.esc(ext['rate'])}</b> (mức nền {ui.esc(ext['baseline_rate'])}). "
                   "Chủ động hướng dẫn khách chuyển sang <b>Ví trong app</b>.", "critical")
    bank = recovery["status_id"].isin([-3, -5])
    errors = pd.Series(facts["customer_care"]["errors_by_code"]).str.replace(",", "").astype(int).sort_values()
    ui.tiles([
        ui.tile("Khách cần liên hệ lại", f"{len(recovery):,}", note="lỗi trong tuần, chưa mua lại được"),
        ui.tile("Do lỗi phía ngân hàng", f"{bank.mean():.0%}" if len(recovery) else "n/a",
                note="khách không tự sửa được → ưu tiên gọi"),
        ui.tile("Lỗi phổ biến nhất", error_vi(facts["top_error"]), note=f"{facts['top_error_count']} lượt · {facts['top_error']}"),
    ])
    left, right = st.columns([2, 3])
    with left:
        ui.section("Số lỗi theo mã")
        fig = go.Figure(go.Bar(x=errors.values, y=[error_vi(i) for i in errors.index], orientation="h",
                               marker={"color": C["s1"]}, text=errors.values, textposition="outside",
                               textfont={"color": C["ink"]}, hovertemplate="%{y}: %{x}<extra></extra>"))
        ui.style_figure(fig, height=60 + 36 * len(errors), hover="closest", legend=False)
        fig.update_xaxes(showticklabels=False, showgrid=False, range=[0, errors.max() * 1.18])
        st.plotly_chart(fig, width="stretch", config=ui.CHART_CONFIG)
    with right:
        ui.section("Mẫu tin nhắn theo mã lỗi")
        rows = "".join(f'<div class="msg"><span class="code">{ui.esc(STATUS_VI.get(code, code))} ({code})</span>'
                       f'<span>{ui.esc(text)}</span></div>' for code, text in briefs.RECOVERY_MESSAGES.items())
        st.markdown(f'<div class="msg-list">{rows}</div>', unsafe_allow_html=True)

    ui.section(f"Danh sách cứu đơn · {len(recovery):,} khách")
    rec = recovery.assign(time=recovery["time"].dt.strftime("%d/%m %H:%M"), bank=bank.map({True: "⚠ Ngân hàng", False: ""}),
                          description=recovery["description"].map(error_vi))
    st.dataframe(rec[["customer_id", "time", "paying_method", "bank", "description", "message"]], hide_index=True,
                 width="stretch", column_config={
                     "customer_id": TXT("Mã khách"), "time": TXT("Thời điểm lỗi"), "paying_method": TXT("Phương thức"),
                     "bank": TXT("Ưu tiên"), "description": TXT("Lỗi"), "message": TXT("Tin nhắn gửi khách", width="large"),
                 })
    download(recovery, "recovery_list.csv", "Tải danh sách cứu đơn")
    show_brief(facts, "customer_care")

# ------------------------------------------------------------------ Product / IT
with tabs[3]:
    group = st.segmented_control("Nhóm lỗi", list(GROUP_LABELS), default="external",
                                 format_func=GROUP_LABELS.get, label_visibility="collapsed") or "external"
    # 26 tuần THEO LỊCH tới tuần đang xem; tuần thiếu dữ liệu (< 100 lượt) để trống, không nối thẳng qua
    start = week - pd.Timedelta(weeks=25)
    data = (alerts[(alerts["error_group"] == group) & alerts["week"].between(start, week)]
            .set_index("week").reindex(pd.date_range(start, week, freq="W-MON")).rename_axis("week").reset_index())
    data["is_alert"] = data["is_alert"].astype("boolean").fillna(False).astype(bool)
    current = data[(data["week"] == week) & data["rate"].notna()]
    row = current.iloc[0] if len(current) else None
    flagged = bool(row is not None and row["is_alert"])
    ui.tiles([
        ui.tile(f"Tỷ lệ lỗi {GROUP_LABELS[group].split(' (')[0].lower()} tuần này",
                f"{row['rate']:.1%}" if row is not None else "n/a", alert=flagged,
                extra=ui.badge("Có cảnh báo", "critical") if flagged else ui.badge("Bình thường", "good"),
                note=f"mức nền 8 tuần: {row['baseline']:.1%}" if row is not None and pd.notna(row["baseline"]) else ""),
        ui.tile("Lỗi vượt mức bình thường", f"{row['excess_errors']:,.0f}" if row is not None and pd.notna(row["excess_errors"]) else "n/a",
                note="số lỗi nhiều hơn mức nền"),
        ui.tile("Độ lệch (z)", f"{row['z']:.1f}" if row is not None and pd.notna(row["z"]) else "n/a",
                note="cảnh báo khi z ≥ 3 và tuần ≥ 100 lượt"),
    ])
    ui.section("26 tuần gần nhất", "Đường xanh: tỷ lệ lỗi tuần · đường xám: mức nền (trung vị 8 tuần trước) · chấm đỏ: tuần có cảnh báo.")
    fig = go.Figure()
    fig.add_scatter(x=data["week"], y=data["baseline"], name="Mức nền", mode="lines",
                    line={"color": C["axis"], "width": 2}, connectgaps=False, hovertemplate="Mức nền: %{y:.1%}<extra></extra>")
    fig.add_scatter(x=data["week"], y=data["rate"], name="Tỷ lệ lỗi tuần", mode="lines+markers", connectgaps=False,
                    line={"color": C["s1"], "width": 2}, marker={"size": 8, "color": C["s1"], "line": {"color": C["surface"], "width": 2}},
                    hovertemplate="Tỷ lệ lỗi: %{y:.1%}<extra></extra>")
    hits = data[data["is_alert"]]
    fig.add_scatter(x=hits["week"], y=hits["rate"], name="Cảnh báo", mode="markers",
                    marker={"size": 13, "color": C["critical"], "symbol": "circle", "line": {"color": C["surface"], "width": 2}},
                    hovertemplate="⚠ Cảnh báo: %{y:.1%}<extra></extra>")
    fig.update_xaxes(tickformat="%d/%m/%y")
    fig.add_vrect(x0=week - pd.Timedelta(days=3), x1=week + pd.Timedelta(days=3), fillcolor=C["s1_light"], opacity=0.6,
                  line_width=0, layer="below", annotation_text="tuần đang xem", annotation_position="top left",
                  annotation_font={"color": C["ink2"], "size": 12})
    ui.style_figure(fig, height=340)
    fig.update_yaxes(tickformat=".0%", rangemode="tozero")
    st.plotly_chart(fig, width="stretch", config=ui.CHART_CONFIG)

    ui.section("Khoanh vùng: mã lỗi × nền tảng × phương thức",
               "Tuần này so với 8 tuần trước, xếp theo số lỗi vượt mức - dòng đầu là chỗ cần xử lý trước.")
    br = tables["product_breakdown"].head(15).copy()
    br[["rate", "baseline_rate"]] = br[["rate", "baseline_rate"]] * 100
    br["description"] = br["description"].map(error_vi)
    st.dataframe(br[["description", "platform", "paying_method", "errors", "attempts", "rate", "baseline_rate",
                     "change_pp", "excess_errors"]], hide_index=True, width="stretch", column_config={
        "description": TXT("Mã lỗi", width="medium"), "platform": TXT("Nền tảng"), "paying_method": TXT("Phương thức"),
        "errors": NUM("Số lỗi", format="%d"), "attempts": NUM("Lượt thanh toán", format="%d"),
        "rate": NUM("Tỷ lệ tuần này", format=PCT), "baseline_rate": NUM("8 tuần trước", format=PCT),
        "change_pp": NUM("Thay đổi (điểm %)", format="%+.1f"), "excess_errors": NUM("Lỗi vượt mức", format="%.0f"),
    })
    download(tables["product_breakdown"], "product_breakdown.csv")
    show_brief(facts, "product_it")

# ------------------------------------------------------------------ Tài chính
with tabs[4]:
    fin = facts["finance"]
    ui.tiles([
        ui.tile("Giá trị giao dịch lỗi tuần này", facts["failed_ticket_value"]),
        ui.tile("Chi phí giảm giá tuần này", facts["discount_spend"]),
        ui.tile("Đơn lỗi không được mua lại", fin["unrecovered_share"],
                note=f"tháng {month_vi(fin['unrecovered_month'])} · trong 7 ngày sau lỗi"),
        ui.tile("Giảm giá cho khách không quay lại", fin["one_time_discount_share"],
                note=f"tháng {month_vi(fin['one_time_discount_month'])} · trong 90 ngày"),
    ])
    losses = tables["monthly_losses"].dropna(how="all")
    losses = losses[losses.index >= "2021-11"]
    ui.section("Thất thoát theo tháng", "Đơn vị tiền theo dữ liệu nguồn. Tháng gần nhất để trống vì chưa đủ 7 / 90 ngày quan sát.")
    x = [pd.Period(m).to_timestamp() for m in losses.index]
    fig = go.Figure()
    fig.add_bar(x=x, y=losses["unrecovered_failed_value"], name="Đơn lỗi không được mua lại", marker_color=C["s1"],
                hovertemplate="%{y:,.0f}<extra>Đơn lỗi không mua lại</extra>")
    fig.add_bar(x=x, y=losses["discount_one_time"], name="Giảm giá cho khách không quay lại", marker_color=C["s2"],
                hovertemplate="%{y:,.0f}<extra>Giảm giá lãng phí</extra>")
    ui.style_figure(fig, height=340)
    fig.update_layout(barmode="group")
    fig.update_xaxes(dtick="M1", tickformat="%m/%y")
    fig.update_yaxes(tickformat=",")
    st.plotly_chart(fig, width="stretch", config=ui.CHART_CONFIG)
    # Bảng nhỏ (≤ 14 tháng) -> định dạng sẵn thành chữ để ô chưa đủ dữ liệu hiện "—" thay vì "None"
    money = lambda v: "—" if pd.isna(v) else f"{v:,.0f}"
    share = lambda v: "—" if pd.isna(v) else f"{v:.1%}"
    fin_view = pd.DataFrame({
        "Tháng": [pd.Period(m).strftime("%m/%Y") for m in losses.index],
        "Giá trị đơn lỗi": losses["failed_value"].map(money),
        "Không mua lại (7 ngày)": losses["unrecovered_failed_value"].map(money),
        "% không mua lại": losses["unrecovered_share"].map(share),
        "Tổng giảm giá": losses["discount_total"].map(money),
        "Cho khách không quay lại (90 ngày)": losses["discount_one_time"].map(money),
        "% giảm giá lãng phí": losses["one_time_discount_share"].map(share),
    })
    st.dataframe(fin_view, hide_index=True, width="stretch")
    st.caption("— = chưa đủ thời gian quan sát (7 ngày sau đơn lỗi / 90 ngày sau giao dịch khuyến mãi).")
    show_brief(facts, "finance")

# ------------------------------------------------------------------ Dữ liệu
with tabs[5]:
    if log is not None and not log.empty:
        blocked = int((log["status"] == "failed").sum())
        ui.tiles([
            ui.tile("File đã kiểm tra", f"{len(log):,}"),
            ui.tile("File bị chặn", f"{blocked:,}", alert=blocked > 0,
                    extra=ui.badge("Cần xử lý", "warning") if blocked else ui.badge("Không có", "good")),
            ui.tile("File có cảnh báo", f"{int(log['warnings'].notna().sum()):,}", note="không chặn, chỉ cần theo dõi"),
            ui.tile("File gần nhất", str(log.iloc[-1]["date"]), note=str(log.iloc[-1]["file"])),
        ])
        ui.section("Lịch sử kiểm tra (50 file gần nhất)")
        view = log.tail(50).iloc[::-1].assign(status=lambda d: d["status"].map({"passed": "✓ Đạt", "failed": "⛔ Bị chặn"}))
        view[["errors", "warnings"]] = view[["errors", "warnings"]].fillna("").replace({"volume": "số dòng bất thường",
                                                                                         "unknown_device": "thiết bị lạ",
                                                                                         "exact_duplicates": "dòng trùng"}, regex=True)
        st.dataframe(view[["date", "file", "rows", "status", "errors", "warnings"]], hide_index=True, width="stretch",
                     column_config={"date": TXT("Ngày"), "file": TXT("File"), "rows": NUM("Số dòng", format="%d"),
                                    "status": TXT("Kết quả"), "errors": TXT("Lỗi"), "warnings": TXT("Cảnh báo")})
    else:
        ui.callout("Chưa có log kiểm tra. Chạy <code>python -m src.ingest simulate</code> rồi <code>python -m src.ingest run</code>.")
    ui.section("Dataset cho analyst / product", "Từ điển dữ liệu sinh tự động bởi src/marts.py.")
    dictionary_file = MARTS_DIR / "data_dictionary.csv"
    if dictionary_file.exists():
        dictionary = pd.read_csv(dictionary_file)
        table = st.segmented_control("Bảng", dictionary["table"].unique().tolist(),
                                     default=dictionary["table"].iloc[0], label_visibility="collapsed") or dictionary["table"].iloc[0]
        st.dataframe(pct100(dictionary[dictionary["table"] == table][["column", "dtype", "description", "null_rate", "n_unique", "examples"]], ["null_rate"]),
                     hide_index=True, width="stretch", column_config={
                         "column": TXT("Cột"), "dtype": TXT("Kiểu"), "description": TXT("Mô tả", width="large"),
                         "null_rate": NUM("Trống", format=PCT), "n_unique": NUM("Giá trị khác nhau", format="%d"),
                         "examples": TXT("Ví dụ")})
    else:
        ui.callout("Chưa có dataset. Chạy <code>python -m src.marts</code>.")

# ------------------------------------------------------------------ Hỏi dữ liệu
@st.cache_resource(show_spinner="Đang chuẩn bị chỉ mục tài liệu…", max_entries=1)
def rag_index(fingerprint=None):
    """`fingerprint` đổi (có tài liệu / bản tin mới) -> xây lại chỉ mục; chỉ nhúng đoạn mới nhờ cache."""
    try:
        return rag.build_index()
    except LLMUnavailable:  # không nhúng được tài liệu -> vẫn tìm được bằng từ khóa
        return rag.build_index(use_embeddings=False)


def rag_answer(question):
    """Nhớ câu trả lời trong phiên (Streamlit chạy lại script mỗi lần bấm) - không lưu lần gọi API lỗi."""
    memo = st.session_state.setdefault("rag_answers", {})
    if question not in memo:
        res = rag.answer(rag_index(rag.source_fingerprint()), question)
        if res["status"] == "search_only":
            return res
        memo[question] = res
    return memo[question]


def show_passages(items):
    for i, chunk in items:
        with st.expander(f"[{i}] {chunk.label} › {chunk.title}"):
            st.markdown(chunk.text)


with tabs[6]:
    mode = st.radio("Chế độ", ["Hỏi tài liệu & báo cáo", "Hỏi số liệu (SQL)"], horizontal=True,
                    label_visibility="collapsed")

    if mode == "Hỏi tài liệu & báo cáo":
        ui.section("Hỏi tài liệu & báo cáo bằng tiếng Việt",
                   "Tìm trong hướng dẫn vận hành, định nghĩa chỉ số, kết quả phân tích và bản tin các tuần; "
                   "Gemini trả lời CHỈ từ các đoạn tìm được, kèm nguồn [n]. Số không có trong tài liệu sẽ bị chặn.")
        if not gemini.enabled():
            ui.callout("Chưa có <b>GEMINI_API_KEY</b> trong file <code>.env</code>: vẫn tìm được đoạn tài liệu liên quan, "
                       "nhưng không viết câu trả lời.")
        examples = [q["question"] for q in rag.load_eval() if q["sources"]]
        question = (st.selectbox("Câu hỏi mẫu", [""] + examples, key="rag_example", placeholder="Chọn câu hỏi mẫu")
                    or st.text_input("Hoặc tự đặt câu hỏi", key="rag_question",
                                     placeholder="vd. Khi có cảnh báo lỗi ngân hàng thì CSKH cần làm gì?"))
        if question:
            with st.spinner("Đang tìm trong tài liệu…"):
                res = rag_answer(question)
            if res["status"] == "answered":
                with st.container(border=True):
                    st.markdown(res["answer"])
                ui.section("Nguồn", "Bấm để xem nguyên văn đoạn tài liệu đã dùng.")
                show_passages(res["sources"])
            else:
                if res["status"] == "not_found":
                    ui.callout(f"<b>Tài liệu chưa có thông tin này.</b> {ui.esc(res['answer'])}<br>"
                               "Câu hỏi cần tính số liệu (doanh thu, số vé theo tháng…)? Dùng chế độ <b>Hỏi số liệu (SQL)</b>.")
                else:
                    st.warning(res["note"])
                ui.section("Đoạn tài liệu liên quan nhất")
                show_passages(list(enumerate((c for c, _ in res["hits"]), 1)))
            model = f" · trả lời bởi {res['model']}" if res["model"] else ""
            index = rag_index(rag.source_fingerprint())
            st.caption(f"Tìm kiếm: {index.mode} · {len(index.chunks)} đoạn tài liệu{model}")
    else:
        ui.section("Hỏi số liệu bằng tiếng Việt",
                   "Gemini chuyển câu hỏi thành 1 câu SQL chỉ-đọc (SELECT) rồi chạy trên toàn bộ dữ liệu giao dịch "
                   "2019-2022. Câu lệnh sửa / xóa dữ liệu bị chặn.")
        if not gemini.enabled():
            ui.callout("Tính năng cần <b>GEMINI_API_KEY</b> trong file <code>.env</code>.")
        examples = [q["question"] for q in ask_data.load_eval()]
        question = (st.selectbox("Câu hỏi mẫu", [""] + examples, key="sql_example", placeholder="Chọn câu hỏi mẫu")
                    or st.text_input("Hoặc tự đặt câu hỏi", key="sql_question",
                                     placeholder="vd. Tỷ lệ thanh toán thành công trên mobile năm 2022?"))
        if question:
            memo = st.session_state.setdefault("sql_answers", {})
            try:
                if question not in memo:
                    with st.spinner("Gemini đang viết câu SQL…"):
                        memo[question] = ask_data.ask(sql_connection(), question)
                answer = memo[question]
                st.dataframe(answer["result"], hide_index=True)
                st.caption(f"{answer['explanation']} · trả lời bởi {answer['model']}")
                with st.expander("Xem câu SQL"):
                    st.code(answer["sql"], language="sql")
            except LLMUnavailable as exc:
                st.warning(f"Chưa dùng được Gemini: {exc}.")
            except ValueError as exc:
                st.error(f"Câu SQL bị chặn: {exc}")
            except pd.errors.DatabaseError as exc:
                st.error(f"Gemini sinh câu SQL không chạy được: {exc}")
