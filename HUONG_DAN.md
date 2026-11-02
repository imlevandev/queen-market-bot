# HƯỚNG DẪN SỬ DỤNG & AUTO-UPDATE BOT QUEEN MARKET

## 📦 1. GỬI FILE CHO NGƯỜI KHÁC DÙNG
Bạn chỉ cần gửi 2 file trong thư mục `E:\codebot`:
1. **`market_bot.exe`** (File chạy bot độc lập, không cần cài Python).
2. **`config.json`** (File cấu hình bot token, ID kênh Discord).

Người khác chỉ cần mở `market_bot.exe` là bot sẽ tự kết nối và quét giá.

---

## 🚀 2. TỰ ĐỘNG CẬP NHẬT (AUTO-UPDATE) CHO MÁY NGƯỜI KHÁC
Mỗi khi người khác bật `market_bot.exe`:
- Bot sẽ tự động hỏi GitHub Releases (`imlevandev/queen-market-bot`).
- Nếu phát hiện có bản mới hơn, bot sẽ **tự động tải bản mới về**, thay thế bản cũ và tự khởi động lại.
- Người dùng **không cần tải thủ công** hay làm bất cứ thao tác gì phức tạp!

---

## 🛠️ 3. KHI BẠN SỬA CODE VÀ MUỐN TỰ ĐỘNG PHÁT HÀNH BẢN MỚI
Sau khi bạn chỉnh sửa xong tính năng trong code (`bot.py`, `market_data.py`...):

👉 **Cách 1 (Đơn giản nhất):**
Nhấp đúp chuột vào file:
**`build_release.bat`**
- Nhập số phiên bản mới (ví dụ: `1.0.2`, hoặc chỉ cần ấn `Enter` để bot tự tăng số).
- Nhập ghi chú cập nhật rồi ấn `Enter`.
- Script sẽ tự động:
  1. Build ra `market_bot.exe`.
  2. Đăng bản mới lên GitHub Releases.
  3. Tất cả các máy người khác khi bật tool lên sẽ **ngay lập tức tự động tải bản mới này về**!

👉 **Cách 2 (Bằng dòng lệnh):**
```bash
python release.py 1.0.2 "Sửa lỗi và thêm tính năng mới"
```

---

## 📋 4. LINK GITHUB RELEASES
Bản phát hành được lưu công khai tại:  
👉 **[https://github.com/imlevandev/queen-market-bot/releases](https://github.com/imlevandev/queen-market-bot/releases)**
