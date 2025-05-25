from pymongo import MongoClient

# Kết nối đến MongoDB
client = MongoClient("mongodb+srv://pcq3014:bigdata@mealtracker.9ged2qc.mongodb.net/")

# Lấy database
db = client["meal_tracker"]

# Khai báo các collection
activities_col = db["activities"]
activity_logs_col = db["activity_logs"]
login_logs_col = db["login_logs"]
logs_col = db["logs"]
meals_col = db["meals"]
users_col = db["users"]
