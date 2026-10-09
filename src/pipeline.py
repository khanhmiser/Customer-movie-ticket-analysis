"""Pipeline chạy mỗi tuần: dữ liệu -> cảnh báo bất thường -> bản tin + file dữ liệu cho 5 phòng ban.

Chạy:  python -m src.pipeline                      (tuần đầy đủ gần nhất trong dữ liệu)
       python -m src.pipeline --week 2022-02-28    (chạy lại 1 tuần trong quá khứ - backtest)
       python -m src.pipeline --no-llm             (chỉ dùng template, không gọi API)
       python -m src.pipeline --ingest             (nạp file ngày mới + kiểm tra chất lượng trước, lỗi -> dừng)
       python -m src.pipeline --send-email         (gửi email + file Excel riêng cho từng phòng ban)
"""

import argparse
import json
import os
import shutil
import sys

import pandas as pd

from src import anomaly, briefs, deliver, departments, excel_report, ingest, metrics, notify
from src.data_prep import load_tickets

# Marketing nhận top khách theo điểm quay lại (toàn bộ danh sách có thể > 100k khách)
TARGET_LIST_SIZE = 5000


def latest_full_week(df):
    last = df["time"].max()
    week = df["week"].max()
    # Tuần cuối chưa đủ 7 ngày thì lấy tuần trước đó
    return week if last >= week + pd.Timedelta(days=6, hours=23) else week - pd.Timedelta(weeks=1)


def recovery_list(df, week_start):
    """Giao dịch lỗi trong tuần mà khách CHƯA mua lại thành công tính tới cuối tuần."""
    week = df[df["week"] == week_start]
    failed = week[week["is_failed"]]
    later_success = week[week["is_success"]].groupby("customer_id")["time"].max()
    still_lost = failed[~(failed["customer_id"].map(later_success) > failed["time"])]
    out = still_lost[["ticket_id", "customer_id", "time", "paying_method", "status_id", "description"]].copy()
    out["message"] = out["status_id"].map(briefs.RECOVERY_MESSAGES)
    return out.drop_duplicates("customer_id", keep="last")


class DataQualityError(RuntimeError):
    pass


def run(week_start=None, send=False, source="csv", ingest_first=False, paths=None, send_email=False):
    """source="warehouse" đọc kho nạp theo ngày; ingest_first=True nạp file mới trước (lỗi -> DataQualityError)."""
    paths = paths or ingest.Paths()
    dq_log = None
    if ingest_first:
        result = ingest.run(paths, send_alert=send)
        if result["failed"]:
            raise DataQualityError(
                f"File {result['failed']} không đạt kiểm tra chất lượng {result['failed_checks']} - "
                f"đã cách ly vào {paths.quarantine}, KHÔNG chạy báo cáo.")
        source = "warehouse"
    if source == "warehouse":
        df = load_tickets(source="warehouse", warehouse_dir=paths.warehouse)
        log_file = paths.dq_dir / "dq_log.csv"
        dq_log = pd.read_csv(log_file) if log_file.exists() else None
    else:
        df = load_tickets()
    weekly = metrics.weekly_error_rates(df)
    alerts = anomaly.detect(weekly)
    week_start = pd.Timestamp(week_start) if week_start else latest_full_week(df)

    out_dir = paths.reports / "weekly" / str(week_start.date())
    out_dir.mkdir(parents=True, exist_ok=True)

    facts = briefs.weekly_facts(df, alerts, week_start)
    extra, tables = departments.build(df, week_start)
    facts.update(extra)
    generated = {}
    for dept in briefs.DEPARTMENTS:
        brief, brief_source = briefs.generate_brief(facts, dept)
        generated[dept] = (brief, brief_source)
        (out_dir / f"brief_{dept}.md").write_text(briefs.to_markdown(brief, dept, facts, brief_source), encoding="utf-8")
    sources = {dept: src for dept, (_, src) in generated.items()}

    def save(table, name, index=False):
        table.to_csv(out_dir / name, index=index, encoding="utf-8-sig")

    recovery = recovery_list(df, week_start)
    save(recovery, "recovery_list.csv")                                          # CSKH
    save(tables["marketing_targets"].head(TARGET_LIST_SIZE), "marketing_targets.csv", index=True)  # Marketing
    save(tables["campaign_effectiveness"], "campaign_effectiveness.csv", index=True)
    save(tables["campaign_ids"], "campaign_ids_effectiveness.csv", index=True)
    save(tables["product_breakdown"], "product_breakdown.csv")                   # Product / IT
    save(tables["monthly_losses"], "finance_monthly_losses.csv", index=True)     # Tài chính
    save(tables["kpis"], "kpis_monthly.csv", index=True)                         # Ban lãnh đạo
    excel_path = excel_report.build(out_dir / f"weekly_report_{week_start.date()}.xlsx",
                                    facts, generated, tables, recovery, alerts, dq_log)
    # Bản mới nhất luôn ở cùng 1 chỗ, tên dễ nhận ra -> người dùng không phải tìm theo ngày
    latest_copy = paths.reports / "BAO_CAO_MOI_NHAT.xlsx"
    try:
        shutil.copyfile(excel_path, latest_copy)
        latest_note = str(latest_copy)
    except PermissionError:
        # Windows khóa file khi đang mở trong Excel -> không làm hỏng cả lần chạy, báo cáo tuần vẫn có trong out_dir
        latest_note = f"KHÔNG cập nhật được {latest_copy.name} (file đang mở trong Excel) - dùng {excel_path}"
        print(f"⚠ {latest_note}")

    deliveries = []
    if send_email:
        # Ban lãnh đạo nhận đủ file; các phòng khác nhận file chỉ có Tóm tắt + sheet của mình
        per_dept = out_dir / "by_department"
        per_dept.mkdir(exist_ok=True)
        attachments = {"leadership": excel_path}
        for dept in briefs.DEPARTMENTS:
            if dept != "leadership":
                attachments[dept] = excel_report.build(
                    per_dept / f"weekly_report_{week_start.date()}_{dept}.xlsx",
                    facts, generated, tables, recovery, alerts, dq_log, departments=[dept])
        deliveries = deliver.deliver(out_dir, facts, generated, attachments)

    week_alerts = alerts[(alerts["week"] == week_start) & alerts["is_alert"]]
    summary = {
        "week_start": facts["week_start"],
        "alerts": week_alerts[["error_group", "rate", "baseline", "z"]].round(4).to_dict("records"),
        "recovery_list_size": int(len(recovery)),
        "brief_sources": sources,
        "excel_report": excel_path.name,
        "latest_report": latest_note,
        "data_source": source,
        "deliveries": deliveries,
        "facts": facts,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    if send:
        alert_text = ", ".join(f"{a['error_group']} {a['rate']:.1%}" for a in summary["alerts"]) or "không có"
        notify.send_telegram(
            f"Bản tin tuần {facts['week_start']}\n"
            f"Tỷ lệ thành công: {facts['success_rate']}\n"
            f"Cảnh báo: {alert_text}\n"
            f"Khách mới mất ở bước thanh toán: {facts['new_customers_lost_at_payment']}\n"
            f"Danh sách cứu đơn: {len(recovery)} khách"
        )
    return out_dir, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--week", help="Ngày thứ Hai đầu tuần, dạng YYYY-MM-DD")
    parser.add_argument("--no-llm", action="store_true", help="Chỉ dùng bản tin template")
    parser.add_argument("--notify", action="store_true", help="Gửi tóm tắt qua Telegram")
    parser.add_argument("--source", choices=["csv", "warehouse"], default="csv",
                        help="csv = file lịch sử gốc; warehouse = kho nạp theo ngày (src/ingest.py)")
    parser.add_argument("--ingest", action="store_true", help="Nạp file ngày mới (có kiểm tra chất lượng) trước khi chạy")
    parser.add_argument("--send-email", action="store_true",
                        help="Gửi email cho từng phòng ban (chưa cấu hình SMTP -> lưu .eml vào outbox/ để xem trước)")
    args = parser.parse_args()
    if args.no_llm:
        os.environ["LLM_MODE"] = "off"
    try:
        out_dir, summary = run(args.week, send=args.notify, source=args.source, ingest_first=args.ingest,
                               send_email=args.send_email)
    except DataQualityError as exc:
        print(f"⛔ {exc}")
        sys.exit(1)
    print(f"Đã ghi báo cáo vào {out_dir}")
    print(json.dumps({k: summary[k] for k in ["week_start", "data_source", "alerts", "recovery_list_size",
                                              "brief_sources", "excel_report", "deliveries"]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
