"""Gọi Gemini dùng chung cho Hỏi tài liệu (RAG) và Hỏi số liệu (Text-to-SQL).

- Key: GEMINI_API_KEY trong .env. GEMINI_MODE=off để tắt hẳn (test luôn tắt).
- Thử lần lượt các model trong `GEMINI_MODELS`: model hết hạn mức (429) / quá tải (503) / bị ngừng (404)
  / quá TIMEOUT_MS -> sang ngay model sau. Mọi lỗi đổi thành LLMUnavailable để caller có đường lui.
"""

import json
import os
import time

from src.config import GEMINI_MODELS
from src.llm import LLMUnavailable

TIMEOUT_MS = 15_000  # 1 lần gọi quá 15 giây -> bỏ, sang model sau (đã gặp 1 lần treo ~40 giây)


class ModelBusy(LLMUnavailable):
    """Model này tạm không dùng được (hết hạn mức / quá tải / bị ngừng) -> thử model khác."""


def enabled():
    has_key = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    return has_key and os.getenv("GEMINI_MODE", "on").lower() != "off"


def client():
    if not enabled():
        raise LLMUnavailable("chưa có GEMINI_API_KEY trong .env hoặc GEMINI_MODE=off")
    try:
        from google import genai
    except ImportError as exc:
        raise LLMUnavailable("chưa cài thư viện google-genai (pip install google-genai)") from exc
    return genai.Client()


def call(fn, retries=2, attempt=0):
    """Chạy 1 lệnh gọi SDK, đổi lỗi thành LLMUnavailable / ModelBusy.

    500/503/504 (quá tải / quá thời gian tạm thời) -> đợi 2s, 4s rồi thử lại (`retries=0` khi còn model dự phòng).
    429 không chờ: hạn mức gói miễn phí thường tính theo ngày, chờ chỉ làm người dùng đợi lâu.
    """
    import httpx
    from google.genai import errors
    try:
        return fn()
    except httpx.TimeoutException as exc:
        raise ModelBusy(f"quá {TIMEOUT_MS // 1000} giây không trả lời") from exc
    except (httpx.TransportError, OSError) as exc:  # mất mạng / DNS
        raise LLMUnavailable("không kết nối được tới Gemini") from exc
    except errors.APIError as exc:
        if exc.code in (500, 503, 504) and attempt < retries:
            time.sleep(2 * 2 ** attempt)
            return call(fn, retries, attempt + 1)
        if exc.code in (404, 429, 500, 503, 504):
            reason = {404: "model không còn được cung cấp", 429: "hết hạn mức gọi",
                      504: "quá thời gian xử lý"}.get(exc.code, "máy chủ quá tải")
            raise ModelBusy(f"{reason} ({exc.code})") from exc
        if exc.code in (401, 403) or "API key" in str(exc):
            raise LLMUnavailable("API key Gemini không hợp lệ") from exc
        raise LLMUnavailable(f"lỗi Gemini {exc.code}: {exc.message}") from exc


def generate_json(system, prompt, schema, models=GEMINI_MODELS, client_=None, temperature=0.1):
    """Trả về dict đúng `schema` + khóa `model` (model đã trả lời). Raise LLMUnavailable nếu mọi model lỗi."""
    from google.genai import types
    gem = client_ or client()
    config = types.GenerateContentConfig(system_instruction=system, temperature=temperature,
                                         response_mime_type="application/json", response_schema=schema,
                                         http_options=types.HttpOptions(timeout=TIMEOUT_MS))
    errors_seen = []
    for model in models:
        try:
            r = call(lambda: gem.models.generate_content(model=model, contents=prompt, config=config), retries=0)
        except ModelBusy as exc:
            errors_seen.append(f"{model}: {exc}")
            continue
        if not r.text:
            raise LLMUnavailable("Gemini không trả về nội dung (có thể bị bộ lọc an toàn chặn)")
        return {**json.loads(r.text), "model": model}
    raise LLMUnavailable("mọi model đều tạm không dùng được - " + "; ".join(errors_seen))
