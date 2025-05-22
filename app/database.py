from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client["meal_tracker"]
meals_col = db["meals"]
logs_col = db["logs"]
users_col = db["users"]
