# HƯỚNG DẪN CÀI ĐẶT & CHẠY BOT DISCORD BÁO GIÁ QUEEN CITY

Bot tự động theo dõi biến động thị trường trong server Queen City FiveM. Khi phát hiện bất kỳ vật phẩm nào có **giá chạm đỉnh (100% MAX)** hoặc **sát đỉnh (mặc định >= 85%)**, bot sẽ ngay lập tức gửi cảnh báo lên Discord để anh em nhanh chóng đem hàng đi bán xả kiếm tiền!

---

## 📌 LƯU Ý VỀ THÔNG TIN BẠN ĐÃ CUNG CẤP

Trong tin nhắn bạn gửi:
- **ID:** `1565812710736793660` (Đây là **Application ID / Client ID** của Bot)
- **Secret:** `EgfBnIVsps2qU5xw1WoOy-p0xD9ZdCWe` (Đây là **Client Secret** dùng cho trang web OAuth2, **không phải** Bot Token)

Để Discord cho phép bot gửi tin nhắn vào server của bạn, bạn có **2 cách cực kỳ đơn giản**:

---

## 🚀 CÁCH 1: DÙNG DISCORD WEBHOOK (CỰC NHANH - MẤT 10 GIÂY)
> *Dành cho bạn nào muốn bot tự động bắn thông báo sát max vào kênh Discord ngay lập tức mà không cần cấu hình bot gateway phức tạp!*

1. Mở Discord trên máy tính.
2. Nhấp chuột phải vào kênh bạn muốn nhận thông báo (ví dụ `#kenh-bao-gia`) -> Chọn **Chỉnh sửa kênh** (*Edit Channel*).
3. Chọn mục **Tích hợp** (*Integrations*) -> Nhấn **Tạo Webhook** (*Create Webhook*).
4. Nhấn nút **Sao chép URL Webhook** (*Copy Webhook URL*).
5. Mở file `E:\codebot\config.json`, dán URL vào ô `"webhook_url"`:
   ```json
   "webhook_url": "https://discord.com/api/webhooks/...",
   ```
6. Chạy file `run.bat`. Xong! Bot sẽ tự động bắn tin nhắn đẹp mắt mỗi khi có món sát max hoặc chạm max!

---

## 🤖 CÁCH 2: DÙNG BOT TOKEN (CÓ ĐỦ LỆNH SLASH /gia, /max, !gia)
> *Dành cho bot tương tác 2 chiều (thành viên trong server có thể tự gõ `!gia <tên>` hoặc `/max` để tra cứu).*

### Bước 1: Lấy Bot Token
1. Truy cập vào trang quản trị Bot của bạn:  
   👉 **[https://discord.com/developers/applications/1565812710736793660/bot](https://discord.com/developers/applications/1565812710736793660/bot)**
2. Nhấn nút **Reset Token** (hoặc **View Token**) -> Nhập mật khẩu / mã xác thực nếu được hỏi -> Bấm **Copy** chuỗi Token (chuỗi dài khoảng 70 ký tự).
3. Cũng tại trang Bot đó, kéo xuống mục **Privileged Gateway Intents**:
   - Bật gạt xanh mục **MESSAGE CONTENT INTENT** (để bot đọc được lệnh chat `!gia`, `!max`).
   - Nhấn **Save Changes** ở thanh dưới cùng.

### Bước 2: Mời Bot vào Server Discord của bạn
Nhấp vào đường link mời đã được tạo sẵn theo ID của bạn:  
👉 **[LINK MỜI BOT VÀO SERVER](https://discord.com/oauth2/authorize?client_id=1565812710736793660&permissions=8&scope=bot%20applications.commands)**  
(Chọn server Discord của bạn rồi bấm Phê duyệt / Hoàn tất).

### Bước 3: Dán Token vào `config.json`
Mở file `E:\codebot\config.json`:
```json
{
  "application_id": "1565812710736793660",
  "client_secret": "EgfBnIVsps2qU5xw1WoOy-p0xD9ZdCWe",
  "bot_token": "DÁN_CHUỖI_TOKEN_VỪA_COPY_VÀO_ĐÂY",
  "webhook_url": "",
  "channel_id": "ID_KÊNH_NHẬN_THÔNG_BÁO_TỰ_ĐỘNG",
  "alert_threshold_percent": 85,
  "check_interval_seconds": 30
}
```
*(Mẹo: Bạn có thể để trống `"channel_id"`, sau khi bot vào server chỉ cần vào kênh muốn nhận thông báo gõ lệnh `!kenh` là bot tự ghi nhớ kênh đó!)*

### Bước 4: Khởi động Bot
Nhấp đúp chuột vào file **`run.bat`** để chạy bot.

---

## 📋 DANH SÁCH LỆNH CỦA BOT

| Lệnh Chat | Lệnh Slash | Chức Năng |
| :--- | :--- | :--- |
| `!gia <tên>` | `/gia <tên>` | Tra cứu giá hiện tại, giá min, giá max, % chạm đỉnh của 1 vật phẩm (VD: `!gia sắt`, `!gia bột mì`, `!gia nấm`) |
| `!max` | `/max` | Xem danh sách toàn bộ các mặt hàng đang **Chạm Max** (100%) hoặc **Sát Max** (>=85%) |
| `!check` | `/kiemtra` | Bắt bot quét thị trường ngay lập tức và cập nhật giá |
| `!all` | — | Xem toàn bộ 52 vật phẩm trong chợ chia theo từng danh mục (Khoáng sản, Câu cá, Nông sản, Nấm, Đốn gỗ...) |
| `!kenh` | — | *(Chỉ Admin)* Đặt kênh hiện tại làm nơi nhận thông báo giá tự động |
| `!nguong <% >` | — | *(Chỉ Admin)* Thay đổi ngưỡng báo sát max (Ví dụ: `!nguong 90` để chỉ báo khi đạt từ 90% trở lên) |
| `!help` | — | Mở bảng hướng dẫn trợ giúp lệnh |

---

## 🔄 CƠ CHẾ CẬP NHẬT GIÁ
- **Khi FiveM đang chạy:** Bot kết nối trực tiếp với bộ nhớ UI FiveM (CEF port 13172), đọc giá thời gian thực từ game mỗi 30 giây.
- **Khi FiveM tắt:** Bot tự động sử dụng và theo dõi file `market_prices.json` (52 vật phẩm với đầy đủ Min/Max chính xác).
- **Chống spam:** Bot chỉ gửi thông báo khi vật phẩm mới đạt mốc sát max hoặc có giá lập đỉnh cao hơn, không gửi lặp lại vô nghĩa.
