"""Không đưa bí mật lên GitHub: .gitignore đủ chặn + bộ quét bắt được key (scripts/check_secrets.py)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_secrets  # noqa: E402

# Key giả ghép lúc chạy -> chính file test này không chứa chuỗi giống key
FAKE = {
    "gemini": "AIza" + "Sy" + "x" * 33,
    "google_new": "AQ." + "Ab8" + "Z" * 40,
    "anthropic": "sk-ant-" + "api03-" + "q" * 30,
    "telegram": "123456789:" + "A" * 35,
}


def test_gitignore_blocks_secret_files():
    assert check_secrets.missing_ignores() == []


def test_project_has_no_secrets_in_files_that_would_be_pushed():
    assert check_secrets.scan() == []


def test_detects_each_key_format():
    for kind, key in FAKE.items():
        assert check_secrets.scan_text(f"config = '{key}'"), kind
    assert check_secrets.scan_text("GEMINI_API_KEY=" + "abcdefghijklmnop")
    # .env.example: biến để trống không phải bí mật (kể cả khi dòng dưới là tên biến khác)
    assert check_secrets.scan_text("GEMINI_API_KEY=\nTELEGRAM_BOT_TOKEN=\nTELEGRAM_CHAT_ID=\n") == []


def test_secret_files_are_recognized_by_name():
    for rel in [".env", ".env.local", ".streamlit/secrets.toml", "config/recipients.json", "certs/server.pem"]:
        assert check_secrets.is_secret_file(rel), rel
    assert not check_secrets.is_secret_file(".env.example")


def test_scan_catches_key_pasted_into_code(tmp_path):
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    (tmp_path / ".env").write_text("GEMINI_API_KEY=" + FAKE["google_new"], encoding="utf-8")  # bị bỏ qua: đã ignore
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text(f"API_KEY = '{FAKE['google_new']}'\n", encoding="utf-8")
    assert check_secrets.scan(tmp_path) == [("src/app.py", "Google API key dạng mới (AQ.…)")]
