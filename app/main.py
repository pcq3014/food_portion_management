from fastapi import FastAPI, Request, Form, Cookie, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from app.database import meals_col, logs_col, users_col
from bson import ObjectId
from datetime import datetime
import pytz
import csv
import io
from passlib.hash import bcrypt

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Đăng ký
@app.get("/register")
def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register_user(
    request: Request,
    fullname: str = Form(...),
    username: str = Form(...),
    password: str = Form(...)
):
    if users_col.find_one({"username": username}):
        return HTMLResponse("Tên đăng nhập đã tồn tại", status_code=400)
    
    hashed = bcrypt.hash(password)
    users_col.insert_one({
        "fullname": fullname,
        "username": username,
        "hashed_password": hashed
    })
    
    return RedirectResponse("/login", status_code=302)

# Đăng nhập
@app.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login_user(
    response: Response,
    username: str = Form(...),
    password: str = Form(...)
):
    user = users_col.find_one({"username": username})
    if not user or not bcrypt.verify(password, user["hashed_password"]):
        return HTMLResponse("Invalid login", status_code=401)
    response = RedirectResponse("/", status_code=302)
    # Set cookie bảo mật hơn
    response.set_cookie(
        key="user_id",
        value=str(user["_id"]),
        httponly=True,
        max_age=86400,  # 1 ngày
        path="/"
    )
    return response

# Hàm hỗ trợ lấy user hiện tại
def get_current_user_id(user_id: str = Cookie(None)) -> ObjectId:
    if not user_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    return ObjectId(user_id)

# Trang chính
@app.get("/", response_class=HTMLResponse)
async def home(request: Request, user_id: str = Cookie(None)):
    if not user_id:
        return RedirectResponse("/login", status_code=302)

    user_id_obj = ObjectId(user_id)
    
    # ✅ Lấy thông tin người dùng
    user = users_col.find_one({"_id": user_id_obj})
    fullname = user.get("fullname", "Người dùng") if user else "Người dùng"

    meals = []
    for meal in meals_col.find():
        meal["_id"] = str(meal["_id"])
        meals.append(meal)

    vn_tz = pytz.timezone("Asia/Ho_Chi_Minh")
    today = datetime.now(vn_tz).strftime('%Y-%m-%d')

    logs = []
    for log in logs_col.aggregate([
        {"$match": {"user_id": user_id_obj, "date": today}},
        {"$lookup": {
            "from": "meals",
            "localField": "meal_id",
            "foreignField": "_id",
            "as": "meal"
        }},
        {"$unwind": "$meal"}
    ]):
        log["_id"] = str(log["_id"])
        log["meal_id"] = str(log["meal_id"])
        log["meal"]["_id"] = str(log["meal"]["_id"])
        logs.append(log)

    summary_result = logs_col.aggregate([
        {"$match": {"user_id": user_id_obj, "date": today}},
        {"$lookup": {
            "from": "meals",
            "localField": "meal_id",
            "foreignField": "_id",
            "as": "meal"
        }},
        {"$unwind": "$meal"},
        {"$group": {
            "_id": "$date",
            "total_calories": {"$sum": {"$multiply": ["$quantity", "$meal.calories"]}},
            "total_protein": {"$sum": {"$multiply": ["$quantity", "$meal.protein"]}},
            "total_carbs": {"$sum": {"$multiply": ["$quantity", "$meal.carbs"]}},
            "total_fat": {"$sum": {"$multiply": ["$quantity", "$meal.fat"]}},
        }}
    ])
    summary = next(summary_result, {
        "total_calories": 0,
        "total_protein": 0,
        "total_carbs": 0,
        "total_fat": 0,
    })

    # ✅ Truyền fullname vào template
    return templates.TemplateResponse("index.html", {
        "request": request,
        "meals": meals,
        "logs": logs,
        "summary": summary,
        "fullname": fullname,
        "today": today
    })


# Các route thêm, sửa, xóa món ăn, ghi nhật ký... giữ nguyên không đổi


@app.post("/add-meal")
async def add_meal(
    name: str = Form(...),
    calories: int = Form(...),
    carbs: int = Form(...),
    protein: int = Form(...),
    fat: int = Form(...)
):
    meals_col.insert_one({
        "name": name,
        "calories": calories,
        "carbs": carbs,
        "protein": protein,
        "fat": fat
    })
    return RedirectResponse("/", status_code=303)


@app.post("/log-meal")
async def log_meal(
    request: Request,
    meal_id: str = Form(...),
    quantity: int = Form(...),
    date: str = Form(...),
    user_id: str = Cookie(None)
):
    if not user_id:
        return RedirectResponse("/login", status_code=302)
    logs_col.insert_one({
        "user_id": ObjectId(user_id),
        "meal_id": ObjectId(meal_id),
        "quantity": quantity,
        "date": date
    })
    return RedirectResponse("/", status_code=303)


@app.post("/edit-meal/{meal_id}")
async def update_meal(
    meal_id: str,
    name: str = Form(...),
    calories: int = Form(...),
    carbs: int = Form(...),
    protein: int = Form(...),
    fat: int = Form(...)
):
    meals_col.update_one(
        {"_id": ObjectId(meal_id)},
        {"$set": {
            "name": name,
            "calories": calories,
            "carbs": carbs,
            "protein": protein,
            "fat": fat
        }}
    )
    return RedirectResponse("/", status_code=303)

@app.post("/delete-meal/{meal_id}")
async def delete_meal(meal_id: str):
    meals_col.delete_one({"_id": ObjectId(meal_id)})
    return RedirectResponse("/", status_code=303)

@app.get("/export-csv")
def export_csv():
    pipeline = [
        {
            "$lookup": {
                "from": "users",
                "localField": "user_id",
                "foreignField": "_id",
                "as": "user"
            }
        },
        {"$unwind": "$user"},
        {
            "$lookup": {
                "from": "meals",
                "localField": "meal_id",
                "foreignField": "_id",
                "as": "meal"
            }
        },
        {"$unwind": "$meal"},
        {
            "$project": {
                "fullname": "$user.fullname",
                "meal_name": "$meal.name",
                "quantity": 1,
                "date": 1
            }
        }
    ]
    logs = logs_col.aggregate(pipeline)

    # Sử dụng StringIO để ghi CSV, sau đó encode sang bytes
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Họ tên", "Tên món ăn", "Số lượng", "Ngày"])
    for log in logs:
        writer.writerow([
            log.get("fullname", ""),
            log.get("meal_name", ""),
            log.get("quantity", 0),
            log.get("date", "")
        ])
    csv_content = output.getvalue().encode('utf-8-sig')
    output.close()

    return StreamingResponse(
        io.BytesIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=log_data.csv"}
    )

# Đăng xuất
@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("user_id", path="/")
    return response
