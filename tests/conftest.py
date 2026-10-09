import os
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["LLM_MODE"] = "off"  # test không bao giờ gọi API tốn phí
os.environ["GEMINI_MODE"] = "off"  # kể cả Gemini (RAG + Text-to-SQL)
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")

from src import ingest  # noqa: E402
from src.data_prep import load_tickets  # noqa: E402


@pytest.fixture(scope="session")
def raw_tickets():
    return pd.read_csv(ROOT / "data" / "ticket_history.csv")


@pytest.fixture(scope="session")
def refs():
    return ingest.load_refs()


@pytest.fixture(scope="session")
def tickets():
    return load_tickets()


@pytest.fixture
def one_day(raw_tickets):
    """Giao dịch thật của 1 ngày (sạch)."""
    day = pd.to_datetime(raw_tickets["time"]).dt.date.astype(str)
    return raw_tickets[day == "2022-03-05"].reset_index(drop=True).copy()


@pytest.fixture
def paths(tmp_path):
    p = ingest.Paths(root=tmp_path / "data", reports=tmp_path / "reports")
    p.incoming.mkdir(parents=True)
    return p


def make_day(template, date, prefix="t"):
    """Copy giao dịch mẫu sang ngày khác với ticket_id mới."""
    d = template.copy()
    d["ticket_id"] = [f"{prefix}{date.replace('-', '')}{i:05d}" for i in range(len(d))]
    d["time"] = date + pd.to_datetime(d["time"]).dt.strftime(" %H:%M:%S.%f").str[:-3]
    return d
