<p align="center">
  <img src="/assets/icon.png" width="120" alt="SmartCalories logo">
</p>

<h1 align="center">🥗 SmartCalories</h1>

<p align="center"><strong>Ứng dụng quản lý khẩu phần ăn và phân tích dinh dưỡng hằng ngày</strong></p>
<p align="center">
  <a href="https://nhat-ky-an-uong.onrender.com/" target="_blank"><strong>🌐 Truy cập bản demo</strong></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-blue?logo=python">
  <img src="https://img.shields.io/badge/FastAPI-Framework-0ba360?logo=fastapi">
  <img src="https://img.shields.io/badge/MongoDB-Database-green?logo=mongodb">
  <img src="https://img.shields.io/badge/TailwindCSS-UI-blue?logo=tailwindcss">
</p>

---

## 🚀 Tính năng

- 👤 Đăng ký / đăng nhập người dùng (có phân quyền `admin` / `user`)
- 🧠 Phân tích BMR / TDEE dựa theo chiều cao, cân nặng, tuổi, giới tính
- 🍽️ Quản lý món ăn: thêm, sửa, xoá kèm thông tin dinh dưỡng và hình ảnh
- 🧾 Ghi nhật ký ăn uống theo ngày, thống kê và phân tích
- 🧮 Gợi ý món ăn theo chất dinh dưỡng còn thiếu (calories, protein, carbs, fat)
- 📊 Biểu đồ phân tích bằng Chart.js
- 📤 Xuất dữ liệu nhật ký ra `.csv` (theo ngày hoặc tất cả)
- ☁️ Upload ảnh đại diện lên Cloudinary
- 🔐 Quản lý phiên đăng nhập bằng cookie và mã phiên
- 🔑 Đặt lại mật khẩu qua email với FastAPI-Mail
- 👮‍♀️ Admin: quản lý người dùng, khóa tài khoản, theo dõi nhật ký hoạt động và đăng nhập
- 📸 Giao diện hiện đại bằng TailwindCSS

---

## 🛠️ Cài đặt

### ✅ Yêu cầu

- Python 3.8+
- MongoDB đã khởi chạy
- Tài khoản Cloudinary (để upload avatar)
- SMTP email (ví dụ Gmail để gửi mail đặt lại mật khẩu)

### 📥 Cài đặt local

```bash
git clone https://github.com/your-username/smartcalories.git
cd smartcalories
pip install -r requirements.txt
📌 Tạo file .env (nếu cần) để chứa thông tin nhạy cảm (mail, cloudinary, v.v.)

bash
Sao chép
Chỉnh sửa
uvicorn main:app --reload
👉 Truy cập tại: http://localhost:8000

### 🧰 Thư viện sử dụng

fastapi, uvicorn, pymongo, jinja2, python-dotenv

passlib[bcrypt], bcrypt, python-multipart

pytz, fastapi-mail, httpx, cloudinary

apscheduler (tự động hóa hoặc gửi thông báo định kỳ)

Chart.js và TailwindCSS (frontend)

### 📁 Cấu trúc thư mục

csharp
Sao chép
Chỉnh sửa
smartcalories/
├── app/
│   ├── templates/         # HTML sử dụng Jinja2
│   ├── static/            # Ảnh, CSS, JS, favicon, logo
│   ├── database.py        # Kết nối MongoDB
│   └── main.py            # FastAPI endpoints
├── assets/
│   └── icon.png
├── requirements.txt
└── README.md
🖼️ Giao diện minh họa
📋 Danh sách món ăn

<p align="center"><img src="/assets/demo.png" width="600"></p>

### 📈 Nhật ký & Phân tích

<p align="center"><img src="/assets/analysis.png" width="600"></p>

### 📤 Xuất CSV

Chọn "Xuất CSV" từ menu, chọn xuất hôm nay hoặc tất cả lịch sử nhật ký ăn uống.

### 📄 Giấy phép

Phát hành dưới giấy phép MIT.

### 💡 Góp ý & Hỗ trợ

Bạn có thể tạo issue hoặc gửi pull request để đóng góp cho dự án.
Cảm ơn bạn đã sử dụng SmartCalories!
