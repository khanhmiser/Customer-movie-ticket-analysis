"""Nạp dữ liệu theo ngày vào kho (parquet), có kiểm tra chất lượng.

Hệ thống nguồn đổ file vào data/incoming/:
    ticket_history_YYYY-MM-DD.csv    giao dịch của 1 ngày
    customer_YYYY-MM-DD.csv          khách mới / khách cập nhật thông tin trong ngày   (tùy chọn)
    campaign_YYYY-MM-DD.csv          campaign mới                                      (tùy chọn)
    device_detail_YYYY-MM-DD.csv     thiết bị mới                                      (tùy chọn)
    status_detail_YYYY-MM-DD.csv     mã trạng thái / mã lỗi mới                        (tùy chọn)
    ticket_history_<tên bất kỳ>.csv  file xuất nhiều ngày -> tự tách thành file theo ngày

Thứ tự xử lý: theo ngày; trong cùng 1 ngày, bảng tham chiếu được cập nhật TRƯỚC rồi mới kiểm tra giao dịch
(khách đăng ký và mua vé cùng ngày vẫn qua được). File nạp xong chuyển sang data/archive/.

    python -m src.ingest simulate                 # chia ticket_history.csv thành file theo ngày
    python -m src.ingest run --until 2022-03-06   # nạp các file MỚI tới ngày này
    python -m src.ingest inject-bad               # tạo 1 file lỗi để thử cơ chế dừng
    python -m src.ingest status                   # đã nạp tới đâu
"""

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from src import notify, quality
from src.config import DATA_DIR, REPORTS_DIR

TICKETS = "ticket_history"
REFERENCE_TABLES = list(quality.REFERENCE_SPECS)
FILE_PREFIX = f"{TICKETS}_"
NAME_RE = re.compile(rf"^({'|'.join([TICKETS] + REFERENCE_TABLES)})_(\d{{4}}-\d{{2}}-\d{{2}})(__.+)?\.csv$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class Paths:
    """Cho phép notebook/test dùng thư mục riêng mà không đụng vào kho chính."""
    root: Path = DATA_DIR
    reports: Path = REPORTS_DIR

    @property
    def incoming(self):
        return self.root / "incoming"

    @property
    def warehouse(self):
        return self.root / "warehouse" / TICKETS

    @property
    def refs(self):
        return self.root / "warehouse" / "refs"

    @property
    def archive(self):
        return self.root / "archive"

    @property
    def quarantine(self):
        return self.root / "quarantine"

    @property
    def state_file(self):
        return self.root / "warehouse" / "_state.json"

    @property
    def dq_dir(self):
        return self.reports / "data_quality"

    @property
    def daily_ops(self):
        return self.reports / "daily" / "daily_ops.csv"


def parse_name(path):
    """(bảng, ngày) từ tên file, hoặc None nếu tên không đúng quy ước."""
    m = NAME_RE.match(path.name)
    return (m.group(1), m.group(2)) if m else None


def file_date(path):
    parsed = parse_name(path)
    return parsed[1] if parsed else path.stem.removeprefix(FILE_PREFIX)


def load_refs(paths=None):
    """Bảng tham chiếu hiện hành: bản đã cập nhật trong kho nếu có, nếu không thì file gốc."""
    refs = {}
    for name in REFERENCE_TABLES:
        updated = paths.refs / f"{name}.parquet" if paths else None
        refs[name] = pd.read_parquet(updated) if updated and updated.exists() else pd.read_csv(DATA_DIR / f"{name}.csv")
    return refs


def read_state(paths):
    if not paths.state_file.exists():
        return {"loaded": {}, "failed": {}}
    state = json.loads(paths.state_file.read_text(encoding="utf-8"))
    # Định dạng cũ: key = ngày -> chuyển sang key = tên file
    for section in ["loaded", "failed"]:
        converted = {}
        for key, value in state.get(section, {}).items():
            if DATE_RE.match(key) and "file" in value:
                converted[value["file"]] = {"kind": TICKETS, "date": key, **{k: v for k, v in value.items() if k != "file"}}
            else:
                converted[key] = value
        state[section] = converted
    return state


def write_state(paths, state):
    paths.state_file.parent.mkdir(parents=True, exist_ok=True)
    paths.state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def loaded_ticket_dates(state):
    return sorted(v["date"] for v in state["loaded"].values() if v.get("kind") == TICKETS)


def simulate_drops(paths=Paths(), source=DATA_DIR / "ticket_history.csv"):
    """Chia file lịch sử thành 1 file/ngày trong incoming/ (giữ nguyên dữ liệu gốc, kể cả dòng trùng)."""
    paths.incoming.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(source)
    day = pd.to_datetime(raw["time"]).dt.date
    for d, rows in raw.groupby(day):
        rows.to_csv(paths.incoming / f"{FILE_PREFIX}{d}.csv", index=False)
    return day.nunique()


def _find_loaded_file(paths, date):
    for folder in [paths.incoming, paths.archive]:
        candidate = folder / f"{FILE_PREFIX}{date}.csv"
        if candidate.exists():
            return pd.read_csv(candidate)
    return pd.read_parquet(paths.warehouse / f"{date}.parquet")


def inject_bad_file(paths=Paths(), date=None):
    """Tạo file của ngày kế tiếp với 4 loại lỗi thường gặp - để chứng minh pipeline dừng đúng lúc."""
    pending = [file_date(f) for f in paths.incoming.glob(f"{FILE_PREFIX}*.csv")]
    last = max(pending + loaded_ticket_dates(read_state(paths)))
    date = pd.Timestamp(date) if date else pd.Timestamp(last) + pd.Timedelta(days=1)
    bad = _find_loaded_file(paths, last).head(50).copy()
    bad["ticket_id"] = [f"bad{date:%Y%m%d}{i:04d}" for i in range(len(bad))]
    bad["time"] = pd.to_datetime(bad["time"]).apply(lambda t: t.replace(year=date.year, month=date.month, day=date.day)).astype(str)
    bad.loc[0:2, "status_id"] = 99                                     # mã trạng thái chưa có trong bảng status
    bad.loc[3:4, "customer_id"] = None                                 # thiếu khóa
    bad.loc[5, "final_price"] = bad.loc[5, "original_price"] + 5       # giá sai công thức
    bad.loc[6, "ticket_id"] = bad.loc[7, "ticket_id"]                  # trùng ticket_id, khác nội dung
    path = paths.incoming / f"{FILE_PREFIX}{date.date()}.csv"
    bad.to_csv(path, index=False)
    return path


def split_exports(paths):
    """File giao dịch nhiều ngày (tên không theo ngày) -> tách thành file theo ngày, file gốc chuyển sang archive.

    Tên file con: ticket_history_<ngày>__<tên file gốc>.csv để không trùng với file ngày gửi riêng.
    Không đọc được thời gian của dòng nào -> không tách được -> cách ly cả file.
    """
    out = {"split": [], "unsplittable": []}
    for path in sorted(paths.incoming.glob(f"{FILE_PREFIX}*.csv")):
        if parse_name(path):
            continue
        raw = pd.read_csv(path)
        day = pd.to_datetime(raw["time"], errors="coerce", format="ISO8601") if "time" in raw else None
        if day is None or day.isna().any():
            paths.quarantine.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), paths.quarantine / path.name)
            out["unsplittable"].append(path.name)
            continue
        for d, rows in raw.groupby(day.dt.date):
            rows.to_csv(paths.incoming / f"{FILE_PREFIX}{d}__{path.stem}.csv", index=False)
        (paths.archive / "exports").mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), paths.archive / "exports" / path.name)
        out["split"].append({"file": path.name, "days": int(day.dt.date.nunique())})
    return out


def _log_quality(paths, kind, date, path, n_rows, results, summary):
    paths.dq_dir.mkdir(parents=True, exist_ok=True)
    report = {"date": date, "table": kind, "file": path.name, "rows": n_rows, **summary, "checks": results,
              "checked_at": datetime.now().isoformat(timespec="seconds")}
    (paths.dq_dir / f"{path.stem}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    row = pd.DataFrame([{
        "date": date, "file": path.name, "rows": n_rows, "status": summary["status"],
        "errors": ";".join(summary["errors"]), "warnings": ";".join(summary["warnings"]),
        "checked_at": report["checked_at"],
    }])
    log = paths.dq_dir / "dq_log.csv"
    row.to_csv(log, mode="a", header=not log.exists(), index=False, encoding="utf-8")


def _log_daily_ops(paths, date, batch, refs):
    status = batch.merge(refs["status_detail"], on="status_id", how="left")
    groups = status.loc[status["status_id"] != 1, "error_group"].value_counts()
    row = pd.DataFrame([{
        "date": date, "tickets": len(batch), "success": int((batch["status_id"] == 1).sum()),
        "success_rate": round(float((batch["status_id"] == 1).mean()), 4),
        "revenue": round(float(batch.loc[batch["status_id"] == 1, "final_price"].sum()), 2),
        **{f"errors_{g}": int(groups.get(g, 0)) for g in ["customer", "external", "internal"]},
    }])
    paths.daily_ops.parent.mkdir(parents=True, exist_ok=True)
    row.to_csv(paths.daily_ops, mode="a", header=not paths.daily_ops.exists(), index=False, encoding="utf-8")


def loaded_ticket_ids(paths):
    if not paths.warehouse.exists() or not any(paths.warehouse.glob("*.parquet")):
        return set()
    return set(pd.read_parquet(paths.warehouse, columns=["ticket_id"])["ticket_id"])


def _quarantine(paths, path, state, kind, date, errors):
    paths.quarantine.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), paths.quarantine / path.name)
    state["failed"][path.name] = {"kind": kind, "date": date, "errors": errors}


def run(paths=Paths(), until=None, send_alert=False):
    """Nạp lần lượt các file chưa nạp. Gặp lỗi 'error' -> cách ly file đó và DỪNG.

    Trả về dict: loaded (số file giao dịch), rows, reference_updates, failed (tên file lỗi hoặc None), warnings...
    """
    out = {"loaded": 0, "rows": 0, "reference_updates": {}, "failed": None, "failed_checks": [], "warnings": {},
           "split_exports": [], "unrecognized_files": []}
    paths.incoming.mkdir(parents=True, exist_ok=True)
    split = split_exports(paths)
    out["split_exports"] = split["split"]
    if split["unsplittable"]:
        out.update(failed=split["unsplittable"][0], failed_checks=["cannot_split_export"])
        return out

    state = read_state(paths)
    refs = load_refs(paths)
    pending = []
    for path in paths.incoming.glob("*.csv"):
        parsed = parse_name(path)
        if not parsed:
            out["unrecognized_files"].append(path.name)
            continue
        kind, date = parsed
        if until and date > str(pd.Timestamp(until).date()):
            continue
        pending.append((date, 1 if kind == TICKETS else 0, path.name, kind, path))  # tham chiếu trước
    pending.sort()

    ids = loaded_ticket_ids(paths)
    recent = [v["rows"] for v in sorted(state["loaded"].values(), key=lambda v: v["date"]) if v.get("kind") == TICKETS]
    paths.warehouse.mkdir(parents=True, exist_ok=True)
    paths.refs.mkdir(parents=True, exist_ok=True)
    (paths.archive / "incoming").mkdir(parents=True, exist_ok=True)

    for date, _, name, kind, path in pending:
        size = path.stat().st_size
        if name in state["loaded"]:
            # Cùng tên đã nạp: cùng nội dung (hoặc kho cũ chưa ghi size) -> chỉ dọn vào archive;
            # khác nội dung = nguồn gửi lại bản sửa của ngày đã nạp -> cần người kiểm tra, không tự ghi đè
            if state["loaded"][name].get("size") in (None, size):
                shutil.move(str(path), paths.archive / "incoming" / name)
                continue
            _quarantine(paths, path, state, kind, date, ["file_resent_with_different_content"])
            write_state(paths, state)
            out.update(failed=name, failed_checks=["file_resent_with_different_content"])
            break

        raw = pd.read_csv(path)
        if kind == TICKETS:
            batch, results = quality.check_batch(raw, refs, ids, expected_date=date, recent_daily_rows=recent)
        else:
            batch, results = quality.check_reference(kind, raw, refs[kind])
        summary = quality.summarize(results)
        _log_quality(paths, kind, date, path, len(raw), results, summary)

        if summary["status"] == "failed":
            _quarantine(paths, path, state, kind, date, summary["errors"])
            write_state(paths, state)
            out.update(failed=name, failed_checks=summary["errors"])
            if send_alert:
                notify.send_telegram(f"⛔ File {name} KHÔNG đạt kiểm tra chất lượng: {summary['errors']}. "
                                     f"Đã cách ly file, chưa chạy báo cáo.")
            break

        if kind == TICKETS:
            batch.to_parquet(paths.warehouse / f"{path.stem.removeprefix(FILE_PREFIX)}.parquet", index=False)
            ids.update(batch["ticket_id"])
            recent.append(len(batch))
            _log_daily_ops(paths, date, batch, refs)
            out["loaded"] += 1
            out["rows"] += len(batch)
        else:
            key = quality.REFERENCE_SPECS[kind]["key"]
            current = refs[kind]
            refs[kind] = pd.concat([current[~current[key].isin(batch[key])], batch], ignore_index=True)
            refs[kind].to_parquet(paths.refs / f"{kind}.parquet", index=False)
            out["reference_updates"][kind] = out["reference_updates"].get(kind, 0) + len(batch)
        state["loaded"][name] = {"kind": kind, "date": date, "rows": len(batch), "size": size,
                                 "warnings": summary["warnings"]}
        # File cùng bảng + cùng ngày đã nạp thành công (vd. bản sửa "__fixed") -> lỗi cũ coi như đã xử lý
        for failed_name in [n for n, v in state["failed"].items() if v.get("kind") == kind and v.get("date") == date]:
            state["failed"].pop(failed_name)
        if summary["warnings"]:
            out["warnings"][name] = summary["warnings"]
        shutil.move(str(path), paths.archive / "incoming" / name)
        write_state(paths, state)

    write_state(paths, state)  # cũng lưu luôn trạng thái đã chuyển từ định dạng cũ
    dates = loaded_ticket_dates(state)
    out["last_loaded_date"] = dates[-1] if dates else None
    return out


def read_warehouse(paths=Paths()):
    return pd.read_parquet(paths.warehouse)


def reset(paths):
    """Xóa kho + log của `paths` (dùng cho demo/notebook với thư mục riêng)."""
    for p in [paths.incoming, paths.warehouse.parent, paths.archive, paths.quarantine, paths.dq_dir, paths.daily_ops.parent]:
        shutil.rmtree(p, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("simulate")
    run_p = sub.add_parser("run")
    run_p.add_argument("--until", help="Chỉ nạp tới ngày này (YYYY-MM-DD)")
    run_p.add_argument("--notify", action="store_true")
    bad_p = sub.add_parser("inject-bad")
    bad_p.add_argument("--date")
    sub.add_parser("status")
    args = parser.parse_args()

    paths = Paths()
    if args.cmd == "simulate":
        print(f"Đã tạo {simulate_drops(paths)} file theo ngày trong {paths.incoming}")
    elif args.cmd == "inject-bad":
        print(f"Đã tạo file lỗi: {inject_bad_file(paths, args.date)}")
    elif args.cmd == "status":
        state = read_state(paths)
        dates = loaded_ticket_dates(state)
        refs = {k: sum(1 for v in state["loaded"].values() if v.get("kind") == k) for k in REFERENCE_TABLES}
        print(json.dumps({"loaded_ticket_files": len(dates), "last_loaded_date": dates[-1] if dates else None,
                          "reference_update_files": refs,
                          "pending_files": len(list(paths.incoming.glob("*.csv"))) if paths.incoming.exists() else 0,
                          "failed": state["failed"]}, ensure_ascii=False, indent=2))
    else:
        result = run(paths, args.until, send_alert=args.notify)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["failed"]:
            sys.exit(1)


if __name__ == "__main__":
    main()
