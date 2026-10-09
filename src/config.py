from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

try:  # đọc API key / token từ file .env nếu có (không bắt buộc)
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

DATA_DIR = ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = ROOT / "reports"
MODELS_DIR = ROOT / "models"
EVAL_DIR = ROOT / "eval"

# Tuổi được tính tại ngày cuối của dữ liệu đang có (dữ liệu mới về -> tuổi tự cập nhật), không dùng
# date.today() như bản gốc (mỗi lần chạy lại ra kết quả khác). Đây chỉ là giá trị mặc định.
REFERENCE_DATE = pd.Timestamp("2022-12-31")

# Train trên 2019-2021, test trên 2022 (chia theo thời gian, không chia ngẫu nhiên)
TEST_START = pd.Timestamp("2022-01-01")

# Phát hiện bất thường theo tuần
ANOMALY_WINDOW_WEEKS = 8
ANOMALY_Z_THRESHOLD = 3.0
ANOMALY_MIN_WEEKLY_TICKETS = 100

LLM_MODEL = "claude-opus-5-5"

# Gemini (key GEMINI_API_KEY trong .env): Hỏi tài liệu (RAG) + Hỏi số liệu (Text-to-SQL)
# Thử lần lượt: model đầu hết hạn mức (429) / quá tải (503) / bị ngừng (404) -> model sau.
# Đã gọi thử từng model với 1 câu hỏi RAG (2026-10-09). Model đầu = model đã chạy bộ đánh giá RAG 14 câu.
# Không dùng: gemini-3.8-flash, omni-1.1-flash, 3.1-pro-preview (429); 2.5-flash, 2.5-flash-lite, 2.5-pro (404);
# gemma-4-31b-it (trả lời đúng nhưng mất 35 giây).
GEMINI_MODELS = [
    "gemini-3.5-flash",               # 2.7s
    "gemini-3.7-flash",               # 4.4s
    "gemini-3-flash-preview",         # 2.4s
    "gemini-3.6-flash",               # lúc thử bị quá tải (503)
    "gemini-3.5-flash-lite",          # 1.4s
    "gemini-3.1-flash-lite",          # 1.6s
    "gemini-3.1-flash-lite-preview",  # 1.0s
    "gemma-4-26b-a4b-it",             # 1.8s, họ model khác -> hạn mức riêng
]
RAG_EMBED_MODEL = "gemini-embedding-001"
