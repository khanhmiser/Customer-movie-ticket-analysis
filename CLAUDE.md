# CLAUDE.md - Online Movie Ticketing: payment-failure recovery & operations reporting

Hệ thống phân tích + tự động hóa báo cáo vận hành cho nền tảng bán vé xem phim online (dữ liệu 2019–2022). Mô tả đầy đủ: `README.md`; lịch sử thay đổi: `CHANGELOG.md`; tài liệu: `docs/` (đọc các file này trước khi suy luận lại từ code). **Muốn sửa gì → mở file nào: `docs/architecture.md`** (sơ đồ luồng, bảng tra, hàm nóng, biến môi trường). Đồ thị code: codebase-memory project `movie-ticket`.

## Bản đồ code
| Ở đâu | Làm gì |
|---|---|
| `src/data_prep.py` | Load + làm sạch + join 5 bảng (`load_tickets(source="csv"|"warehouse")`) |
| `src/ingest.py`, `src/quality.py` | Nạp file theo ngày từ `data/incoming/` + 12 kiểm tra; file cập nhật bảng tham chiếu (`customer_/campaign_/device_detail_/status_detail_<ngày>.csv`); lỗi → `data/quarantine/` và DỪNG |
| `src/metrics.py`, `src/anomaly.py` | Chỉ số thanh toán, cảnh báo tuần (robust z ≥ 3, ≥ 100 lượt, 8 tuần nền) |
| `src/kpis.py`, `src/marketing.py`, `src/product.py`, `src/finance.py`, `src/departments.py` | Số liệu cho 5 phòng ban (6 KPI + 4 nhóm khách lấy theo slide báo cáo gốc) |
| `src/model.py` | Model rủi ro thanh toán lỗi (LightGBM, train 2019–2021, test 2022) |
| `src/llm.py`, `src/briefs.py` | LLM (**Claude**, structured output) viết bản tin từ FACTS + bộ chống bịa số |
| `src/gemini.py` | Gọi **Gemini** dùng chung (`GEMINI_API_KEY` trong `.env`): chuỗi model dự phòng `config.GEMINI_MODELS`, 15 giây/lần, lỗi → `LLMUnavailable` |
| `src/ask_data.py` | Text-to-SQL (Gemini) chỉ-đọc + `eval/ask_data_eval.json` (12/12 ngày 2026-10-09) |
| `src/rag.py` | Hỏi đáp tài liệu (Gemini): nhúng + TF-IDF, trả lời kèm nguồn, chặn số lạ; cache vector `data/rag/`; `eval/rag_eval.json` |
| `src/excel_report.py`, `src/deliver.py`, `src/notify.py` | Excel 7 sheet, email từng phòng (chưa có SMTP → `.eml` trong `outbox/`), Telegram |
| `src/pipeline.py` | Job tuần: `python -m src.pipeline [--week YYYY-MM-DD] [--ingest] [--send-email] [--no-llm]` |
| `src/marts.py` | Dataset cho analyst + `data/marts/data_dictionary.md` |
| `app/streamlit_app.py`, `app/ui.py` | Dashboard 7 tab; `ui.py` = màu, CSS, thẻ chỉ số, kiểu biểu đồ |
| `notebooks/01–06` | Phân tích → vấn đề → model → giám sát/LLM → phòng ban → tự động hóa (sinh lại bằng code, chạy được từ đầu) |
| `tests/` | 55 test pytest (conftest đặt `LLM_MODE=off`, `GEMINI_MODE=off`) |
| `scripts/build_notebooks.py` | Nguồn của notebook 01–06 |
| `scripts/check_secrets.py` | Quét key/mật khẩu trong file sẽ lên GitHub; `--install-hook` chặn commit |

## Chạy
- Python: conda env **`analyst`** (`C:\Users\Acer\anaconda3\envs\analyst\python.exe`). Env base của Anaconda lỗi matplotlib/NumPy - không dùng.
- Luôn đặt `PYTHONIOENCODING=utf-8` (tiếng Việt) và `LOKY_MAX_CPU_COUNT=4` (tránh cảnh báo joblib).
- Test: `python -m pytest -q` (phải xanh trước khi báo xong). Dashboard: `streamlit run app/streamlit_app.py`. File bấm đúp cho người dùng: `1_CHAY_BAO_CAO_TUAN.bat`, `2_MO_DASHBOARD.bat`, `3_DAT_LICH_TU_CHAY_THU_HAI.bat` (gọi `scripts/chay_tu_dong.bat`).

## Quy ước
- Comment, docstring, notebook, docs, giao diện: **tiếng Việt**. `README.md`: tiếng Anh.
- LLM **không bao giờ tự tính số**: Python tính FACTS (đã format), LLM chỉ diễn đạt, `briefs.validate_numbers` chặn số lạ → template. Thêm số mới vào bản tin thì thêm vào FACTS.
- **Bí mật không bao giờ lên GitHub:** key chỉ ở `.env` / Secrets; trước khi `git add`/push chạy `python scripts/check_secrets.py` (phải `OK`); sau `git init` cài hook bằng `--install-hook`. Thêm loại bí mật mới → thêm vào `.gitignore` + `REQUIRED_IGNORES`/`SECRET_PATTERNS`.
- Không gọi API tốn phí khi test / chạy thử: `LLM_MODE=off` hoặc `--no-llm`; Gemini: `GEMINI_MODE=off`. Gemini gói miễn phí hạn mức thấp, model hay quá tải (503/504) → `GEMINI_MODELS` là chuỗi 8 model dự phòng, mỗi lần gọi tối đa 15 giây; đừng chạy `rag eval` / `ask_data.run_eval` lặp lại. Thêm model: gọi thử 1 câu trước (nhiều model trong danh sách của Google báo 404/429). Không gửi email thật khi chưa được yêu cầu.
- Mọi số liệu cho tuần W chỉ dùng dữ liệu tới hết tuần W (backtest không nhìn tương lai). Tháng/tuần chưa đủ cửa sổ quan sát → `NaN`/"—", không lấy nửa kỳ.
- Kết luận trong notebook/README chỉ viết **sau khi** chạy và xem output; giữ cả kết quả âm; ghi rõ khi là backtest / mô phỏng.
- Biểu đồ: bảng màu thương hiệu người dùng chọn (`ui.C`: navy `#091540` chữ/tiêu đề, `#1B2CC1` chuỗi chính, `#7692FF` chuỗi 2 - kèm chú thích + bảng số vì tương phản < 3:1, `#ABD2FA` nền nhấn), màu trạng thái chỉ khi mang nghĩa tốt/xấu + kèm chữ, không 2 trục y, không nối đường qua khoảng thiếu dữ liệu (COVID). Bảng: tiêu đề cột tiếng Việt, định dạng số không phụ thuộc ngôn ngữ trình duyệt (`pct100` + `"%.1f%%"`).
- Sửa notebook: nội dung 6 notebook được định nghĩa trong **`scripts/build_notebooks.py`** - sửa ở đó (không sửa tay JSON), chạy `python scripts/build_notebooks.py`, rồi `python -m nbconvert --to notebook --execute --inplace notebooks/0X_*.ipynb` và kiểm tra 0 lỗi. Markdown kết luận có số cụ thể → kiểm lại với output sau khi chạy.

## Bẫy đã gặp trên máy này
- Streamlit giữ module đã import (`app/ui.py`) trong bộ nhớ → **khởi động lại server** sau khi sửa; phím "r" chỉ chạy lại script chính.
- `python -I` bỏ qua `PYTHONIOENCODING` → dùng `sys.stdout.reconfigure(encoding="utf-8")`.
- PowerShell 5.1 làm hỏng ký tự tiếng Việt trong script (vd. tên sheet Excel) → dùng chỉ số / ASCII.
- Tự động hóa Excel qua COM hay kẹt (`RPC_E_CALL_REJECTED`) và để lại EXCEL.EXE chạy ngầm → tránh; nếu dùng thì chỉ tắt tiến trình mình tạo.
- File `.bat` phải xuống dòng CRLF. Heredoc bash lồng `"""`/`'''` dễ vỡ → ghi script vá ra file rồi chạy.
- File Excel đang mở bị Windows khóa → pipeline đã xử lý (`PermissionError` chỉ cảnh báo).

## Dữ liệu sinh ra (không commit, tạo lại bằng lệnh)
`data/incoming|warehouse|archive|quarantine|processed|_demo`, `data/marts/*` (trừ data dictionary), `reports/data_quality|daily|logs`, `reports/weekly/*/outbox`, `data/rag/` (cache vector Gemini). Kho thật đã nạp đủ 1,174 file tới 2022-12-31.
