"""Gọi Claude với structured output; lỗi/không có key -> trả None để caller dùng bản dự phòng."""

import json
import os

from src.config import LLM_MODEL


class LLMUnavailable(Exception):
    pass


def llm_enabled():
    # LLM_MODE=off để chạy hoàn toàn bằng template (CI không có key, demo offline...)
    return os.getenv("LLM_MODE", "on").lower() != "off"


def _client():
    try:
        import anthropic
    except ImportError as exc:
        raise LLMUnavailable("chưa cài thư viện anthropic (pip install anthropic)") from exc
    return anthropic, anthropic.Anthropic()


def generate_json(system, prompt, schema, effort="medium", max_tokens=16000):
    """Trả về dict đúng `schema`. Raise LLMUnavailable nếu không gọi được hoặc bị từ chối."""
    if not llm_enabled():
        raise LLMUnavailable("LLM_MODE=off")
    anthropic, client = _client()
    try:
        response = client.beta.messages.create(
            model=LLM_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            # Nếu model từ chối vì bộ lọc an toàn, server tự chạy lại trên model dự phòng phù hợp
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AuthenticationError as exc:
        raise LLMUnavailable("API key không hợp lệ hoặc chưa cấu hình") from exc
    except anthropic.RateLimitError as exc:
        raise LLMUnavailable("bị giới hạn tốc độ (rate limit)") from exc
    except anthropic.APIStatusError as exc:
        raise LLMUnavailable(f"lỗi API {exc.status_code}: {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise LLMUnavailable("không kết nối được tới API") from exc
    except TypeError as exc:
        # SDK báo không tìm thấy thông tin xác thực (không có key / profile)
        raise LLMUnavailable(str(exc)) from exc

    if response.stop_reason == "refusal":
        raise LLMUnavailable("model từ chối yêu cầu")
    if response.stop_reason == "max_tokens":
        raise LLMUnavailable("output bị cắt do max_tokens")
    text = next(block.text for block in response.content if block.type == "text")
    return json.loads(text)
