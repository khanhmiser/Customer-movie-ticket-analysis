"""Gửi bản tin qua Telegram (tùy chọn). Không cấu hình -> bỏ qua, pipeline vẫn chạy."""

import json
import os
import urllib.request


def send_telegram(text):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    body = json.dumps({"chat_id": chat_id, "text": text[:4000]}).encode()
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body, headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.status == 200
