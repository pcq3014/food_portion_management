<div align="center">
  <img src="/app/static/logo.png" width="120" alt="SmartCalories logo">
  
  # 🥗 SmartCalories
  
  ### *Ứng dụng quản lý khẩu phần ăn và phân tích dinh dưỡng thông minh*
  
  [![Demo](https://img.shields.io/badge/🌐_Demo-Live-success?style=for-the-badge)](https://nhat-ky-an-uong.onrender.com/)
  [![Python](https://img.shields.io/badge/Python-3.8+-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
  [![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
  [![MongoDB](https://img.shields.io/badge/MongoDB-47A248?style=for-the-badge&logo=mongodb&logoColor=white)](https://mongodb.com)
  [![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com)
  
  ---
  
  **SmartCalories** là một ứng dụng web hiện đại giúp bạn theo dõi và quản lý chế độ ăn uống một cách thông minh và khoa học.
  
</div>

## ✨ Tính năng nổi bật

### 🔐 **Quản lý người dùng**
- 👤 Đăng ký/đăng nhập với xác thực an toàn
- 🔑 Đặt lại mật khẩu qua email với giao diện đẹp mắt
- 👥 Phân quyền admin/user với quản lý chi tiết
- 🔒 Bảo mật phiên đăng nhập với cookie và token

### 🧠 **Phân tích thông minh**
- 📊 Tính toán BMR/TDEE dựa trên thông số cá nhân
- 🎯 Gợi ý món ăn theo chất dinh dưỡng còn thiếu
- 📈 Biểu đồ phân tích dinh dưỡng trực quan
- 📋 Thống kê chi tiết theo ngày/tuần/tháng

### 🍽️ **Quản lý món ăn**
- ➕ Thêm món ăn với thông tin dinh dưỡng đầy đủ
- ✏️ Chỉnh sửa và cập nhật món ăn
- 🖼️ Upload hình ảnh món ăn lên Cloudinary
- 🗑️ Xóa món ăn không cần thiết

### 📝 **Nhật ký ăn uống**
- 📅 Ghi nhật ký theo ngày
- 🔍 Tìm kiếm món ăn nhanh chóng
- 💾 Lưu trữ lịch sử ăn uống
- 📤 Xuất dữ liệu ra file CSV

### 🏃‍♂️ **Ghi nhật ký hoạt động thể chất**
- 🏃 Chọn hoạt động: Đi bộ, chạy bộ, đạp xe, bơi lội, gym, yoga,...
- 🕒 Thời gian thực hiện: Ghi theo phút hoặc giờ
- 🔥 Tính toán calo tiêu hao: Dựa vào loại hoạt động, thời gian và trọng lượng cơ thể
- 📅 Lưu nhật ký hoạt động: Dễ dàng xem lại và theo dõi tiến độ

### 👨‍💼 **Tính năng Admin**
- 👥 Quản lý người dùng (khóa/mở tài khoản)
- 📊 Theo dõi nhật ký hoạt động hệ thống
- 🔑 Xem nhật ký đăng nhập
- 🔄 Phân quyền người dùng

### 🎨 **Giao diện hiện đại**
- 📱 Responsive design cho mọi thiết bị
- 🌈 Giao diện đẹp mắt với TailwindCSS
- ⚡ Tốc độ tải nhanh và mượt mà
- 🎭 Hiệu ứng animation tinh tế

## 👤 Tác giả

- **Đỗ Ngọc Phi** - MSSV: 2221050848
- **Nguyễn Minh Quân** - MSSV: 2221050125
- **GVHD**: Thầy Đặng Văn Nam, Cô Dương Thị Hiền Thanh  
  _Khoa CNTT - Trường ĐH Mỏ - Địa chất_

## 🚀 Demo trực tiếp

Bạn có thể trải nghiệm ứng dụng tại: **[nhat-ky-an-uong.onrender.com](https://nhat-ky-an-uong.onrender.com/)**

**Tài khoản demo:**
- **Admin:** `admin` / `admin123`
- **User:** `demo` / `demo123`

## 🛠️ Cài đặt và triển khai

### 📋 Yêu cầu hệ thống

- ![Python](https://img.shields.io/badge/-Python_3.8+-blue?logo=python&logoColor=white) **Python 3.8+**
- ![MongoDB](https://img.shields.io/badge/-MongoDB-green?logo=mongodb&logoColor=white) **MongoDB** (local hoặc cloud)
- ![Cloudinary](https://img.shields.io/badge/-Cloudinary-blue) **Tài khoản Cloudinary** (upload ảnh)
- ![Gmail](https://img.shields.io/badge/-SMTP_Email-red?logo=gmail&logoColor=white) **SMTP Email** (gửi mail đặt lại mật khẩu)

### 📥 Cài đặt local

```bash
# Clone repository
git clone https://github.com/your-username/smartcalories.git
cd smartcalories

# Cài đặt dependencies
pip install -r requirements.txt

# Tạo file .env (tùy chọn)
cp .env.example .env
# Chỉnh sửa thông tin trong file .env

# Chạy ứng dụng
cd app
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 🌐 Truy cập ứng dụng

Mở trình duyệt và truy cập: **[http://localhost:8000](http://localhost:8000)**

### ⚙️ Cấu hình môi trường

Tạo file `.env` trong thư mục `app/` với nội dung:

```env
# MongoDB
MONGODB_URL=mongodb://localhost:27017/smartcalories

# Cloudinary (Upload ảnh)
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# Email (Đặt lại mật khẩu)
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password
MAIL_FROM=your_email@gmail.com
MAIL_PORT=587
MAIL_SERVER=smtp.gmail.com

# Security
SECRET_KEY=your_secret_key_here

# Gemini AI (Tùy chọn)
GEMINI_API_KEY=your_gemini_api_key
```

## 📦 Thư viện và công nghệ

### 🐍 Backend
- ![FastAPI](https://img.shields.io/badge/-FastAPI-009688?logo=fastapi&logoColor=white) **FastAPI** - Web framework hiện đại
- ![MongoDB](https://img.shields.io/badge/-PyMongo-green?logo=mongodb&logoColor=white) **PyMongo** - MongoDB driver
- ![Jinja2](https://img.shields.io/badge/-Jinja2-red) **Jinja2** - Template engine
- ![Passlib](https://img.shields.io/badge/-Passlib-orange) **Passlib[bcrypt]** - Mã hóa mật khẩu
- ![FastAPI-Mail](https://img.shields.io/badge/-FastAPI--Mail-blue) **FastAPI-Mail** - Gửi email
- ![Cloudinary](https://img.shields.io/badge/-Cloudinary-blue) **Cloudinary** - Upload ảnh
- ![APScheduler](https://img.shields.io/badge/-APScheduler-purple) **APScheduler** - Task scheduling

### 🎨 Frontend
- ![TailwindCSS](https://img.shields.io/badge/-TailwindCSS-38B2AC?logo=tailwind-css&logoColor=white) **TailwindCSS** - CSS framework
- ![Chart.js](https://img.shields.io/badge/-Chart.js-ff6384?logo=chart.js&logoColor=white) **Chart.js** - Biểu đồ
- ![Font Awesome](https://img.shields.io/badge/-Font_Awesome-339af0?logo=font-awesome&logoColor=white) **Font Awesome** - Icons
- ![JavaScript](https://img.shields.io/badge/-Vanilla_JS-f7df1e?logo=javascript&logoColor=black) **Vanilla JavaScript** - Interactivity

## 📁 Cấu trúc dự án

```
smartcalories/
├── app/                        # Ứng dụng chính
│   ├── templates/              # HTML templates (Jinja2)
│   │   ├── index.html         # Trang chính
│   │   ├── login.html         # Đăng nhập
│   │   ├── register.html      # Đăng ký
│   │   ├── forgot-password.html
│   │   └── reset-password.html
│   ├── static/                # Tài nguyên tĩnh
│   │   ├── logo.png          # Logo ứng dụng
│   │   ├── favicon.ico       # Icon trang web
│   │   ├── default-avatar.png
│   │   └── chart-draw.js     # Script biểu đồ
│   ├── database.py           # Kết nối MongoDB
│   └── main.py              # FastAPI app & routes
├── requirements.txt         # Dependencies
├── README.md               # Tài liệu
└── .env.example           # Mẫu cấu hình
```

## 🖼️ Screenshots

<div align="center">

### 🏠 Trang chủ
<img src="/assets/home-preview.png" width="800" alt="Trang chủ SmartCalories">

### 📊 Phân tích dinh dưỡng
<img src="/assets/analytics-preview.png" width="800" alt="Phân tích dinh dưỡng">

### 📱 Giao diện mobile
<img src="/assets/mobile-preview.png" width="400" alt="Giao diện mobile">

</div>

## 🎯 Hướng dẫn sử dụng

### 👤 Người dùng mới
1. **Đăng ký tài khoản** với thông tin cá nhân
2. **Cập nhật profile** (chiều cao, cân nặng, tuổi)
3. **Thêm món ăn** vào hệ thống
4. **Ghi nhật ký** ăn uống hàng ngày
5. **Xem phân tích** dinh dưỡng và biểu đồ

### 👨‍💼 Admin
1. **Quản lý người dùng** (xem, khóa, phân quyền)
2. **Theo dõi hoạt động** hệ thống
3. **Quản lý món ăn** toàn bộ
4. **Xem báo cáo** tổng quan

## 📤 Xuất dữ liệu

Ứng dụng hỗ trợ xuất nhật ký ăn uống ra file CSV:

- 📅 **Xuất hôm nay**: Dữ liệu trong ngày
- 📦 **Xuất tất cả**: Toàn bộ lịch sử

## 🔧 API Endpoints

### 🔐 Authentication
- `POST /login` - Đăng nhập
- `POST /register` - Đăng ký
- `POST /forgot-password` - Quên mật khẩu
- `POST /reset-password` - Đặt lại mật khẩu
- `GET /logout` - Đăng xuất

### 🍽️ Meals Management
- `GET /meals` - Danh sách món ăn
- `POST /meals` - Thêm món ăn
- `PUT /meals/{id}` - Cập nhật món ăn
- `DELETE /meals/{id}` - Xóa món ăn

### 📝 Food Logging
- `POST /log-meal` - Ghi nhật ký
- `GET /logs` - Xem nhật ký
- `GET /export-csv` - Xuất CSV

### 👨‍💼 Admin
- `GET /users` - Quản lý người dùng
- `POST /change-role` - Phân quyền
- `GET /activity-log` - Nhật ký hoạt động

## 🤝 Đóng góp

Chúng tôi hoan nghênh mọi đóng góp! Hãy:

1. **Fork** dự án
2. **Tạo branch** mới (`git checkout -b feature/amazing-feature`)
3. **Commit** thay đổi (`git commit -m 'Add amazing feature'`)
4. **Push** lên branch (`git push origin feature/amazing-feature`)
5. **Tạo Pull Request**

## 🐛 Báo lỗi

Nếu bạn gặp lỗi, hãy tạo [Issue](https://github.com/pcq3014/food_portion_management/issues) với:
- Mô tả chi tiết lỗi
- Các bước tái hiện
- Screenshot (nếu có)
- Thông tin hệ thống

## 📝 Todo

- [ ] 🤖 Tích hợp AI để gợi ý món ăn
- [ ] 📱 Phát triển mobile app
- [ ] 🔔 Thông báo nhắc nhở
- [ ] 📊 Báo cáo nâng cao
- [ ] 🌍 Đa ngôn ngữ
- [ ] 🎨 Dark mode

## 📄 Giấy phép

Dự án được phát hành dưới giấy phép **MIT License**.

```
MIT License

Copyright (c) 2025 SmartCalories

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

## 💝 Cảm ơn

Cảm ơn các thư viện và công cụ open-source đã giúp dự án này có thể hoàn thành:
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework tuyệt vời
- [MongoDB](https://mongodb.com/) - Database linh hoạt
- [TailwindCSS](https://tailwindcss.com/) - CSS framework hiện đại
- [Chart.js](https://chartjs.org/) - Thư viện biểu đồ
- [Cloudinary](https://cloudinary.com/) - Dịch vụ upload ảnh

---

<div align="center">
  
  **⭐ Nếu bạn thấy dự án hữu ích, hãy cho chúng tôi một ngôi sao!**
  
  Được tạo với ❤️ bởi **SmartCalories Team**
  
  [![GitHub](https://img.shields.io/badge/-GitHub-181717?style=for-the-badge&logo=github)](https://github.com/pcq3014)
  [![Email](https://img.shields.io/badge/-Email-D14836?style=for-the-badge&logo=gmail&logoColor=white)](mailto:smartcalories.vn@gmail.com)
  
</div>
