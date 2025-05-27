<p align="center">
  <img src="/assets/icon.png" width="100" alt="SmartCalories logo">
</p>

<h1 align="center">🥗 SmartCalories</h1>
<p align="center"><strong>Ứng dụng theo dõi khẩu phần ăn, phân tích dinh dưỡng & hoạt động thể chất hằng ngày</strong></p>
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

## 🚀 Tính năng nổi bật

- 👤 Đăng ký / đăng nhập người dùng (phân quyền `admin` / `user`)
- 🔒 Bảo mật phiên đăng nhập với token & cookie
- 🔑 Quên mật khẩu? Hỗ trợ đặt lại qua email (FastAPI-Mail)
- 🍽️ Quản lý món ăn: thêm / sửa / xoá kèm thông tin dinh dưỡng và ảnh
- 📝 Ghi nhật ký ăn uống mỗi ngày
- ⚙️ Tự động tính tổng lượng calories, protein, carbs, fat trong ngày
- 🧠 Phân tích BMR, TDEE theo cân nặng, chiều cao, tuổi, giới tính
- 🥗 Gợi ý món ăn dựa trên dưỡng chất còn thiếu
- 📊 Biểu đồ phân tích dinh dưỡng (Chart.js)
- 🏃 Ghi lại hoạt động thể chất, tính kcal tiêu thụ (MET-based)
- 📤 Xuất dữ liệu nhật ký ăn uống ra file `.csv`
- 👨‍💼 Chế độ admin: quản lý người dùng, khóa tài khoản, xem log đăng nhập & hoạt động
- 🤖 Chatbot tích hợp trợ lý Gemini hỗ trợ người dùng hỏi về dinh dưỡng

---

## 🛠️ Hướng dẫn cài đặt

### ✅ Yêu cầu

- Python 3.8+
- MongoDB đang hoạt động
- Tài khoản Cloudinary (để lưu ảnh)
- SMTP (ví dụ: Gmail cho việc gửi mail)

---

### 📦 Cài đặt local

```bash
git clone https://github.com/your-username/smartcalories.git
cd smartcalories
pip install -r requirements.txt

---

### Tạo file .env để lưu cấu hình bảo mật:

env
Sao chép
Chỉnh sửa
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
CLOUDINARY_CLOUD_NAME=...
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...

---

### Chạy ứng dụng:

bash
Sao chép
Chỉnh sửa
uvicorn main:app --reload
👉 Truy cập tại: http://localhost:8000

---

## 🧰 Công nghệ sử dụng
Backend: FastAPI, uvicorn, pymongo, jinja2, apscheduler

Auth: passlib, bcrypt, secrets

Email: fastapi-mail

UI: TailwindCSS, Chart.js, Jinja2

Others: pytz, cloudinary, httpx, dotenv

---

## 📁 Cấu trúc thư mục
csharp
Sao chép
Chỉnh sửa
smartcalories/
├── app/
│   ├── templates/         # Giao diện HTML
│   ├── static/            # Ảnh, CSS, JS
│   └── database.py        # Kết nối MongoDB
├── main.py                # FastAPI app chính
├── requirements.txt
└── README.md
🖼️ Giao diện minh họa
📋 Danh sách món ăn

<p align="center"><img src="/assets/demo.png" width="600"></p>
📈 Phân tích nhật ký ăn uống

<p align="center"><img src="/assets/analysis.png" width="600"></p>

---

## 📤 Xuất dữ liệu
Trong thanh bên, chọn "📤 Xuất CSV" để tải về:

Nhật ký hôm nay (?mode=today)

Toàn bộ lịch sử (?mode=all)

---

## 📜 Giấy phép
Phát hành theo giấy phép MIT.

---

## 💡 Đóng góp
Gửi ý kiến qua Issues hoặc Pull Request — mọi đóng góp đều được hoan nghênh!
Cảm ơn bạn đã sử dụng SmartCalories ❤️
