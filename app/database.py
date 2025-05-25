from dotenv import load_dotenv
import os
from pymongo import MongoClient

load_dotenv()
# Đọc biến môi trường từ file .env
MONGO_URI = os.getenv("MONGO_URI")

# Kết nối đến MongoDB
client = MongoClient(MONGO_URI)

# Lấy database
db = client["meal_tracker"]

# Khai báo các collection
activities_col = db["activities"]
activity_logs_col = db["activity_logs"]
login_logs_col = db["login_logs"]
logs_col = db["logs"]
meals_col = db["meals"]
users_col = db["users"]
