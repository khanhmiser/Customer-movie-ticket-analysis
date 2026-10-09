"""Luồng nạp dữ liệu theo ngày: chỉ nạp file mới, dừng khi lỗi, xử lý được dữ liệu mới ngoài đời."""

import json

import pandas as pd

from src import ingest
from tests.conftest import make_day


def write(paths, name, df):
    df.to_csv(paths.incoming / name, index=False)


def test_loads_only_new_files(paths, one_day):
    for date in ["2023-01-01", "2023-01-02"]:
        write(paths, f"ticket_history_{date}.csv", make_day(one_day, date))
    first = ingest.run(paths)
    assert first["loaded"] == 2 and first["failed"] is None
    assert not list(paths.incoming.glob("*.csv"))                   # đã chuyển sang archive
    assert ingest.run(paths)["loaded"] == 0                           # chạy lại không nạp trùng
    assert len(ingest.read_warehouse(paths)) == 2 * len(one_day)


def test_bad_file_is_quarantined_and_stops(paths, one_day):
    write(paths, "ticket_history_2023-01-01.csv", make_day(one_day, "2023-01-01").assign(status_id=99))
    write(paths, "ticket_history_2023-01-02.csv", make_day(one_day, "2023-01-02"))
    result = ingest.run(paths)
    assert result["failed"] == "ticket_history_2023-01-01.csv" and "unknown_status" in result["failed_checks"]
    assert (paths.quarantine / "ticket_history_2023-01-01.csv").exists()
    assert (paths.incoming / "ticket_history_2023-01-02.csv").exists()  # ngày sau chưa được nạp


def test_new_customers_need_customer_file(paths, one_day):
    day = make_day(one_day, "2023-01-03")
    day.loc[0, "customer_id"] = 900001
    write(paths, "ticket_history_2023-01-03.csv", day)
    assert ingest.run(paths)["failed_checks"] == ["unknown_customer"]

    write(paths, "customer_2023-01-03.csv",
          pd.DataFrame({"customer_id": [900001], "usergender": ["Female"], "dob": ["2001-04-12"]}))
    (paths.quarantine / "ticket_history_2023-01-03.csv").rename(paths.incoming / "ticket_history_2023-01-03.csv")
    result = ingest.run(paths)
    assert result["failed"] is None and result["reference_updates"] == {"customer": 1}
    assert 900001 in set(ingest.load_refs(paths)["customer"]["customer_id"])
    assert ingest.read_state(paths)["failed"] == {}


def test_multi_day_export_is_split(paths, one_day):
    export = pd.concat([make_day(one_day.head(20), d, prefix=f"e{i}") for i, d in enumerate(["2023-01-05", "2023-01-06"])])
    write(paths, "ticket_history_export_jan.csv", export)
    result = ingest.run(paths)
    assert result["loaded"] == 2 and result["split_exports"] == [{"file": "ticket_history_export_jan.csv", "days": 2}]


def test_resent_file_with_different_content_is_blocked(paths, one_day):
    write(paths, "ticket_history_2023-01-07.csv", make_day(one_day, "2023-01-07"))
    ingest.run(paths)
    write(paths, "ticket_history_2023-01-07.csv", make_day(one_day.head(5), "2023-01-07", prefix="x"))
    assert ingest.run(paths)["failed_checks"] == ["file_resent_with_different_content"]


def test_old_state_format_is_migrated(paths):
    paths.state_file.parent.mkdir(parents=True)
    paths.state_file.write_text(json.dumps({
        "loaded": {"2022-01-01": {"file": "ticket_history_2022-01-01.csv", "rows": 10, "warnings": []}},
        "failed": {}}), encoding="utf-8")
    state = ingest.read_state(paths)
    assert state["loaded"]["ticket_history_2022-01-01.csv"]["date"] == "2022-01-01"
    assert ingest.loaded_ticket_dates(state) == ["2022-01-01"]
