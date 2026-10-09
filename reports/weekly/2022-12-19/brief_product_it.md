# Product / IT - tuần 2022-12-19 → 2022-12-25
_Nguồn: template ("Could not resolve authentication method. Expected one of api_key, auth_token, or credentials to be set. Or for one of the `X-Api-Key` or `Authorization` headers to be explicitly omitted")_

## Payment failed from bank trên website / debit card: 38.9% (nền 31.7%)

2,836 lượt thanh toán, tỷ lệ thành công 93.3% (8 tuần trước: 91.4%). Không có cảnh báo bất thường về lỗi thanh toán tuần này.

### Điểm chính
- 2,836 lượt thanh toán, tỷ lệ thành công 93.3% (8 tuần trước: 91.4%).
- Không có cảnh báo bất thường về lỗi thanh toán tuần này.
- Payment failed from bank · website · debit card: 38.9% so với 31.7% (+7.1 điểm %, vượt mức bình thường 4 lỗi).
- Payment failed from bank · mobile · debit card: 22.6% so với 21.4% (+1.2 điểm %, vượt mức bình thường 2 lỗi).
- Payment overdue · mobile · debit card: 1.7% so với 0.5% (+1.2 điểm %, vượt mức bình thường 2 lỗi).
- Theo phương thức: debit card 27.7% vs money in app 1.2%.

### Hành động đề xuất
| Việc cần làm | Phụ trách | Chỉ số theo dõi |
|---|---|---|
| Làm việc với ngân hàng / cổng thanh toán về tổ hợp lỗi tăng mạnh nhất | Product / IT | Tỷ lệ lỗi nhóm external theo tuần |
| Thiết kế retry flow: thanh toán lại, đổi phương thức, giữ vé tạm thời | Product | Tỷ lệ hoàn tất thanh toán trên app |
| Gợi ý phương thức ít lỗi hơn ở checkout cho giao dịch rủi ro cao (A/B test) | Product | Tỷ lệ thanh toán thành công |
