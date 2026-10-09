# Data dictionary - data marts (as_of 2023-01-01)

Sinh tự động bởi `python -m src.marts`. File `.parquet` giữ đúng kiểu dữ liệu; `.csv` để mở bằng Excel.

## fact_payment_attempts

- **Grain:** 1 dòng = 1 lần thanh toán (thành công hoặc lỗi)
- **Khóa chính:** `ticket_id`
- **Số dòng:** 154,725

| Cột | Kiểu | Mô tả | Null | Unique | Ví dụ |
|---|---|---|---|---|---|
| `ticket_id` | object | Mã giao dịch (duy nhất) | 0.0% | 154,725 | d66e52d3f385fff36d7eccd5438d9af0, c501ae228c2bc33a4b107f5f1e337e34, 78e1c96f87a1d4e7e73c4ee6849459b8 |
| `customer_id` | int64 | Mã khách hàng | 0.0% | 119,477 | 120800, 146290, 111565 |
| `time` | datetime64[ns] | Thời điểm thanh toán | 0.0% | 154,725 | 2019-01-01 00:42:36.037000, 2019-01-01 01:43:45.485000, 2019-01-01 02:09:18.439000 |
| `date` | object | Ngày thanh toán | 0.0% | 1,174 | 2019-01-01, 2019-01-02, 2019-01-03 |
| `week` | datetime64[ns] | Thứ Hai đầu tuần của giao dịch | 0.0% | 185 | 2018-12-31 00:00:00, 2019-01-07 00:00:00, 2019-01-14 00:00:00 |
| `year_month` | object | Tháng giao dịch (YYYY-MM) | 0.0% | 45 | 2019-01, 2019-02, 2019-03 |
| `hour` | int32 | Giờ trong ngày (0-23) | 0.0% | 24 | 0, 1, 2 |
| `day_name` | object | Thứ trong tuần | 0.0% | 7 | Tuesday, Wednesday, Thursday |
| `paying_method` | object | Phương thức thanh toán | 0.0% | 5 | debit card, money in app, credit card |
| `platform` | object | Nền tảng: mobile / website / Unknown | 0.0% | 3 | mobile, website, Unknown |
| `os_version` | object | Hệ điều hành suy ra từ model thiết bị | 0.0% | 4 | ios, android and other, Unknown |
| `device_number` | object | Mã thiết bị | 0.0% | 126,459 | ffa778005430284ac432db6e8368f9ee, 22f03355e50c660ce224814c7bad7f7b, bfc7b908f73f7ca94e7c1fec2e3e5a4c |
| `theater_name` | float64 | Mã rạp | 0.0% | 179 | 131.0, 160.0, 148.0 |
| `movie_name` | object | Tên phim | 0.0% | 253 | Daddy Issues, Bumblebee, Aquaman |
| `campaign_id` | int64 | Mã campaign (0 = không dùng khuyến mãi) | 0.0% | 211 | 0, 13740, 14180 |
| `campaign_type` | object | Loại khuyến mãi: direct discount / voucher / reward point / none | 0.0% | 4 | none, reward point, voucher |
| `is_promotion` | bool | Giao dịch có dùng khuyến mãi | 0.0% | 2 | False, True |
| `original_price` | float64 | Giá gốc (đơn vị theo dataset) | 0.0% | 1,895 | 7.84, 12.78, 4.95 |
| `discount_value` | float64 | Số tiền giảm | 0.0% | 242 | 0.0, 11.96, 2.06 |
| `final_price` | float64 | Giá khách trả = original_price - discount_value | 0.0% | 2,276 | 7.84, 0.82, 4.95 |
| `discount_rate` | float64 | discount_value / original_price | 0.0% | 2,927 | 0.0, 0.9358, 0.1784 |
| `status_id` | int64 | 1 = thành công; -1..-7 = mã lỗi | 0.0% | 8 | 1, -2, -4 |
| `status_description` | object | Mô tả trạng thái / lỗi | 0.0% | 8 | Order successful, Insufficient funds in customer account. , Password locked due to multiple incorrec |
| `error_group` | object | Nhóm lỗi: customer / external (ngân hàng) / internal / none | 0.0% | 4 | none, customer, external |
| `is_success` | bool | Thanh toán thành công | 0.0% | 2 | True, False |
| `attempt_number` | int64 | Lần thanh toán thứ mấy của khách (1 = lần đầu) | 0.0% | 260 | 1, 2, 3 |
| `is_first_attempt` | bool | Là lần thanh toán đầu tiên của khách | 0.0% | 2 | True, False |
| `failure_risk_score` | float64 | Điểm rủi ro lỗi từ model notebook 03 (0-1, chỉ dùng thông tin trước giao dịch; model train trên 2019-2021 nên điểm của giai đoạn này là in-sample) | 0.0% | 6,226 | 0.2793, 0.0179, 0.0306 |

## dim_customer

- **Grain:** 1 dòng = 1 khách hàng trong bảng customer (kể cả khách chưa từng thanh toán)
- **Khóa chính:** `customer_id`
- **Số dòng:** 131,400

| Cột | Kiểu | Mô tả | Null | Unique | Ví dụ |
|---|---|---|---|---|---|
| `customer_id` | int64 | Mã khách hàng | 0.0% | 131,400 | 100032, 100046, 100050 |
| `usergender` | object | Giới tính (Not verify = chưa xác minh) | 0.0% | 3 | Female, Male, Not verify |
| `dob` | datetime64[ns] | Ngày sinh | 0.0% | 11,640 | 1985-08-08 00:00:00, 1987-07-11 00:00:00, 1994-11-19 00:00:00 |
| `age` | int64 | Tuổi tại ngày cuối của dữ liệu | 0.0% | 106 | 37, 35, 28 |
| `age_generation` | object | Thế hệ: gen z / gen y / gen x / baby boomers | 0.0% | 4 | gen y, gen z, gen x |
| `first_attempt_time` | datetime64[ns] | Lần thanh toán đầu tiên | 9.1% | 119,477 | 2019-12-06 10:16:09.481000, 2022-01-07 13:20:22.013000, 2019-06-26 13:33:33.754000 |
| `first_success_time` | datetime64[ns] | Lần mua thành công đầu tiên | 19.5% | 105,776 | 2020-01-10 23:02:28.205000, 2022-01-07 13:20:22.013000, 2019-06-26 13:33:33.754000 |
| `n_attempts` | int64 | Tổng số lần thanh toán | 0.0% | 44 | 3, 2, 0 |
| `n_success` | int64 | Số lần mua thành công | 0.0% | 47 | 2, 0, 1 |
| `total_spend` | float64 | Tổng final_price các giao dịch thành công | 0.0% | 5,525 | 14.93, 8.95, 15.58 |
| `total_discount` | float64 | Tổng tiền được giảm | 0.0% | 1,099 | 3.38, 6.52, 2.56 |
| `first_attempt_failed` | boolean | Lần thanh toán đầu tiên bị lỗi | 9.1% | 2 | True, False |
| `has_activity` | bool | Khách có ít nhất 1 lần thanh toán | 0.0% | 2 | True, False |
| `n_failed` | int64 | Số lần thanh toán lỗi | 0.0% | 7 | 1, 0, 2 |
| `success_rate` | float64 | n_success / n_attempts | 9.1% | 51 | 0.6667, 1.0, 0.0 |
| `lost_at_first_payment` | boolean | Lỗi lần đầu VÀ chưa bao giờ mua thành công | 0.0% | 2 | False, True |
| `is_verified_profile` | bool | Có thông tin giới tính & ngày sinh thật (không phải Not verify / autofill 1970) | 0.0% | 2 | True, False |

## customer_features

- **Grain:** 1 dòng = 1 khách đã từng mua thành công, tính tại thời điểm as_of
- **Khóa chính:** `customer_id`
- **Số dòng:** 105,776

| Cột | Kiểu | Mô tả | Null | Unique | Ví dụ |
|---|---|---|---|---|---|
| `customer_id` | int64 | Mã khách hàng | 0.0% | 105,776 | 100001, 100003, 100004 |
| `as_of` | datetime64[ns] | Thời điểm tính đặc trưng | 0.0% | 1 | 2023-01-01 00:00:00 |
| `recency_days` | int64 | Số ngày từ lần mua thành công gần nhất tới as_of | 0.0% | 1,151 | 1402, 223, 11 |
| `tenure_days` | int64 | Số ngày từ lần mua thành công đầu tiên tới as_of | 0.0% | 1,161 | 1402, 1385, 11 |
| `frequency` | int64 | Số lần mua thành công trước as_of | 0.0% | 46 | 1, 6, 7 |
| `n_months` | int64 | Số tháng có mua | 0.0% | 18 | 1, 6, 7 |
| `monetary` | float64 | Tổng chi tiêu trước as_of | 0.0% | 5,524 | 5.36, 58.39, 32.25 |
| `avg_price` | float64 | Giá trung bình mỗi vé | 0.0% | 7,164 | 5.36, 9.7317, 32.25 |
| `promo_share` | float64 | Tỷ lệ giao dịch có khuyến mãi | 0.0% | 68 | 1.0, 0.1667, 0.0 |
| `discount_rate` | float64 | discount_value / original_price | 0.0% | 11,437 | 0.2776, 0.047, 0.0 |
| `wallet_share` | float64 | Tỷ lệ giao dịch dùng ví trong app | 0.0% | 65 | 1.0, 0.5, 0.2857 |
| `mobile_share` | float64 | Tỷ lệ giao dịch qua mobile | 0.0% | 18 | 1.0, 0.0, 0.5 |
| `n_failed` | float64 | Số lần thanh toán lỗi | 0.0% | 7 | 0.0, 1.0, 2.0 |
| `segment` | object | Nhóm khách (luật theo slide báo cáo) | 0.0% | 5 | Khách lâu chưa quay lại, Khách mua một lần (mới), Khách giá trị cao |
| `action` | object | Hướng xử lý đề xuất cho nhóm | 0.0% | 5 | Kéo lại bằng phim mới, voucher quay lại,, Tặng coupon cho lần mua thứ hai trong vò, Membership, ưu đãi đặc quyền, đặt vé sớm |
| `repurchase_score` | float64 | Xác suất mua lại trong 90 ngày sau as_of (model RFM, AUC backtest ~0.66) | 0.0% | 2,613 | 0.0116, 0.0928, 0.0764 |
| `score_source` | object | Nguồn điểm: model hoặc luật recency (khi thiếu dữ liệu train) | 0.0% | 1 | model |

## campaign_summary

- **Grain:** 1 dòng = 1 campaign_id (0 = không dùng khuyến mãi)
- **Khóa chính:** `campaign_id`
- **Số dòng:** 211

| Cột | Kiểu | Mô tả | Null | Unique | Ví dụ |
|---|---|---|---|---|---|
| `campaign_id` | int64 | Mã campaign (0 = không dùng khuyến mãi) | 0.0% | 211 | 0, 73240, 83330 |
| `campaign_type` | object | Loại khuyến mãi: direct discount / voucher / reward point / none | 0.0% | 4 | none, direct discount, reward point |
| `tickets` | int64 | Số lượt thanh toán | 0.0% | 124 | 63098, 14185, 12805 |
| `success_tickets` | int64 | Số vé thành công | 0.0% | 124 | 55156, 11935, 10917 |
| `customers` | int64 | Số khách khác nhau | 0.0% | 123 | 44858, 11563, 10780 |
| `revenue` | float64 | Doanh thu (tổng final_price thành công) | 0.0% | 205 | 500895.18, 85380.82, 79454.59 |
| `discount_spend` | float64 | Tổng tiền giảm giá | 0.0% | 158 | 14320.01, 41374.83, 28122.85 |
| `failure_rate` | float64 | Tỷ lệ thanh toán lỗi | 0.0% | 119 | 0.1259, 0.1586, 0.1474 |
| `new_customers` | float64 | Số khách có lần mua đầu tiên bằng campaign này (đủ 90 ngày quan sát) | 13.7% | 108 | 32977.0, 10180.0, 9173.0 |
| `returned_90d` | float64 | Tỷ lệ khách mới mua lần 2 trong 90 ngày | 13.7% | 107 | 0.0954, 0.0923, 0.0717 |
| `one_time_rate` | float64 | 1 - returned_90d | 13.7% | 107 | 0.9046, 0.9077, 0.9283 |
| `discount_per_returned` | float64 | Tiền giảm giá cho khách mới / số khách mới quay lại | 42.6% | 116 | 2.529, 37.4663, 35.7607 |
