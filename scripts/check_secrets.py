"""Chặn đưa bí mật (API key, mật khẩu, token) lên GitHub.

Kiểm tra 2 việc:
1. `.gitignore` còn chặn đủ các file bí mật (`REQUIRED_IGNORES`).
2. Không file nào SẼ được commit chứa thứ trông giống key (`SECRET_PATTERNS`).

    python scripts/check_secrets.py                 # quét cả project
    python scripts/check_secrets.py --install-hook  # (sau `git init`) tự quét mỗi lần `git commit`, có key -> chặn commit

Đã có git: lấy đúng danh sách file git sẽ commit (`git ls-files`, đã trừ file trong .gitignore).
Chưa có git: quét mọi file chữ, trừ các file bí mật đã nằm trong .gitignore (`IGNORED_SECRET_FILES`).
"""

import argparse
import fnmatch
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# File bí mật / dữ liệu riêng phải luôn nằm trong .gitignore
REQUIRED_IGNORES = [
    ".env", ".env.*", "!.env.example", ".streamlit/secrets.toml", "config/recipients.json",
    "CLAUDE.local.md", "reports/weekly/*/outbox/", "data/rag/", "*.pem", "*.key", "credentials*.json",
]
IGNORED_SECRET_FILES = [".env", ".env.*", ".streamlit/secrets.toml", "config/recipients.json", "CLAUDE.local.md",
                        "*.pem", "*.key", "*.p12", "credentials*.json", "service_account*.json", "token*.json"]
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".ipynb_checkpoints", ".codebase-memory"}
TEXT_EXT = {".py", ".md", ".txt", ".json", ".toml", ".yml", ".yaml", ".ini", ".cfg", ".bat", ".sh", ".ps1",
            ".ipynb", ".csv", ".example", ".html", ".eml", ""}
MAX_BYTES = 2_000_000  # file CSV dữ liệu lớn: bỏ qua

SECRET_PATTERNS = {
    "Google / Gemini API key (AIza…)": re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    "Google API key dạng mới (AQ.…)": re.compile(r"\bAQ\.[0-9A-Za-z_\-]{30,}"),
    "Anthropic API key (sk-ant-…)": re.compile(r"sk-ant-[0-9A-Za-z_\-]{20,}"),
    "OpenAI API key (sk-…)": re.compile(r"\bsk-(?:proj-)?[0-9A-Za-z]{32,}"),
    "Telegram bot token": re.compile(r"\b\d{8,10}:[0-9A-Za-z_\-]{35}\b"),
    "Khóa riêng (private key)": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "Gán giá trị cho biến bí mật": re.compile(
        # [ \t] thay vì \s: \s khớp cả xuống dòng -> "KEY=" trống bị ghép với dòng dưới
        r"^[ \t]*(?:GEMINI_API_KEY|GOOGLE_API_KEY|ANTHROPIC_API_KEY|SMTP_PASSWORD|TELEGRAM_BOT_TOKEN)[ \t]*=[ \t]*"
        r"[\"']?[0-9A-Za-z_\-\.]{12,}", re.M),
}


def is_secret_file(rel):
    """File bí mật theo tên (.env, secrets.toml, *.pem…); .env.example là mẫu rỗng nên được commit."""
    name = rel.rsplit("/", 1)[-1]
    if name == ".env.example":
        return False
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(name, p) for p in IGNORED_SECRET_FILES)


def candidate_files(root=ROOT, staged=False):
    """Danh sách file (đường dẫn tương đối, dạng a/b.py) sẽ được đưa lên GitHub."""
    if (root / ".git").exists():
        cmd = (["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"] if staged
               else ["git", "ls-files", "--cached", "--others", "--exclude-standard"])
        out = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=True).stdout
        return [line for line in out.splitlines() if line]
    # Chưa có git: bỏ các thư mục dữ liệu sinh ra mà .gitignore đã chặn (hàng nghìn file, không chứa key)
    ignored_dirs = [line.strip().rstrip("*").rstrip("/") for line in
                    (root / ".gitignore").read_text(encoding="utf-8").splitlines()
                    if line.strip().endswith(("/", "/*")) and not line.startswith(("#", "!"))]
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        prefix = "" if rel_dir == "." else f"{rel_dir}/"
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS
                       and not any(fnmatch.fnmatch(prefix + d, pat) for pat in ignored_dirs)]
        files += [prefix + name for name in filenames if not is_secret_file(prefix + name)]
    return files


def scan_text(text):
    return [name for name, pattern in SECRET_PATTERNS.items() if pattern.search(text)]


def scan(root=ROOT, staged=False):
    """Trả về [(file, loại bí mật)]."""
    findings = []
    for rel in candidate_files(root, staged):
        p = root / rel
        if not p.is_file() or p.suffix.lower() not in TEXT_EXT or p.stat().st_size > MAX_BYTES:
            continue
        if is_secret_file(rel):  # file bí mật bị `git add -f` vẫn bị bắt
            findings.append((rel, "file bí mật (phải nằm trong .gitignore)"))
            continue
        findings += [(rel, kind) for kind in scan_text(p.read_text(encoding="utf-8", errors="ignore"))]
    return findings


def missing_ignores(root=ROOT):
    lines = {l.strip() for l in (root / ".gitignore").read_text(encoding="utf-8").splitlines()}
    return [p for p in REQUIRED_IGNORES if p not in lines]


def install_hook(root=ROOT):
    hooks = root / ".git" / "hooks"
    if not hooks.exists():
        sys.exit("Chưa có git. Chạy `git init` trước rồi chạy lại lệnh này.")
    py = Path(sys.executable).as_posix()
    (hooks / "pre-commit").write_text(f'#!/bin/sh\n"{py}" scripts/check_secrets.py --staged || exit 1\n',
                                      encoding="utf-8", newline="\n")
    print(f"Đã cài: mỗi lần `git commit` sẽ quét bí mật trước ({hooks / 'pre-commit'}).")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--staged", action="store_true", help="chỉ quét file đang chờ commit (dùng trong hook)")
    parser.add_argument("--install-hook", action="store_true")
    args = parser.parse_args()
    if args.install_hook:
        return install_hook()
    problems = [(".gitignore", f"thiếu dòng `{p}`") for p in missing_ignores()] + scan(staged=args.staged)
    if problems:
        print("DỪNG - có thể lộ bí mật nếu đưa lên GitHub:")
        for rel, kind in problems:
            print(f"  {rel}: {kind}")
        print("Cách sửa: xóa key khỏi file đó (để trong .env) hoặc thêm file vào .gitignore. "
              "Key đã lỡ đẩy lên GitHub thì phải TẠO KEY MỚI - xóa file không đủ.")
        sys.exit(1)
    print("OK - không thấy bí mật trong các file sẽ đưa lên GitHub.")


if __name__ == "__main__":
    main()
