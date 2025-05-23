🥗 SmartCalories

SmartCalories là một ứng dụng web giúp bạn quản lý lượng calo và thành phần dinh dưỡng trong các bữa ăn hàng ngày. Bạn có thể thêm món ăn, ghi nhật ký ăn uống, phân tích lượng calo tiêu thụ và xuất dữ liệu dưới dạng CSV.

🚀 Tính năng nổi bật
👥 Đăng ký và đăng nhập người dùng

🍽️ Thêm, sửa, xóa món ăn kèm thông tin dinh dưỡng và hình ảnh

🧾 Ghi nhật ký ăn uống theo ngày

📊 Thống kê calo, protein, carbs, và chất béo tiêu thụ hàng ngày

📤 Xuất nhật ký ăn uống ra file CSV

🔐 Quản lý phiên đăng nhập bằng cookie

📸 Giao diện người dùng

Hình ảnh minh họa giao diện chính với danh sách món ăn và phân tích dinh dưỡng.

🛠️ Cài đặt
Yêu cầu:
Python 3.8+

MongoDB

pip

Cài đặt local:
bash
Copy
Edit
git clone https://github.com/your-username/smartcalories.git
cd smartcalories
pip install -r requirements.txt
⚙️ Đảm bảo MongoDB đã khởi chạy và bạn đã cấu hình đúng các collection: users_col, meals_col, logs_col.

🔧 Khởi chạy ứng dụng
bash
Copy
Edit
uvicorn main:app --reload
Truy cập tại: http://localhost:8000

🗂️ Cấu trúc thư mục
csharp
Copy
Edit
smartcalories/
│
├── app/
│   ├── templates/          # Jinja2 HTML templates
│   ├── static/             # Ảnh, CSS, JS tĩnh
│   ├── database.py         # Kết nối MongoDB
│   └── main.py             # FastAPI routes chính
├── assets/
│   └── demo.png            # Ảnh minh họa ứng dụng
├── requirements.txt
└── README.md
📦 Xuất dữ liệu
Tại trang chính, bạn có thể nhấn "Xuất CSV" để tải toàn bộ nhật ký ăn uống (đầy đủ họ tên, món ăn, số lượng, ngày) thành một file .csv.

📃 Giấy phép
Dự án được phát hành dưới giấy phép MIT. Xem chi tiết trong LICENSE.
