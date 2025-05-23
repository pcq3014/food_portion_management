# 🥗 SmartCalories

**SmartCalories** là một ứng dụng web giúp bạn quản lý lượng calo và thành phần dinh dưỡng trong các bữa ăn hàng ngày. Ứng dụng cho phép thêm món ăn, ghi nhật ký ăn uống, phân tích dinh dưỡng và xuất dữ liệu dưới dạng CSV.

![Giao diện chính](/assets/demo.png)

---

## 🚀 Tính năng chính

- 👤 Đăng ký / đăng nhập người dùng
- 🍽️ Quản lý món ăn: thêm, sửa, xoá kèm thông tin dinh dưỡng và hình ảnh
- 🧾 Ghi nhật ký ăn uống theo ngày
- 📊 Thống kê lượng calo, protein, carbs và chất béo tiêu thụ
- 📤 Xuất dữ liệu nhật ký ra file `.csv`
- 🔐 Quản lý phiên đăng nhập bằng cookie
- 📸 Giao diện người dùng trực quan, hiện đại

---

## 🖼️ Giao diện minh họa

### 📋 Danh sách món ăn

![Danh sách món ăn](./mnt/data/321864db-3689-451d-a533-5de58e2a637b.png)

### 📈 Nhật ký & Phân tích

![Phân tích dinh dưỡng](./mnt/data/de3fc34d-35c6-4fb4-b90e-5e33aa926c2d.png)

---

## 🛠️ Cài đặt

### ✅ Yêu cầu

- Python 3.8+
- MongoDB
- pip

### 📥 Cài đặt local

```bash
git clone https://github.com/your-username/smartcalories.git
cd smartcalories
pip install -r requirements.txt
🔔 Đảm bảo MongoDB đã chạy và bạn đã cấu hình các collection:
users_col, meals_col, logs_col

🚀 Khởi chạy ứng dụng
bash
Copy
Edit
uvicorn main:app --reload
Truy cập tại: http://localhost:8000

📦 requirements.txt
txt
Copy
Edit
fastapi
uvicorn
pymongo
jinja2
python-dotenv
python-multipart
pytz
passlib[bcrypt]
🗂️ Cấu trúc thư mục
csharp
Copy
Edit
smartcalories/
├── app/
│   ├── templates/        # Giao diện HTML Jinja2
│   ├── static/           # Ảnh, CSS, JS tĩnh
│   ├── database.py       # Kết nối MongoDB
│   └── main.py           # FastAPI endpoints
├── assets/
│   └── demo.png          # Ảnh minh hoạ ứng dụng
├── requirements.txt
└── README.md
📤 Xuất CSV
Nhấn nút "Xuất CSV" tại thanh menu để tải toàn bộ nhật ký ăn uống (bao gồm họ tên, món ăn, số lượng, ngày) dưới dạng file .csv.

📄 Giấy phép
Dự án được phát hành dưới giấy phép MIT.

💡 Góp ý & Hỗ trợ
Bạn có thể tạo issue hoặc gửi pull request để cải thiện dự án. Cảm ơn bạn đã sử dụng SmartCalories!

less
Copy
Edit

---

### Gợi ý:

- Đặt ảnh bạn chụp vào thư mục `assets/` (ví dụ: `assets/ui_menu.png`, `assets/ui_analysis.png`) và sửa đường dẫn ảnh trong README tương ứng.
- Nếu bạn muốn có badges (ví dụ: Python version, License...), mình có thể thêm.

Bạn có muốn mình tạo file `README.md` hoàn chỉnh này để bạn tải luôn không?
