<p align="center"> <img src="/assets/icon.png" width="120"> </p> <h1 align="center">🥗 SmartCalories</h1> <p align="center"> <strong>Ứng dụng quản lý khẩu phần ăn và phân tích dinh dưỡng hằng ngày</strong><br> <a href="https://nhat-ky-an-uong.onrender.com/" target="_blank"><strong>🌐 Truy cập bản demo</strong></a> </p> <p align="center"> <img src="https://img.shields.io/badge/Python-3.8+-blue?logo=python"> <img src="https://img.shields.io/badge/FastAPI-Framework-0ba360?logo=fastapi"> <img src="https://img.shields.io/badge/MongoDB-Database-green?logo=mongodb"> </p>
🚀 Tính năng chính
👤 Đăng ký / đăng nhập người dùng

🍽️ Quản lý món ăn: thêm, sửa, xoá kèm thông tin dinh dưỡng và hình ảnh

🧾 Ghi nhật ký ăn uống theo ngày

📊 Thống kê lượng calo, protein, carbs và chất béo tiêu thụ

📤 Xuất dữ liệu nhật ký ra file .csv

🔐 Quản lý phiên đăng nhập bằng cookie

📸 Giao diện người dùng trực quan, hiện đại

🖥️ Truy cập nhanh
🔗 Demo Online: https://nhat-ky-an-uong.onrender.com/

🖼️ Giao diện minh họa
📋 Danh sách món ăn
<p align="center"><img src="/assets/demo.png" width="600"></p>
📈 Nhật ký & Phân tích
<p align="center"><img src="/assets/analysis.png" width="600"></p>
🛠️ Cài đặt
✅ Yêu cầu
Python 3.8+

MongoDB

pip

📥 Cài đặt local
bash
Copy
Edit
git clone https://github.com/your-username/smartcalories.git
cd smartcalories
pip install -r requirements.txt
🔔 Đảm bảo MongoDB đã chạy và bạn đã cấu hình các collection:
users_col, meals_col, logs_col

bash
Copy
Edit
uvicorn main:app --reload
🖥️ Truy cập tại: http://localhost:8000

📦 Thư viện sử dụng
css
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
📂 Cấu trúc thư mục
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
│   └── demo.png
├── requirements.txt
└── README.md
📤 Xuất CSV
Chọn "Xuất CSV" tại thanh menu để tải toàn bộ nhật ký ăn uống (họ tên, món ăn, số lượng, ngày) dưới dạng file .csv.

📄 Giấy phép
Phát hành dưới giấy phép MIT.

💡 Góp ý & Hỗ trợ
Bạn có thể tạo issue hoặc gửi pull request để cải thiện dự án.
Cảm ơn bạn đã sử dụng SmartCalories!
