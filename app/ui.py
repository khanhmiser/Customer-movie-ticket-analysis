"""Giao diện dùng chung cho dashboard: màu, CSS, thẻ chỉ số, nhãn trạng thái, kiểu biểu đồ.

Bảng màu thương hiệu (người dùng chọn): navy #091540 · xanh đậm #1B2CC1 · xanh nhạt #7692FF · xanh rất nhạt #ABD2FA.
- Navy làm chữ chính + dải tiêu đề; #1B2CC1 = chuỗi chính (s1); #7692FF = chuỗi thứ 2 (s2); #ABD2FA = nền nhấn.
- validate_palette (s1, s2): CVD ΔE 24.5, mắt thường ΔE 28.6 → phân biệt tốt nhờ khác độ sáng. #7692FF tương phản
  2.79:1 với nền (< 3:1) → biểu đồ 2 chuỗi luôn có chú thích + bảng số bên dưới.
- Màu trạng thái (xanh lá/đỏ/vàng) giữ nguyên: chỉ dùng khi MANG NGHĨA tốt/xấu, luôn đi kèm biểu tượng + chữ.
"""

import html

import pandas as pd
import streamlit as st

C = {
    "page": "#f4f7fd", "surface": "#ffffff", "ink": "#091540", "ink2": "#3b4468", "muted": "#687092",
    "grid": "#e3e9f5", "axis": "#c3cad9", "border": "rgba(9,21,64,0.10)", "wash": "#eaf2fd",
    "navy": "#091540", "s1": "#1B2CC1", "s2": "#7692FF", "s1_light": "#ABD2FA",
    "good": "#0ca30c", "good_text": "#006300", "good_bg": "#e3f4e3",
    "critical": "#d03b3b", "critical_bg": "#fbe7e7", "warning": "#fab219", "warning_bg": "#fdf3dc",
}
FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'

CSS = f"""
<style>
:root {{ --s1: {C['s1']}; }}
html, body, [class*="css"] {{ font-family: {FONT}; }}
.block-container {{ padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1360px; }}
[data-testid="stToolbar"] .stDeployButton, .stDeployButton {{ display: none; }}
h1, h2, h3 {{ letter-spacing: -0.01em; }}

/* Tabs: to hơn, rõ tab đang chọn */
.stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid {C['grid']}; }}
.stTabs [data-baseweb="tab"] {{ padding: 10px 14px; font-size: 15px; font-weight: 500; color: {C['ink2']}; }}
.stTabs [aria-selected="true"] {{ color: {C['ink']}; }}
.stTabs [data-baseweb="tab-highlight"] {{ background-color: {C['s1']}; height: 3px; }}

/* Header trang */
/* Dải tiêu đề navy: chữ trắng / xanh rất nhạt (tương phản > 10:1) */
.page-head {{ display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between;
              gap: 12px; margin-bottom: 10px; padding: 18px 22px; border-radius: 14px;
              background: linear-gradient(120deg, {C['navy']} 0%, {C['navy']} 55%, {C['s1']} 140%); }}
.page-title {{ font-size: 26px; font-weight: 650; color: #ffffff; line-height: 1.2; }}
.page-sub {{ font-size: 14px; color: {C['s1_light']}; margin-top: 2px; }}
.badges {{ display: flex; flex-wrap: wrap; gap: 8px; }}

/* Nhãn trạng thái: luôn có biểu tượng + chữ, không chỉ dựa vào màu */
.badge {{ display: inline-flex; align-items: center; gap: 6px; padding: 5px 10px; border-radius: 999px;
          font-size: 13px; font-weight: 550; border: 1px solid {C['border']}; background: {C['surface']}; color: {C['ink2']}; }}
.badge .dot {{ width: 8px; height: 8px; border-radius: 50%; background: {C['muted']}; }}
.badge.good {{ background: {C['good_bg']}; color: {C['good_text']}; }}
.badge.good .dot {{ background: {C['good']}; }}
.badge.critical {{ background: {C['critical_bg']}; color: #8f1f1f; }}
.badge.critical .dot {{ background: {C['critical']}; }}
.badge.warning {{ background: {C['warning_bg']}; color: #7a5200; }}
.badge.warning .dot {{ background: {C['warning']}; }}

/* Thẻ chỉ số */
.tiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; margin: 10px 0 18px; }}
.tile {{ background: {C['surface']}; border: 1px solid {C['border']}; border-top: 3px solid {C['s1']};
          border-radius: 12px; padding: 13px 16px 14px; box-shadow: 0 1px 3px rgba(9,21,64,0.06); }}
.tile .label {{ font-size: 13px; color: {C['ink2']}; }}
.tile .value {{ font-size: 28px; font-weight: 600; color: {C['ink']}; margin-top: 4px; line-height: 1.15; }}
.tile .note {{ font-size: 12.5px; color: {C['muted']}; margin-top: 6px; }}
.tile.alert {{ border-color: {C['critical']}; border-top-color: {C['critical']}; box-shadow: inset 4px 0 0 {C['critical']}; }}

/* Chip thay đổi: mũi tên + chữ; màu = hướng thay đổi × chiều tốt của chỉ số */
.chip {{ display: inline-block; margin-top: 6px; padding: 2px 8px; border-radius: 6px; font-size: 12.5px;
         font-weight: 550; background: {C['wash']}; color: {C['ink2']}; }}
.chip.good {{ background: {C['good_bg']}; color: {C['good_text']}; }}
.chip.bad {{ background: {C['critical_bg']}; color: #8f1f1f; }}

/* Lưới 6 nhóm KPI: các thẻ cao bằng nhau */
.kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 14px; align-items: stretch; }}
.kpi-card {{ background: {C['surface']}; border: 1px solid {C['border']}; border-radius: 12px; padding: 14px 16px;
              box-shadow: 0 1px 3px rgba(9,21,64,0.06); }}
.kpi-card .title {{ font-size: 14px; font-weight: 650; color: {C['ink']}; margin-bottom: 8px;
                    padding-bottom: 8px; border-bottom: 2px solid {C['s1_light']}; }}
.kpi-row {{ display: flex; justify-content: space-between; align-items: baseline; gap: 10px;
            padding: 9px 0; border-top: 1px solid {C['grid']}; }}
.kpi-row:first-of-type {{ border-top: none; }}
.kpi-row .name {{ font-size: 13px; color: {C['ink2']}; }}
.kpi-row .right {{ text-align: right; white-space: nowrap; }}
.kpi-row .val {{ font-size: 19px; font-weight: 600; color: {C['ink']}; }}
.kpi-row .val.na {{ font-size: 13px; font-weight: 500; color: {C['muted']}; }}
.kpi-row .chip {{ margin: 0 0 0 8px; }}

.section {{ font-size: 18px; font-weight: 650; color: {C['ink']}; margin: 24px 0 2px;
             padding-left: 10px; border-left: 4px solid {C['s1']}; line-height: 1.3; }}
.section-sub {{ font-size: 13px; color: {C['ink2']}; margin-bottom: 8px; padding-left: 14px; }}
.callout {{ border-radius: 10px; padding: 12px 14px; margin: 8px 0 14px; font-size: 14px; }}
.callout.critical {{ background: {C['critical_bg']}; color: #6b1515; border: 1px solid #f2c4c4; }}
.msg-list {{ background: {C['surface']}; border: 1px solid {C['border']}; border-radius: 12px; padding: 4px 14px; }}
.msg {{ display: flex; gap: 12px; padding: 9px 0; border-top: 1px solid {C['grid']}; font-size: 13.5px; color: {C['ink']}; }}
.msg:first-child {{ border-top: none; }}
.msg .code {{ flex: 0 0 150px; color: {C['ink2']}; font-weight: 550; }}
.callout.info {{ background: {C['wash']}; color: {C['ink']}; border: 1px solid {C['s1_light']}; }}

section[data-testid="stSidebar"] {{ background: {C['wash']}; border-right: 1px solid {C['s1_light']}; }}
section[data-testid="stSidebar"] .block-container {{ padding-top: 1.2rem; }}
.side-title {{ font-size: 18px; font-weight: 650; color: {C['ink']}; }}
.side-sub {{ font-size: 12.5px; color: {C['ink2']}; margin-bottom: 10px; }}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def esc(text):
    return html.escape(str(text))


def badge(text, status="neutral"):
    return f'<span class="badge {status}"><span class="dot"></span>{esc(text)}</span>'


def chip(diff, fmt, direction):
    """Chip thay đổi so với kỳ trước. direction = +1 nếu tăng là tốt, -1 nếu giảm là tốt."""
    if diff is None or pd.isna(diff):
        return ""
    text = format_delta(diff, fmt)
    if not any(ch in "123456789" for ch in text):  # vd. "-0.00": thay đổi nhỏ hơn mức hiển thị
        return '<span class="chip">= không đổi</span>'
    arrow = "▲" if diff > 0 else "▼"
    tone = "good" if diff * direction > 0 else "bad"
    return f'<span class="chip {tone}">{arrow} {esc(text)}</span>'


def format_delta(diff, fmt):
    if fmt == "pct":
        return f"{diff * 100:+.1f} điểm %"
    if fmt == "int":
        return f"{diff:+,.0f}"
    if fmt == "money":
        return f"{diff:+,.2f}" if abs(diff) < 1000 else f"{diff:+,.0f}"
    return f"{diff:+.2f}"


def tile(label, value, note="", extra="", alert=False):
    return (f'<div class="tile{" alert" if alert else ""}"><div class="label">{esc(label)}</div>'
            f'<div class="value">{esc(value)}</div>{extra}'
            f'{f"<div class=note>{esc(note)}</div>" if note else ""}</div>')


def tiles(items):
    st.markdown(f'<div class="tiles">{"".join(items)}</div>', unsafe_allow_html=True)


def section(title, sub=""):
    st.markdown(f'<div class="section">{esc(title)}</div>'
                f'{f"<div class=section-sub>{esc(sub)}</div>" if sub else ""}', unsafe_allow_html=True)


def callout(text, kind="info"):
    st.markdown(f'<div class="callout {kind}">{text}</div>', unsafe_allow_html=True)


def pct(text):
    """'80.8%' -> 0.808 (FACTS đã format sẵn)."""
    try:
        return float(str(text).rstrip("%")) / 100
    except ValueError:
        return None


def style_figure(fig, height=340, hover="x unified", legend=True):
    """Kiểu biểu đồ chung: nền sáng, lưới mảnh nằm ngang, trục nhạt, chú thích phía trên."""
    fig.update_layout(
        height=height, margin={"l": 8, "r": 8, "t": 36 if legend else 12, "b": 8},
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font={"family": FONT, "size": 13, "color": C["ink2"]},
        hovermode=hover, hoverlabel={"bgcolor": "#ffffff", "bordercolor": C["grid"], "font": {"color": C["ink"]}},
        showlegend=legend,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0, "title": None},
        bargap=0.28, bargroupgap=0.08, barcornerradius=4,
    )
    fig.update_xaxes(showgrid=False, linecolor=C["axis"], tickfont={"color": C["muted"]}, ticks="", title=None)
    fig.update_yaxes(gridcolor=C["grid"], gridwidth=1, zeroline=False, linecolor=C["axis"],
                     tickfont={"color": C["muted"]}, title=None)
    return fig


CHART_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]}
