"""Hỏi dữ liệu bằng tiếng Việt -> Gemini sinh SQL -> chạy trên SQLite chỉ-đọc.

Có bộ câu hỏi đánh giá (eval/ask_data_eval.json) với đáp án SQL chuẩn để đo độ chính xác.
"""

import json
import re
import sqlite3

import pandas as pd

from src.config import EVAL_DIR
from src import gemini
from src.llm import LLMUnavailable

TABLE_COLUMNS = [
    "ticket_id", "customer_id", "time", "year", "year_month", "hour", "day_name",
    "paying_method", "platform", "os_version", "theater_name", "movie_name",
    "original_price", "discount_value", "final_price", "campaign_type", "type",
    "status_id", "description", "error_group", "is_success", "usergender", "age", "age_generation",
]

SCHEMA_DOC = """Bảng duy nhất: tickets (mỗi dòng = 1 lần thanh toán, thành công hoặc lỗi), dữ liệu 2019-2022.
- ticket_id TEXT, customer_id INTEGER
- time TEXT 'YYYY-MM-DD HH:MM:SS', year INTEGER, year_month TEXT 'YYYY-MM', hour INTEGER 0-23,
  day_name TEXT ('Monday'..'Sunday')
- paying_method TEXT: 'money in app' | 'bank account' | 'credit card' | 'debit card' | 'other'
- platform TEXT: 'mobile' | 'website' | 'Unknown'
- os_version TEXT: 'ios' | 'android and other' | 'browser' | 'Unknown'
- theater_name REAL (mã rạp), movie_name TEXT
- original_price, discount_value, final_price REAL (final_price = original_price - discount_value)
- campaign_type TEXT: 'direct discount' | 'voucher' | 'reward point' | 'none'
- type TEXT: 'promotion' | 'non-promotion'
- status_id INTEGER: 1 = thành công; -1..-7 = các mã lỗi
- description TEXT: mô tả trạng thái/lỗi, error_group TEXT: 'customer' | 'external' | 'internal' | 'none'
- is_success INTEGER 0/1
- usergender TEXT: 'Male' | 'Female' | 'Not verify', age INTEGER, age_generation TEXT
Doanh thu = SUM(final_price) của giao dịch thành công (is_success = 1)."""

SQL_SCHEMA = {
    "type": "object",
    "properties": {"sql": {"type": "string"}, "explanation": {"type": "string"}},
    "required": ["sql", "explanation"],
}

SYSTEM_PROMPT = f"""Bạn chuyển câu hỏi tiếng Việt của quản lý thành MỘT câu lệnh SQLite SELECT.
{SCHEMA_DOC}

Quy tắc: chỉ SELECT (có thể dùng WITH), một câu lệnh, không sửa dữ liệu.
Tỷ lệ trả về dạng số thập phân 0-1. explanation: 1 câu tiếng Việt giải thích cách tính."""

FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|create|attach|pragma|replace)\b", re.I)


def build_connection(df):
    conn = sqlite3.connect(":memory:")
    table = df[TABLE_COLUMNS].copy()
    table["time"] = table["time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    table["is_success"] = table["is_success"].astype(int)
    table.to_sql("tickets", conn, index=False)
    conn.execute("PRAGMA query_only = ON")
    return conn


def check_sql(sql):
    # LLM đôi khi bọc SQL trong khối ```sql ... ``` -> bỏ trước khi kiểm tra
    stripped = re.sub(r"^```(?:sql)?\s*|\s*```$", "", sql.strip(), flags=re.I).strip().rstrip(";").strip()
    if ";" in stripped:
        raise ValueError("Chỉ cho phép một câu lệnh")
    if not re.match(r"^(select|with)\b", stripped, re.I):
        raise ValueError("Chỉ cho phép câu lệnh SELECT")
    if FORBIDDEN.search(stripped):
        raise ValueError("Câu lệnh chứa từ khóa không được phép")
    return stripped


def run_sql(conn, sql, max_rows=1000):
    return pd.read_sql_query(f"SELECT * FROM ({check_sql(sql)}) LIMIT {max_rows}", conn)


def ask(conn, question):
    """Trả về dict: sql, explanation, model, result (DataFrame). Raise LLMUnavailable nếu không gọi được Gemini."""
    out = gemini.generate_json(SYSTEM_PROMPT, question, SQL_SCHEMA)
    out["result"] = run_sql(conn, out["sql"])
    return out


def _normalize(result):
    """Mỗi dòng -> tập giá trị (bỏ tên cột, bỏ thứ tự cột, làm tròn số thực)."""
    rows = []
    for row in result.itertuples(index=False):
        rows.append({round(float(v), 3) if isinstance(v, (int, float)) else str(v) for v in row})
    return rows


def _matches(gold, pred):
    """Đúng khi cùng số dòng và mỗi dòng chuẩn nằm trọn trong một dòng của LLM.

    Cho phép LLM trả thêm cột (vd. thêm tên phim bên cạnh số vé) nhưng không được sai giá trị.
    """
    if len(gold) != len(pred):
        return False
    remaining = list(pred)
    for g in gold:
        hit = next((p for p in remaining if g <= p), None)
        if hit is None:
            return False
        remaining.remove(hit)
    return True


def load_eval(path=EVAL_DIR / "ask_data_eval.json"):
    return json.loads(path.read_text(encoding="utf-8"))


def run_eval(conn, questions=None):
    """So kết quả SQL của LLM với SQL chuẩn. Trả về DataFrame từng câu + cột correct."""
    questions = questions or load_eval()
    rows = []
    for q in questions:
        gold_df = run_sql(conn, q["gold_sql"])
        gold = _normalize(gold_df)
        row = {"id": q["id"], "question": q["question"], "gold": gold_df.head(3).to_dict("records")}
        try:
            answer = ask(conn, q["question"])
            row.update(
                sql=answer["sql"],
                model=answer["model"],
                pred=answer["result"].head(3).to_dict("records"),
                correct=_matches(gold, _normalize(answer["result"])),
            )
        except LLMUnavailable as exc:
            row.update(sql=None, pred=None, correct=None, error=str(exc))
        except Exception as exc:  # SQL sai cú pháp/sai cột -> tính là trả lời sai
            row.update(sql=None, pred=None, correct=False, error=str(exc))
        rows.append(row)
    return pd.DataFrame(rows)
