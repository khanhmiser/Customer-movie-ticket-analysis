"""Gửi báo cáo tuần tới từng phòng ban qua email: bản tin trong nội dung + file Excel riêng đính kèm.

Người nhận không cần chạy code - chỉ mở email.

Cấu hình (file .env hoặc GitHub Secrets):
    SMTP_HOST, SMTP_PORT (mặc định 587), SMTP_USER, SMTP_PASSWORD, EMAIL_FROM (mặc định = SMTP_USER)
    DASHBOARD_URL   (tùy chọn) link dashboard để người nhận bấm xem thêm
Danh sách người nhận: config/recipients.json (mẫu: config/recipients.example.json)
    hoặc biến môi trường RECIPIENTS_JSON cùng định dạng (dùng cho GitHub Actions)

Chưa cấu hình SMTP -> KHÔNG gửi, chỉ lưu email thành file .eml trong thư mục outbox/ để xem trước bằng Outlook.
"""

import html
import json
import mimetypes
import os
import smtplib
from email.message import EmailMessage

from src.briefs import DEPARTMENTS
from src.config import ROOT

RECIPIENTS_FILE = ROOT / "config" / "recipients.json"


def load_recipients(path=RECIPIENTS_FILE):
    """Ưu tiên biến môi trường RECIPIENTS_JSON (GitHub Secrets), sau đó tới file config/recipients.json."""
    if os.getenv("RECIPIENTS_JSON"):
        data = json.loads(os.environ["RECIPIENTS_JSON"])
    elif path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        return {}
    return {dept: emails for dept, emails in data.items() if dept in DEPARTMENTS and emails}


def smtp_settings():
    host, user, password = os.getenv("SMTP_HOST"), os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD")
    if not (host and user and password):
        return None
    return {"host": host, "port": int(os.getenv("SMTP_PORT") or 587), "user": user, "password": password,
            "sender": os.getenv("EMAIL_FROM") or user}


def _html_body(brief, facts, department, dashboard_url):
    e = html.escape
    ext = facts["error_groups"].get("external", {})
    banner = (
        f'<p style="background:#f8d7da;color:#842029;padding:10px 14px;border-radius:6px;font-weight:bold">'
        f'⚠ Cảnh báo lỗi phía ngân hàng tuần này: {e(ext["rate"])} (mức nền {e(ext["baseline_rate"])})</p>'
        if ext.get("alert") else ""
    )
    points = "".join(f"<li>{e(p)}</li>" for p in brief["key_points"])
    actions = "".join(
        f"<tr><td style='padding:6px;border-bottom:1px solid #ddd'>{e(a['action'])}</td>"
        f"<td style='padding:6px;border-bottom:1px solid #ddd'>{e(a['owner'])}</td>"
        f"<td style='padding:6px;border-bottom:1px solid #ddd'>{e(a['kpi'])}</td></tr>"
        for a in brief["actions"]
    )
    link = (f'<p><a href="{e(dashboard_url)}" style="background:#1f3a5f;color:#fff;padding:8px 14px;'
            f'border-radius:6px;text-decoration:none">Mở dashboard</a></p>' if dashboard_url else "")
    return f"""<div style="font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#1d2939;max-width:720px">
<p style="color:#667085;margin:0">Bản tin tuần {e(facts['week_start'])} → {e(facts['week_end'])} · {e(DEPARTMENTS[department])}</p>
<h2 style="color:#1f3a5f;margin:6px 0 12px">{e(brief['headline'])}</h2>
{banner}
<p>{e(brief['summary'])}</p>
<h3 style="color:#1f3a5f">Điểm chính</h3><ul>{points}</ul>
<h3 style="color:#1f3a5f">Hành động đề xuất</h3>
<table style="border-collapse:collapse;width:100%"><tr style="background:#1f3a5f;color:#fff">
<th style="padding:6px;text-align:left">Việc cần làm</th><th style="padding:6px;text-align:left">Phụ trách</th>
<th style="padding:6px;text-align:left">Chỉ số theo dõi</th></tr>{actions}</table>
<p>Chi tiết và danh sách đầy đủ trong file Excel đính kèm.</p>{link}
<p style="color:#98a2b3;font-size:12px">Email gửi tự động mỗi thứ Hai. Số liệu do hệ thống tính từ dữ liệu giao dịch; không trả lời email này.</p>
</div>"""


def _text_body(brief, facts, department, dashboard_url):
    lines = [f"Bản tin tuần {facts['week_start']} -> {facts['week_end']} - {DEPARTMENTS[department]}", "",
             brief["headline"], "", brief["summary"], "", "Điểm chính:"]
    lines += [f"- {p}" for p in brief["key_points"]]
    lines += ["", "Hành động đề xuất:"] + [f"- {a['action']} ({a['owner']}; theo dõi: {a['kpi']})" for a in brief["actions"]]
    if dashboard_url:
        lines += ["", f"Dashboard: {dashboard_url}"]
    return "\n".join(lines)


def build_message(department, brief, facts, attachment, recipients, sender, dashboard_url=None):
    msg = EmailMessage()
    alert = "⚠ " if facts["error_groups"].get("external", {}).get("alert") else ""
    msg["Subject"] = f"{alert}[Báo cáo tuần {facts['week_start']}] {DEPARTMENTS[department]}: {brief['headline']}"
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(_text_body(brief, facts, department, dashboard_url))
    msg.add_alternative(_html_body(brief, facts, department, dashboard_url), subtype="html")
    ctype = mimetypes.guess_type(attachment.name)[0] or "application/octet-stream"
    maintype, subtype = ctype.split("/", 1)
    msg.add_attachment(attachment.read_bytes(), maintype=maintype, subtype=subtype, filename=attachment.name)
    return msg


def deliver(out_dir, facts, generated, attachments, recipients=None, settings=None):
    """generated: {dept: (brief, source)}; attachments: {dept: Path tới file Excel của phòng đó}.

    Trả về list kết quả: [{department, to, status}] với status = sent | saved_to_outbox | no_recipients.
    """
    recipients = load_recipients() if recipients is None else recipients
    settings = smtp_settings() if settings is None else settings
    dashboard_url = os.getenv("DASHBOARD_URL")
    sender = settings["sender"] if settings else "bao-cao-tu-dong@example.com"
    outbox = out_dir / "outbox"
    results, ready = [], []
    for dept, (brief, _) in generated.items():
        # Chưa có danh sách người nhận vẫn tạo bản xem trước (gửi tới địa chỉ mẫu) để duyệt nội dung
        to = recipients.get(dept) or [f"{dept}@example.com"]
        msg = build_message(dept, brief, facts, attachments[dept], to, sender, dashboard_url)
        if settings and dept in recipients:
            ready.append((dept, to, msg))
        else:
            outbox.mkdir(parents=True, exist_ok=True)
            (outbox / f"{dept}.eml").write_bytes(bytes(msg))
            # có SMTP mà phòng này chưa có người nhận -> báo rõ để bổ sung config/recipients.json
            status = "no_recipients" if settings else "saved_to_outbox"
            results.append({"department": dept, "to": to, "status": status})
    if ready:
        with smtplib.SMTP(settings["host"], settings["port"], timeout=30) as smtp:
            smtp.starttls()
            smtp.login(settings["user"], settings["password"])
            for dept, to, msg in ready:
                smtp.send_message(msg)
                results.append({"department": dept, "to": to, "status": "sent"})
    return results
