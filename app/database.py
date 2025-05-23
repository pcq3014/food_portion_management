from pymongo import MongoClient

client = MongoClient("mongodb+srv://pcq301:bigdata@mealtracker.9ged2qc.mongodb.net/")
db = client["meal_tracker"]
meals_col = db["meals"]
logs_col = db["logs"]
users_col = db["users"]
