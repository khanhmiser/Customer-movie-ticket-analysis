"""Bản tin tuần cho từng phòng ban.

Nguyên tắc chống "AI bịa số": Python tính toàn bộ số liệu (FACTS), LLM chỉ được diễn đạt.
Mọi con số trong bản tin LLM viết ra phải xuất hiện trong FACTS, nếu không -> dùng bản template.
"""

import json
import re

import pandas as pd

from src.llm import LLMUnavailable, generate_json

DEPARTMENTS = {
    "marketing": "Marketing",
    "customer_care": "Chăm sóc khách hàng (CSKH)",
    "product_it": "Product / IT",
    "finance": "Tài chính",
    "leadership": "Ban lãnh đạo",
}

# Mẫu tin nhắn cứu đơn theo mã lỗi - nội dung cố định đã duyệt, không để LLM tự sáng tác
RECOVERY_MESSAGES = {
    -1: "Đơn đặt vé của bạn đã quá hạn thanh toán. Ghế vẫn có thể còn trống - đặt lại trong 1 chạm tại đây.",
    -2: "Tài khoản chưa đủ số dư nên giao dịch chưa thành công. Bạn có thể thanh toán bằng Ví trong app để giữ ghế.",
    -3: "Ngân hàng chưa phản hồi nên vé chưa được xuất. Bạn chưa bị trừ tiền - thử lại hoặc chọn Ví trong app.",
    -4: "Tài khoản thanh toán bị khóa tạm do nhập sai mật khẩu nhiều lần. Chọn 'Quên mật khẩu' để mở khóa rồi đặt lại vé.",
    -5: "Thanh toán qua ngân hàng chưa thành công (lỗi từ phía ngân hàng). Thử lại sau ít phút hoặc chọn Ví trong app.",
    -6: "Bạn cần xác minh tài khoản để tiếp tục thanh toán. Hoàn tất xác minh trong 2 phút tại đây.",
    -7: "Giao dịch đang bị giới hạn tạm thời. Đội hỗ trợ sẽ liên hệ bạn - hoặc nhắn tin cho chúng tôi để được xử lý ngay.",
}

BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "summary": {"type": "string"},
        "key_points": {"type": "array", "items": {"type": "string"}},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "owner": {"type": "string"},
                    "kpi": {"type": "string"},
                },
                "required": ["action", "owner", "kpi"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["headline", "summary", "key_points", "actions"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """Bạn là chuyên viên phân tích dữ liệu của một nền tảng bán vé xem phim online.
Nhiệm vụ: viết bản tin tuần ngắn gọn, bằng tiếng Việt, cho một phòng ban cụ thể.

Quy tắc bắt buộc về số liệu:
- Chỉ dùng các con số có trong FACTS, chép nguyên định dạng (kể cả dấu phẩy, dấu chấm, ký hiệu %).
- Không tự tính thêm số mới (không cộng, trừ, chia, làm tròn lại).
- Nếu FACTS không có số cần thiết thì diễn đạt bằng lời, không đoán.

Nội dung: 1 tiêu đề, 1 đoạn tóm tắt 2-3 câu, 3-5 điểm chính, 2-4 hành động cụ thể
(mỗi hành động có người phụ trách và chỉ số theo dõi). Viết cho người không chuyên dữ liệu."""


def _fmt_int(x):
    return f"{int(round(x)):,}"


def _fmt_pct(x):
    return f"{x * 100:.1f}%"


def weekly_facts(df, alerts, week_start):
    """Tính FACTS cho tuần bắt đầu `week_start` (thứ Hai). Mọi số đều đã format sẵn."""
    week_start = pd.Timestamp(week_start)
    week = df[df["week"] == week_start]
    prev_weeks = df[(df["week"] < week_start) & (df["week"] >= week_start - pd.Timedelta(weeks=8))]
    if week.empty:
        raise ValueError(f"Không có giao dịch trong tuần {week_start.date()}")

    # Khách mới = khách có lần thanh toán đầu tiên rơi vào tuần này
    first_week = df.groupby("customer_id")["week"].transform("min")
    new = week[first_week.loc[week.index] == week_start]
    new_first = new.groupby("customer_id").head(1)
    converted = set(new.loc[new["is_success"], "customer_id"])
    new_failed_first = new_first[new_first["is_failed"]]
    new_lost = new_failed_first[~new_failed_first["customer_id"].isin(converted)]

    failed = week[week["is_failed"]]
    top_error = failed["description"].value_counts()
    method = week.groupby("paying_method").agg(n=("ticket_id", "count"), fail=("is_failed", "mean"))
    method = method[method["n"] >= 30].sort_values("fail", ascending=False)

    week_alerts = alerts[(alerts["week"] == week_start)].set_index("error_group")
    success = week[week["is_success"]]

    facts = {
        "week_start": str(week_start.date()),
        "week_end": str((week_start + pd.Timedelta(days=6)).date()),
        "tickets": _fmt_int(len(week)),
        "success_rate": _fmt_pct(week["is_success"].mean()),
        "success_rate_prev_8_weeks": _fmt_pct(prev_weeks["is_success"].mean()) if len(prev_weeks) else "n/a",
        "failed_tickets": _fmt_int(len(failed)),
        "failed_ticket_value": _fmt_int(failed["final_price"].sum()),
        "top_error": top_error.index[0] if len(top_error) else "none",
        "top_error_count": _fmt_int(top_error.iloc[0]) if len(top_error) else "0",
        "new_customers": _fmt_int(new_first.shape[0]),
        "new_customers_failed_first_payment": _fmt_int(len(new_failed_first)),
        "new_customers_lost_at_payment": _fmt_int(len(new_lost)),
        "promotion_share_of_success": _fmt_pct(success["type"].eq("promotion").mean()) if len(success) else "n/a",
        "discount_spend": _fmt_int(success["discount_value"].sum()),
        "worst_payment_method": method.index[0] if len(method) else "n/a",
        "worst_payment_method_failure_rate": _fmt_pct(method["fail"].iloc[0]) if len(method) else "n/a",
        "best_payment_method": method.index[-1] if len(method) else "n/a",
        "best_payment_method_failure_rate": _fmt_pct(method["fail"].iloc[-1]) if len(method) else "n/a",
        "error_groups": {},
        "definitions": {
            "recovery_window": "mua lại thành công trong 7 ngày sau giao dịch lỗi",
            "retention_window": "giữ chân = mua lần 2 trong 30 ngày",
            "repeat_window": "quay lại / chỉ mua 1 lần = có / không mua thêm trong 90 ngày",
            "baseline_window": "mức nền = trung vị 8 tuần trước",
        },
    }
    for group in ["customer", "external", "internal"]:
        if group in week_alerts.index:
            row = week_alerts.loc[group]
            facts["error_groups"][group] = {
                "rate": _fmt_pct(row["rate"]),
                "baseline_rate": _fmt_pct(row["baseline"]) if pd.notna(row["baseline"]) else "n/a",
                "z_score": f"{row['z']:.1f}" if pd.notna(row["z"]) else "n/a",
                "alert": bool(row["is_alert"]),
                "excess_errors": _fmt_int(row["excess_errors"]) if pd.notna(row["excess_errors"]) else "0",
            }
    return facts


NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*%?")
# Số nhỏ (đánh số thứ tự, "3 việc"...) không coi là số liệu
SMALL_NUMBERS = {str(i) for i in range(11)}


def numbers_in(text):
    return set(NUMBER_RE.findall(text))


def validate_numbers(brief, facts):
    """Trả về các con số trong bản tin KHÔNG có trong FACTS (rỗng = hợp lệ)."""
    allowed = numbers_in(json.dumps(facts, ensure_ascii=False)) | SMALL_NUMBERS
    used = numbers_in(json.dumps(brief, ensure_ascii=False))
    return sorted(n for n in used if n not in allowed and n.rstrip("%") not in allowed)


def facts_for(facts, department):
    """Số liệu chung + phần riêng của phòng ban (ban lãnh đạo nhận tóm tắt của tất cả)."""
    common = {k: v for k, v in facts.items() if k not in DEPARTMENTS}
    if department == "leadership":
        return {**common, **{k: facts[k] for k in DEPARTMENTS if k in facts}}
    return {**common, department: facts.get(department, {})}


def _alert_line(facts):
    ext = facts["error_groups"].get("external", {})
    if ext.get("alert"):
        return f"CẢNH BÁO: lỗi phía ngân hàng {ext['rate']} (mức nền {ext['baseline_rate']}, z = {ext['z_score']})."
    return "Không có cảnh báo bất thường về lỗi thanh toán tuần này."


def template_brief(facts, department):
    """Bản tin dự phòng không cần LLM - luôn chạy được, số liệu lấy thẳng từ FACTS."""
    common = [
        f"{facts['tickets']} lượt thanh toán, tỷ lệ thành công {facts['success_rate']} "
        f"(8 tuần trước: {facts['success_rate_prev_8_weeks']}).",
        _alert_line(facts),
    ]
    mk = facts.get("marketing", {})
    cs = facts.get("customer_care", {})
    pr = facts.get("product_it", {})
    fi = facts.get("finance", {})
    ld = facts.get("leadership", {})

    if department == "marketing":
        types = mk.get("campaign_types", {})
        worst, best = mk.get("worst_campaign_type"), mk.get("best_campaign_type")
        segs = mk.get("segments", {})
        headline = f"{facts['new_customers_lost_at_payment']} khách mới bị mất ngay ở bước thanh toán"
        points = [
            f"{facts['new_customers']} khách mới, {facts['new_customers_failed_first_payment']} người lỗi ngay lần thanh toán đầu.",
            f"Khuyến mãi chiếm {facts['promotion_share_of_success']} giao dịch thành công, chi phí giảm giá {facts['discount_spend']}.",
        ]
        if worst in types and best in types:
            points.append(
                f"Campaign '{worst}': {types[worst]['one_time_rate']} khách mới chỉ mua 1 lần, "
                f"tốn {types[worst]['discount_per_returned']} giảm giá cho mỗi khách quay lại; "
                f"'{best}' chỉ tốn {types[best]['discount_per_returned']}."
            )
        if segs:
            points.append("Phân nhóm khách: " + ", ".join(f"{k} {v}" for k, v in segs.items()) + ".")
        actions = [
            {"action": "Gửi coupon lần mua thứ hai (7–14 ngày) cho nhóm 'Khách mua một lần (mới)' có điểm quay lại cao",
             "owner": "Marketing", "kpi": "Khách mới mua lần 2 trong 90 ngày"},
            {"action": f"Giảm ngân sách '{worst}', chuyển sang '{best}' và theo dõi chi phí trên mỗi khách quay lại",
             "owner": "Marketing", "kpi": "Chi phí giảm giá / 1 khách KM quay lại"},
            {"action": "Gửi tin cứu đơn cho khách mới bị lỗi thanh toán lần đầu", "owner": "Marketing + CSKH",
             "kpi": "Tỷ lệ khách mới mua thành công trong 7 ngày"},
        ]
    elif department == "customer_care":
        headline = f"{facts['failed_tickets']} giao dịch lỗi cần liên hệ lại"
        points = [
            f"Lỗi phổ biến nhất: {facts['top_error']} ({facts['top_error_count']} lượt).",
            "Số lỗi theo mã: " + "; ".join(f"{k}: {v}" for k, v in cs.get("errors_by_code", {}).items()) + ".",
            "Danh sách cứu đơn kèm tin nhắn mẫu theo mã lỗi nằm trong file recovery_list.csv.",
        ]
        actions = [
            {"action": "Gửi tin nhắn mẫu theo mã lỗi cho toàn bộ danh sách cứu đơn", "owner": "CSKH",
             "kpi": "Tỷ lệ đơn lỗi được mua lại trong 7 ngày"},
            {"action": "Khi có cảnh báo lỗi ngân hàng: chủ động thông báo khách đổi sang Ví trong app", "owner": "CSKH",
             "kpi": "Số phàn nàn về lỗi thanh toán"},
        ]
    elif department == "product_it":
        top = pr.get("top_increases", [])
        headline = (
            f"{top[0]['error']} trên {top[0]['platform']} / {top[0]['paying_method']}: {top[0]['rate']} (nền {top[0]['baseline_rate']})"
            if top else f"Phương thức {facts['worst_payment_method']} lỗi {facts['worst_payment_method_failure_rate']}"
        )
        points = [
            f"{r['error']} · {r['platform']} · {r['paying_method']}: {r['rate']} so với {r['baseline_rate']} "
            f"(+{r['change_pp']} điểm %, vượt mức bình thường {r['excess_errors']} lỗi)."
            for r in top
        ] + [
            f"Theo phương thức: {facts['worst_payment_method']} {facts['worst_payment_method_failure_rate']} "
            f"vs {facts['best_payment_method']} {facts['best_payment_method_failure_rate']}.",
        ]
        actions = [
            {"action": "Làm việc với ngân hàng / cổng thanh toán về tổ hợp lỗi tăng mạnh nhất", "owner": "Product / IT",
             "kpi": "Tỷ lệ lỗi nhóm external theo tuần"},
            {"action": "Thiết kế retry flow: thanh toán lại, đổi phương thức, giữ vé tạm thời", "owner": "Product",
             "kpi": "Tỷ lệ hoàn tất thanh toán trên app"},
            {"action": "Gợi ý phương thức ít lỗi hơn ở checkout cho giao dịch rủi ro cao (A/B test)", "owner": "Product",
             "kpi": "Tỷ lệ thanh toán thành công"},
        ]
    elif department == "finance":
        headline = f"Giá trị giao dịch lỗi tuần này: {facts['failed_ticket_value']}"
        points = [f"{facts['failed_tickets']} giao dịch lỗi tuần này, chi phí giảm giá {facts['discount_spend']}."]
        if fi.get("unrecovered_month", "n/a") != "n/a":
            points.append(
                f"Tháng {fi['unrecovered_month']}: đơn lỗi trị giá {fi['failed_value']}, trong đó "
                f"{fi['unrecovered_failed_value']} ({fi['unrecovered_share']}) không được mua lại trong 7 ngày."
            )
        if fi.get("one_time_discount_month", "n/a") != "n/a":
            points.append(
                f"Tháng {fi['one_time_discount_month']}: chi {fi['discount_total']} giảm giá, "
                f"{fi['discount_one_time']} ({fi['one_time_discount_share']}) rơi vào khách không quay lại trong 90 ngày."
            )
        actions = [
            {"action": "Theo dõi giá trị đơn lỗi được cứu lại sau chiến dịch cứu đơn", "owner": "Tài chính",
             "kpi": "Giá trị đơn lỗi không được mua lại"},
            {"action": "Đặt trần ngân sách giảm giá theo chi phí trên mỗi khách quay lại", "owner": "Tài chính + Marketing",
             "kpi": "Tỷ trọng giảm giá cho khách chỉ mua 1 lần"},
        ]
    else:  # leadership
        month = ld.get("kpi_month", "n/a")
        headline = f"Tóm tắt tuần {facts['week_start']} · KPI tháng {month}"
        points = [
            f"{group}: " + "; ".join(f"{label} {v['value']} (tháng trước {v['previous_month']})" for label, v in items.items())
            for group, items in ld.get("kpis", {}).items()
        ]
        if mk.get("worst_campaign_type"):
            points.append(f"Campaign kém hiệu quả nhất về giữ chân: '{mk['worst_campaign_type']}'.")
        actions = [
            {"action": "Duyệt chiến dịch cứu đơn tự động cho mọi giao dịch lỗi", "owner": "Ban lãnh đạo",
             "kpi": "Tỷ lệ thanh toán thành công"},
            {"action": "Chuyển ngân sách khuyến mãi sang loại campaign giữ chân tốt hơn", "owner": "Ban lãnh đạo + Marketing",
             "kpi": "Khách mới mua lần 2 trong 90 ngày"},
        ]
    return {"headline": headline, "summary": " ".join(common), "key_points": common + points, "actions": actions}


def generate_brief(facts, department):
    """Trả về (brief, source). source = 'llm' | 'template (<lý do>)'."""
    scoped = facts_for(facts, department)
    prompt = (
        f"Phòng ban nhận bản tin: {DEPARTMENTS[department]}\n\n"
        f"FACTS (tuần {facts['week_start']} -> {facts['week_end']}):\n"
        f"{json.dumps(scoped, ensure_ascii=False, indent=2)}"
    )
    try:
        brief = generate_json(SYSTEM_PROMPT, prompt, BRIEF_SCHEMA)
    except LLMUnavailable as exc:
        return template_brief(scoped, department), f"template ({exc})"
    invalid = validate_numbers(brief, scoped)
    if invalid:
        return template_brief(scoped, department), f"template (LLM dùng số không có trong FACTS: {invalid})"
    return brief, "llm"


def to_markdown(brief, department, facts, source):
    lines = [
        f"# {DEPARTMENTS[department]} - tuần {facts['week_start']} → {facts['week_end']}",
        f"_Nguồn: {source}_",
        "",
        f"## {brief['headline']}",
        "",
        brief["summary"],
        "",
        "### Điểm chính",
        *[f"- {p}" for p in brief["key_points"]],
        "",
        "### Hành động đề xuất",
        "| Việc cần làm | Phụ trách | Chỉ số theo dõi |",
        "|---|---|---|",
        *[f"| {a['action']} | {a['owner']} | {a['kpi']} |" for a in brief["actions"]],
    ]
    return "\n".join(lines) + "\n"
