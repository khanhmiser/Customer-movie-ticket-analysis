# Changelog

## [1.8.1] - 2026-10-09 · Chặn đưa bí mật lên GitHub
- `.gitignore` chặn thêm: `.env.*` (trừ `.env.example`), `.streamlit/secrets.toml` (key khi deploy), `*.pem`, `*.key`, `*.p12`, `credentials*.json`, `service_account*.json`, `token*.json`, `.claude/*.local.*`, `.codebase-memory/`, `.pytest_cache/`.
- `scripts/check_secrets.py`: quét các file sẽ đưa lên GitHub tìm key Google/Gemini (`AIza…`, `AQ.…`), Anthropic, OpenAI, Telegram, private key, và dòng `…_API_KEY=<giá trị>`; kiểm tra `.gitignore` còn đủ dòng bắt buộc. `--install-hook` (sau `git init`) → tự quét mỗi lần `git commit`, có key thì chặn commit.
- 5 test mới (`tests/test_secrets.py`) → 55 test; GitHub Actions chạy test nên cũng chặn ở bước CI. Đã thử: bộ quét bắt được định dạng key Gemini thật trong `.env`.

## [1.8] - 2026-10-09 · Hỏi số liệu (Text-to-SQL) chuyển sang Gemini
- `src/gemini.py`: phần gọi Gemini dùng chung cho Hỏi tài liệu (RAG) và Hỏi số liệu (SQL) - chuỗi model dự phòng `GEMINI_MODELS` (đổi tên từ `RAG_MODELS`), tối đa 15 giây/lần gọi, 429/500/503/504/404 → sang model sau. Biến tắt Gemini đổi từ `RAG_MODE` thành `GEMINI_MODE`.
- `src/ask_data.py` dùng Gemini thay Claude → chế độ "Hỏi số liệu (SQL)" chạy được khi có `GEMINI_API_KEY` (không cần bật "Dùng LLM viết bản tin"). SQL bọc trong khối ```sql được bóc ra rồi mới kiểm tra an toàn.
- Dashboard, chế độ SQL: bảng kết quả hiện trước, câu giải thích + model đã trả lời, câu SQL thu vào "Xem câu SQL"; câu trả lời được nhớ trong phiên (không gọi lại API khi bấm qua lại).
- **Lần đầu chạy bộ đánh giá Text-to-SQL** (`eval/ask_data_eval.json`, 12 câu, chấm bằng so kết quả với SQL chuẩn): **12/12 đúng**, 146 giây, ngày 2026-10-09. Model chính `gemini-3.5-flash` đã hết hạn mức trong ngày nên các câu do `gemini-3.7-flash`, `gemini-3-flash-preview`, `gemini-3.6-flash` trả lời.
- Bản tin phòng ban vẫn dùng Claude (chưa có key → template).
- 50 test.

## [1.7] - 2026-10-09 · Hỏi đáp tài liệu (RAG) bằng Gemini
- `src/rag.py`: hỏi đáp trên 144 đoạn tài liệu (README, `docs/`, từ điển dữ liệu, CHANGELOG, phần chữ của 6 notebook, bản tin các tuần). Chia đoạn theo tiêu đề → nhúng vector `gemini-embedding-001` (có cache, chỉ nhúng đoạn mới/đổi) + TF-IDF → gộp xếp hạng (Reciprocal Rank Fusion) → Gemini trả lời CHỈ từ đoạn tìm được, kèm nguồn [n].
- Chống bịa số như bản tin: số trong câu trả lời không có trong đoạn trích → chặn, chỉ hiện đoạn trích. Không có key / Gemini lỗi → vẫn tìm đoạn liên quan bằng TF-IDF.
- Chuỗi 8 model dự phòng (`src/config.py` → `RAG_MODELS`): `gemini-3.5-flash` → `3.7-flash` → `3-flash-preview` → `3.6-flash` → `3.5-flash-lite` → `3.1-flash-lite` → `3.1-flash-lite-preview` → `gemma-4-26b-a4b-it`. Model hết hạn mức (429) / quá tải (503) / bị ngừng (404) / quá 15 giây → sang ngay model sau. Đã gọi thử 14 model với 1 câu hỏi RAG; loại 6 model báo 429/404 và `gemma-4-31b-it` (đúng nhưng 35 giây).
- Tab "Hỏi dữ liệu" có 2 chế độ: **Hỏi tài liệu & báo cáo** (RAG) và **Hỏi số liệu (SQL)** như cũ.
- `eval/rag_eval.json` (14 câu: 12 có đáp án trong tài liệu + 2 ngoài phạm vi). Kết quả chạy thật 2026-10-09: tìm đúng tài liệu trong top 6: 12/12 (chỉ TF-IDF cũng 12/12); trả lời đúng 14/14. Bộ câu hỏi nhỏ, do Claude soạn từ chính tài liệu → chỉ là kiểm tra cơ bản, chưa phải đánh giá độc lập.
- 8 test mới (`tests/test_rag.py`, không gọi API, gồm test chuyển model khi model trước hết hạn mức) → 49 test.
- Dashboard tự nạp lại chỉ mục khi tài liệu / bản tin đổi (không cần khởi động lại).

## [1.6.1] - 2026-10-09 · Bảng màu thương hiệu
- Đổi bảng màu theo lựa chọn của người dùng: navy `#091540` (chữ chính, dải tiêu đề, header Excel), xanh đậm `#1B2CC1` (chuỗi chính), xanh nhạt `#7692FF` (chuỗi thứ 2), xanh rất nhạt `#ABD2FA` (nền nhấn). Nền trang ánh xanh `#f4f7fd`.
- Kiểm định (`validate_palette`): `#1B2CC1`/`#7692FF` tách biệt tốt với người mù màu (ΔE 24.5) và mắt thường (ΔE 28.6); `#7692FF` tương phản 2.79:1 (< 3:1) → biểu đồ 2 chuỗi luôn kèm chú thích + bảng số. `#1B2CC1` hơi tối so với dải sáng khuyến nghị (L 0.41 < 0.43) - giữ đúng mã màu người dùng chọn.
- Thẻ chỉ số có viền trên màu xanh, tiêu đề mục có vạch xanh bên trái; màu trạng thái (xanh lá/đỏ/vàng) giữ nguyên.

## [1.6] - 2026-10-09 · Giao diện dashboard
- Thiết kế lại toàn bộ dashboard (`app/ui.py` + `app/streamlit_app.py`): header chung kèm nhãn trạng thái (cảnh báo / chất lượng dữ liệu), thẻ chỉ số đồng đều, chip thay đổi có mũi tên + chữ, màu theo chiều tốt của từng chỉ số.
- Bảng màu theo bộ tham chiếu đã kiểm định cho người mù màu (xanh `#2a78d6` / cam `#eb6834`); màu trạng thái chỉ dùng khi mang nghĩa tốt/xấu, luôn kèm biểu tượng + chữ.
- Biểu đồ: không nối thẳng qua giai đoạn COVID (để trống tháng/tuần thiếu dữ liệu), Product/IT chỉ hiện 26 tuần theo lịch, trục thời gian dạng `MM/YY`, nhấn mạnh 1 cột thay vì tô màu tất cả.
- Bảng: tiêu đề cột tiếng Việt, tên lỗi tiếng Việt ngắn gọn, định dạng số thống nhất với bản tin & Excel (không đổi theo ngôn ngữ trình duyệt), ô chưa đủ dữ liệu hiện "—".

## [1.5] - 2026-10-09 · Tài liệu & kiểm thử
- `docs/runbook.md` (vận hành, xử lý khi dữ liệu lỗi, cảnh báo, cấu hình, sự cố thường gặp), `docs/data_workflow.md` (sơ đồ luồng dữ liệu, định nghĩa mọi chỉ số), `docs/huong_dan_phong_ban.md` (hướng dẫn cho 5 phòng ban), `docs/ai_usage_log.md` (dùng AI thế nào, kiểm chứng ra sao).
- 41 test tự động (`tests/`, `pytest`); GitHub Actions chạy test trước, test hỏng thì không gửi báo cáo.
- Sửa: pipeline không còn lỗi khi `BAO_CAO_MOI_NHAT.xlsx` đang mở trong Excel (chỉ cảnh báo).

## [1.4] - 2026-10-09 · Xử lý dữ liệu mới thật
- Nhận file cập nhật bảng tham chiếu `customer_ / campaign_ / device_detail_ / status_detail_<ngày>.csv`, kiểm tra riêng, áp dụng **trước** giao dịch cùng ngày.
- Tự tách file xuất nhiều ngày; chặn file gửi lại khác nội dung; file đã nạp chuyển sang `data/archive/`; tuổi tính tại ngày cuối dữ liệu.
- Kho cũ tự chuyển sang định dạng trạng thái mới, không nạp lại.
- Sửa: bản trước chặn **mọi** ngày có khách mới (bảng tham chiếu cố định).

## [1.3] - 2026-10-09 · Phòng ban dùng không cần code
- Email riêng cho từng phòng (bản tin trong nội dung + Excel riêng đính kèm); chưa cấu hình SMTP thì chỉ lưu bản xem trước `.eml`.
- File bấm đúp `1_CHAY_BAO_CAO_TUAN.bat`, `2_MO_DASHBOARD.bat`, `3_DAT_LICH_TU_CHAY_THU_HAI.bat`; `reports/BAO_CAO_MOI_NHAT.xlsx`.
- Dashboard mặc định tuần mới nhất, có hướng dẫn; sẵn sàng deploy Streamlit Community Cloud; GitHub Actions gửi email qua Secrets.

## [1.2] - 2026-10-09 · Tự động hóa vận hành
- Nạp dữ liệu theo ngày (`src/ingest.py`) + 12 kiểm tra chất lượng (`src/quality.py`): lỗi → cách ly file và dừng báo cáo.
- Báo cáo Excel 7 sheet (`src/excel_report.py`).
- Dataset cho analyst + từ điển dữ liệu tự sinh (`src/marts.py`).
- Notebook 06.

## [1.1] - 2026-10-09 · Mỗi phòng ban nhận được gì
- 6 nhóm KPI theo slide báo cáo (`src/kpis.py`); phân nhóm khách theo slide + điểm quay lại 90 ngày + hiệu quả campaign (`src/marketing.py`); khoanh vùng lỗi mã × nền tảng × phương thức (`src/product.py`); thất thoát tài chính (`src/finance.py`).
- Bản tin cho Ban lãnh đạo; dashboard 1 tab / phòng ban; notebook 05.

## [1.0] - 2026-10-08 · Dựng lại project
- Phát hiện vấn đề chính: 16,802 khách lỗi thanh toán ngay lần đầu, 13,701 không bao giờ mua được.
- Model rủi ro thanh toán, cảnh báo tuần, bản tin LLM có chống bịa số, Text-to-SQL + bộ đánh giá, pipeline tuần, dashboard; notebook 01–04.
- Sửa 5 lỗi của notebook gốc (cohort 2022, khách 0 giao dịch thành công bị loại, biểu đồ vẽ nhầm biến, thiếu 1 mã lỗi, tuổi theo ngày chạy) và 3 số không tái lập được trong README cũ. README mới bỏ khung "Kompany".

## [0.1] · Bản gốc
- `file analyst.ipynb`: phân tích khám phá hành vi đặt vé 2019–2022 (chân dung khách, thời gian, nền tảng, thanh toán, khuyến mãi, cohort, tỷ lệ thanh toán thành công).
