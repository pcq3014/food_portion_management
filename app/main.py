from fastapi import FastAPI, Request, Form, Cookie, HTTPException, Response, Query, Body
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi import UploadFile, File
from threading import Lock
from dotenv import load_dotenv
import os
from app.database import meals_col, logs_col, users_col, activities_col
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from apscheduler.schedulers.background import BackgroundScheduler
import google.generativeai as genai
import secrets
from bson import ObjectId
import threading
import pytz
import csv
import io
import json
import time
from passlib.hash import bcrypt
from datetime import datetime, timedelta
import cloudinary
import cloudinary.uploader

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Đăng ký
@app.get("/register")
def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

last_register_time = {}
register_lock = Lock()
def is_too_fast(user, action, seconds=3):
    now = time.time()
    last_time = user.get(f"last_{action}_time", 0)
    if now - last_time < seconds:
        return True
    users_col.update_one({"_id": user["_id"]}, {"$set": {f"last_{action}_time": now}})
    return False
@app.post("/register")
def register_user(
    request: Request,
    fullname: str = Form(...),
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    with register_lock:
        last_time = last_register_time.get(client_ip, 0)
        if now - last_time < 3:
            return templates.TemplateResponse("register.html", {
                "request": request,
                "error": "Vui lòng chờ vài giây rồi thử lại.",
                "fullname": fullname,
                "username": username,
                "email": email
            }, status_code=429)
        last_register_time[client_ip] = now

    if password != confirm_password:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Mật khẩu không khớp",
            "fullname": fullname,
            "username": username,
            "email": email
        }, status_code=400)

    if users_col.find_one({"username": username}):
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Tên đăng nhập đã tồn tại",
            "fullname": fullname,
            "username": username,
            "email": email
        }, status_code=400)

    if users_col.find_one({"email": email}):
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Email đã được sử dụng",
            "fullname": fullname,
            "username": username,
            "email": email
        }, status_code=400)

    user_count = users_col.count_documents({})
    role = "admin" if user_count < 3 else "user"
    hashed = bcrypt.hash(password)
    users_col.insert_one({
        "fullname": fullname,
        "username": username,
        "email": email,  # Lưu email
        "hashed_password": hashed,
        "role": role
    })

    return RedirectResponse("/login", status_code=302)


# Đăng nhập
@app.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

def log_login_async(db, user_fullname, ip, time_str):
    def task():
        db["login_logs"].insert_one({
            "time": time_str,
            "user": user_fullname,
            "ip": ip
        })
    threading.Thread(target=task, daemon=True).start()

@app.post("/login")
def login_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    user = users_col.find_one({"username": username})
    if not user or not bcrypt.verify(password, user["hashed_password"]):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Tên đăng nhập hoặc mật khẩu không đúng"
            },
            status_code=401
        )
    if user.get("is_banned", False):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Tài khoản của bạn đã bị khóa. Vui lòng liên hệ quản trị viên."
            },
            status_code=403
        )

    session_token = secrets.token_urlsafe(16)
    users_col.update_one({"_id": user["_id"]}, {"$set": {"session_token": session_token}})
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(
        key="user_id",
        value=str(user["_id"]),
        httponly=True,
        max_age=86400,
        path="/"
    )
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        max_age=86400,
        path="/"
    )
    # Ghi log đăng nhập với giờ Việt Nam (bất đồng bộ)
    vn_tz = pytz.timezone("Asia/Ho_Chi_Minh")
    now_vn = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(vn_tz)
    db = meals_col.database
    log_login_async(
        db,
        user.get("fullname", ""),
        request.client.host if request.client else "",
        now_vn.strftime("%Y-%m-%d %H:%M:%S")
    )
    return response
reset_tokens = {}

@app.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_form(request: Request):
    return templates.TemplateResponse("forgot-password.html", {"request": request})

@app.post("/forgot-password", response_class=HTMLResponse)
async def forgot_password_submit(request: Request, email: str = Form(...)):
    user = users_col.find_one({"username": email}) or users_col.find_one({"email": email})
    
    # Luôn trả về cùng một thông điệp để đảm bảo tính bảo mật
    message = "Đặt lại mật khẩu đã được gửi vào email."

    if user:
        token = secrets.token_urlsafe(32)
        reset_tokens[token] = {
            "user_id": str(user["_id"]),
            "expires": datetime.utcnow() + timedelta(minutes=30)
        }

        reset_link = str(request.url_for('reset_password_form')) + f"?token={token}"

        email_message = MessageSchema(
            subject="Yêu cầu đặt lại mật khẩu - SmartCalories",
            recipients=[user["email"]],
            body=f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 0;">
      <tr>
        <td align="center" style="padding: 40px 0;">
          <!-- Không có logo -->
          <table width="420" cellpadding="0" cellspacing="0" style="background: #fff; border-radius: 12px; box-shadow: 0 2px 8px #0001;">
            <tr>
              <td style="padding: 32px 32px 16px 32px;">
                <h2 style="color: #FF6F61; margin: 0 0 16px 0; text-align:center;">Đặt lại mật khẩu</h2>
                <p style="font-size: 16px; color: #222;">Xin chào <strong>{user.get('fullname', '')}</strong>,</p>
                <p style="font-size: 15px; color: #444;">Bạn vừa yêu cầu đặt lại mật khẩu cho tài khoản SmartCalories.</p>
                <p style="font-size: 15px; color: #444;">Nhấn vào nút bên dưới để đặt lại mật khẩu (liên kết có hiệu lực trong 30 phút):</p>
                <div style="text-align: center; margin: 28px 0;">
                  <a href="{reset_link}" style="background: linear-gradient(90deg,#FF6F61,#FF8A80); color: #fff; padding: 14px 32px; border-radius: 6px; font-size: 16px; text-decoration: none; font-weight: bold; letter-spacing: 1px; display: inline-block;">Đặt lại mật khẩu</a>
                </div>
                <p style="font-size: 14px; color: #888;">Nếu bạn không yêu cầu điều này, vui lòng bỏ qua email.</p>
                <p style="font-size: 14px; color: #888; margin-top: 32px;">Trân trọng,<br>Đội ngũ <span style="color:#FF6F61;font-weight:bold;">SmartCalories</span></p>
              </td>
            </tr>
            <tr>
              <td style="background: #f4f4f4; color: #888; text-align: center; font-size: 12px; padding: 18px 0; border-radius: 0 0 12px 12px;">
                © 2025 SmartCalories. Mọi quyền được bảo lưu.
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
    """,
            subtype="html"
        )

        fm = FastMail(conf)
        await fm.send_message(email_message)

    return templates.TemplateResponse(
        "forgot-password.html",
        {"request": request, "message": message}
    )

@app.get("/reset-password", response_class=HTMLResponse)
def reset_password_form(request: Request, token: str = ""):
    info = reset_tokens.get(token)
    if not info or info["expires"] < datetime.utcnow():
        return templates.TemplateResponse(
            "forgot-password.html",
            {"request": request, "message": "Liên kết không hợp lệ hoặc đã hết hạn."}
        )
    return templates.TemplateResponse("reset-password.html", {"request": request, "token": token})

@app.post("/reset-password", response_class=HTMLResponse)
def reset_password_submit(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...)
):
    info = reset_tokens.get(token)
    if not info or info["expires"] < datetime.utcnow():
        return templates.TemplateResponse(
            "forgot-password.html",
            {"request": request, "message": "Liên kết không hợp lệ hoặc đã hết hạn."}
        )
    if password != confirm_password:
        return templates.TemplateResponse(
            "reset-password.html",
            {"request": request, "token": token, "error": "Mật khẩu không khớp"}
        )
    users_col.update_one(
        {"_id": ObjectId(info["user_id"])},
        {"$set": {"hashed_password": bcrypt.hash(password)}}
    )
    del reset_tokens[token]
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "message": "Đặt lại mật khẩu thành công, hãy đăng nhập lại!"}
    )

conf = ConnectionConfig(
    MAIL_USERNAME="pcq30012004@gmail.com",
    MAIL_PASSWORD="gnxc lyya fvuq aokl",
    MAIL_FROM="pcq30012004@gmail.com",
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,      # Đúng tên biến
    MAIL_SSL_TLS=False,      # Đúng tên biến
    USE_CREDENTIALS=True
)

# Hàm hỗ trợ lấy user hiện tại
def get_current_user_id(user_id: str = Cookie(None)) -> ObjectId:
    if not user_id:
        raise HTTPException(status_code=401, detail="Not logged in")
    return ObjectId(user_id)

def fix_objectid(obj):
    if isinstance(obj, list):
        return [fix_objectid(item) for item in obj]
    if isinstance(obj, dict):
        return {k: (str(v) if isinstance(v, ObjectId) else fix_objectid(v)) for k, v in obj.items()}
    return obj

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def home(
    request: Request,
    user_id: str = Cookie(None),
    session_token: str = Cookie(None),
    search: str = Query("", alias="search"),
    view: str = Query("", alias="view"),
    goals: str = Cookie(None)
):
    if not user_id:
        return RedirectResponse("/login", status_code=302)

    user_id_obj = ObjectId(user_id)
    user = users_col.find_one({"_id": user_id_obj})
    if user:
        user = fix_objectid(user)
    fullname = user.get("fullname", "Người dùng") if user else "Người dùng"
    
    # Kiểm tra session_token và trạng thái ban
    if not user or user.get("is_banned", False):
        response = RedirectResponse("/login", status_code=302)
        response.delete_cookie("user_id", path="/")
        response.delete_cookie("session_token", path="/")
        response.set_cookie("logout_reason", "ban", path="/")
        return response
    if session_token != user.get("session_token"):
        response = RedirectResponse("/login", status_code=302)
        response.delete_cookie("user_id", path="/")
        response.delete_cookie("session_token", path="/")
        response.set_cookie("logout_reason", "other_login", path="/")
        return response

    bmr = tdee = None
    if user and all(k in user for k in ("weight", "height", "age", "gender")):
        bmr = calculate_bmr(user["weight"], user["height"], user["age"], user["gender"])
        tdee = calculate_tdee(bmr)
    
    # Lọc món ăn theo tên nếu có search
    meals = []
    meal_query = {}
    if search:
        meal_query["name"] = {"$regex": search, "$options": "i"}
    meals = [fix_objectid(meal) for meal in meals_col.find(meal_query)]

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
        logs.append(fix_objectid(log))

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
    # Lấy mục tiêu từ cookie nếu có
    default_goals = {
        "calories": int(tdee) if tdee else 2000,
        "protein": 100,
        "carbs": 250,
        "fat": 60
    }
    if goals:
        try:
            goals_dict = json.loads(goals)
            goals = {**default_goals, **goals_dict}
        except Exception:
            goals = default_goals
    else:
        goals = default_goals

    # Tính lượng còn thiếu
    missing = {
        "calories": max(goals["calories"] - summary.get("total_calories", 0), 0),
        "protein": max(goals["protein"] - summary.get("total_protein", 0), 0),
        "carbs": max(goals["carbs"] - summary.get("total_carbs", 0), 0),
        "fat": max(goals["fat"] - summary.get("total_fat", 0), 0),
    }

    # Gợi ý món ăn
    nutrient_priority = max(missing, key=missing.get)
    suggested_meals = sorted(
        meals,
        key=lambda m: m.get(nutrient_priority, 0),
        reverse=True
    )[:3]

    # Lấy danh sách hoạt động thể chất
    activities = []
    activities = [fix_objectid(act) for act in activities_col.find({"user_id": user_id_obj})]


    # Lấy danh sách user cho admin
    users = []
    if user and user.get("role") == "admin":
        for u in users_col.find():
            u = fix_objectid(u)
            u["is_banned"] = u.get("is_banned", False)
            users.append(u)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "meals": meals,
        "logs": logs,
        "summary": summary,
        "fullname": fullname,
        "user": user,
        "today": today,
        "search": search,
        "goals": goals,
        "missing": missing,
        "bmr": int(bmr) if bmr else None,
        "tdee": int(tdee) if tdee else None,
        "suggested_meals": suggested_meals,
        "nutrient_priority": nutrient_priority,
        "view": view,
        "users": users,
        "activities": activities,
    })
# tạo favicon
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("app/static/favicon.ico")

# Các route thêm, sửa, xóa món ăn, ghi nhật ký... giữ nguyên không đổi

activity_met_table = {
    "walking": 3.5,
    "running": 7.5,
    "cycling": 6.8,
    "swimming": 8.0,
    "yoga": 2.5,
    "weightlifting": 3.0,
    "jumping_rope": 10.0,
}
def calculate_burned_calories(weight_kg: float, duration_min: float, met: float) -> float:
    return round(met * weight_kg * (duration_min / 60.0), 2)

# Hiển thị form nhập hoạt động thể chất
@app.get("/activity", response_class=HTMLResponse)
def activity_form(request: Request, user_id: str = Cookie(None)):
    if not user_id:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("activity.html", {
        "request": request,
        "activities": activity_met_table.keys()
    })

@app.post("/activity")
async def add_activity(
    request: Request,
    activity: str = Form(...),
    duration: int = Form(...),
    user_id: str = Cookie(None)
):
    if not user_id:
        return JSONResponse({"error": "Chưa đăng nhập"}, status_code=401)
    user = users_col.find_one({"_id": ObjectId(user_id)})
    if is_too_fast(user, "activity"):
        return JSONResponse({"error": "Bạn thao tác quá nhanh, vui lòng thử lại sau."}, status_code=429)
    if not user:
        return JSONResponse({"error": "Không tìm thấy user"}, status_code=404)
    weight = user.get("weight", 60)
    met = activity_met_table.get(activity)
    if not met:
        return JSONResponse({"error": "Hoạt động không hợp lệ"}, status_code=400)
    calories_burned = calculate_burned_calories(weight, duration, met)
    vn_tz = pytz.timezone("Asia/Ho_Chi_Minh")
    now_vn = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(vn_tz)
    activities_col.insert_one({
        "user_id": ObjectId(user_id),
        "fullname": user.get("fullname", ""), 
        "activity": activity,
        "duration": duration,
        "calories_burned": calories_burned,
        "timestamp": now_vn.strftime("%Y-%m-%d %H:%M:%S")
    })
    return {"success": True, "calories_burned": calories_burned}

@app.get("/activity-history")
async def activity_history(user_id: str = Cookie(None)):
    if not user_id:
        return JSONResponse({"error": "Chưa đăng nhập"}, status_code=401)

    activities = list(activities_col.find({"user_id": ObjectId(user_id)}).sort("timestamp", -1).limit(30))

    # Sửa toàn bộ ObjectId trong document
    activities = [fix_objectid(act) for act in activities]

    result = [
        {
            "fullname": act.get("fullname", ""),
            "activity": act.get("activity", ""),
            "timestamp": format_vn_datetime(act.get("timestamp", "")),
            "calories_burned": act.get("calories_burned", 0)
        }
        for act in activities
    ]
    return JSONResponse(result)


def format_vn_datetime(dt_str):
    # dt_str dạng "YYYY-MM-DD HH:MM:SS"
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%H:%M %d/%m/%Y")
    except Exception:
        return dt_str

def format_vn_datetime(dt_str):
    # dt_str dạng "YYYY-MM-DD HH:MM:SS"
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%H:%M %d/%m/%Y")
    except Exception:
        return dt_str

@app.post("/add-meal")
async def add_meal(
    name: str = Form(...),
    calories: int = Form(...),
    carbs: int = Form(...),
    protein: int = Form(...),
    fat: int = Form(...),
    image_url: str = Form(None),
    user_id: str = Cookie(None)
):
    user = users_col.find_one({"_id": ObjectId(user_id)}) if user_id else None
    if user and is_too_fast(user, "add_meal"):
        return RedirectResponse(url="/?view=meals&error=double_click", status_code=303)
    fullname = user.get("fullname", "") if user else ""
    meals_col.insert_one({
        "name": name,
        "calories": calories,
        "carbs": carbs,
        "protein": protein,
        "fat": fat,
        "image_url": image_url,
        "created_by": fullname
    })
    # Ghi log hoạt động
    db = meals_col.database
    db["activity_logs"].insert_one({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user": fullname,
        "action": f"Thêm món ăn: {name}"
    })
    return RedirectResponse(url="/?view=meals", status_code=303)


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
    # --- Chống double-click ---
    user = users_col.find_one({"_id": ObjectId(user_id)})
    now = datetime.utcnow()
    last_log = user.get("last_log_meal_time")
    if last_log:
        if isinstance(last_log, str):
            last_log = datetime.strptime(last_log, "%Y-%m-%d %H:%M:%S")
        if now - last_log < timedelta(seconds=3):
            # Nếu thao tác quá nhanh, từ chối
            return RedirectResponse(url="/?view=log&error=double_click", status_code=303)
    users_col.update_one({"_id": ObjectId(user_id)}, {"$set": {"last_log_meal_time": now.strftime("%Y-%m-%d %H:%M:%S")}})
    # --- End chống double-click ---
    logs_col.insert_one({
        "user_id": ObjectId(user_id),
        "meal_id": ObjectId(meal_id),
        "quantity": quantity,
        "date": date
    })
    return RedirectResponse(url="/?view=log", status_code=303)

@app.post("/set-goals")
async def set_goals(
    request: Request,
    response: Response,
    calories: int = Form(...),
    protein: int = Form(...),
    carbs: int = Form(...),
    fat: int = Form(...),
    user_id: str = Cookie(None)
):
    goals = {
        "calories": calories,
        "protein": protein,
        "carbs": carbs,
        "fat": fat
    }
    response.set_cookie(
        key="goals",
        value=json.dumps(goals, ensure_ascii=False),
        max_age=60 * 60 * 24 * 30,
        path="/"
    )

    # Lấy tổng hôm nay
    vn_tz = pytz.timezone("Asia/Ho_Chi_Minh")
    today = datetime.now(vn_tz).strftime('%Y-%m-%d')
    summary_result = logs_col.aggregate([
        {"$match": {"user_id": ObjectId(user_id), "date": today}},
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

    missing = {
        "calories": max(calories - summary.get("total_calories", 0), 0),
        "protein": max(protein - summary.get("total_protein", 0), 0),
        "carbs": max(carbs - summary.get("total_carbs", 0), 0),
        "fat": max(fat - summary.get("total_fat", 0), 0),
    }

    # Lấy tất cả món ăn
    meals = list(meals_col.find())
    for m in meals:
        m["_id"] = str(m["_id"])

    # Tính gợi ý: chỉ món nào có lượng phù hợp với phần còn thiếu (trong khoảng 30% đến 100%)
    suggested_by_nutrient = {}
    for nutrient in ["calories", "protein", "carbs", "fat"]:
        target = missing[nutrient]
        lower = target * 0.3
        upper = target * 1.1
        filtered = [m for m in meals if lower <= m.get(nutrient, 0) <= upper]
        suggested_by_nutrient[nutrient] = sorted(
            filtered, key=lambda m: abs(m.get(nutrient, 0) - target)
        )[:3]

    return JSONResponse({
        "goals": goals,
        "missing": missing,
        "suggested_meals": suggested_by_nutrient
    })

cloudinary.config(
    cloud_name="df4esejf8",
    api_key="673739585779132",
    api_secret="_s-PaBNgEJuBLdtRrRE62gQm4n0"
)

@app.post("/edit-meal/{meal_id}")
async def update_meal(
    meal_id: str,
    name: str = Form(...),
    calories: int = Form(...),
    carbs: int = Form(...),
    protein: int = Form(...),
    fat: int = Form(...),
    image_url: str = Form(None)  
):
    meals_col.update_one(
        {"_id": ObjectId(meal_id)},
        {"$set": {
            "name": name,
            "calories": calories,
            "carbs": carbs,
            "protein": protein,
            "fat": fat,
            "image_url": image_url  
        }}
    )
    return RedirectResponse(url="/?view=meals", status_code=303)

@app.post("/delete-meal/{meal_id}")
async def delete_meal(meal_id: str, user_id: str = Cookie(None)):
    if not user_id:
        return RedirectResponse("/login", status_code=302)
    user = users_col.find_one({"_id": ObjectId(user_id)})
    fullname = user.get("fullname", "") if user else ""
    if not user or user.get("role") != "admin":
        return JSONResponse({"error": "Bạn không có quyền xóa!"}, status_code=403)
    meal = meals_col.find_one({"_id": ObjectId(meal_id)})  # Lấy thông tin món ăn trước khi xóa
    meals_col.delete_one({"_id": ObjectId(meal_id)})
    # Ghi log hoạt động
    db = meals_col.database
    db["activity_logs"].insert_one({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user": fullname,
        "action": f"Xóa món ăn: {meal.get('name', '') if meal else meal_id}"
    })
    return RedirectResponse(url="/?view=meals", status_code=303)

# Hàm tính BMR/TDEE
def calculate_bmr(weight, height, age, gender):
    if gender == "male":
        return 88.36 + (13.4 * weight) + (4.8 * height) - (5.7 * age)
    else:
        return 447.6 + (9.2 * weight) + (3.1 * height) - (4.3 * age)

def calculate_tdee(bmr, activity_level=1.55):
    return int(bmr * activity_level)

# Trang thông tin cá nhân
@app.post("/profile")
async def update_profile(
    request: Request,
    height: int = Form(...),
    weight: int = Form(...),
    age: int = Form(...),
    gender: str = Form(...),
    email: str = Form(...),
    avatar_file: UploadFile = File(None),
    user_id: str = Cookie(None)
):
    if not user_id:
        return JSONResponse({"success": False, "message": "Chưa đăng nhập"}, status_code=401)

    user = users_col.find_one({"_id": ObjectId(user_id)})
    if users_col.find_one({"email": email, "_id": {"$ne": ObjectId(user_id)}}):
        return JSONResponse({"success": False, "message": "Email đã được sử dụng!"}, status_code=400)

    avatar_url = ""
    if avatar_file:
        # Upload lên Cloudinary
        result = cloudinary.uploader.upload(await avatar_file.read(), folder="avatars")
        avatar_url = result["secure_url"]

    update_data = {
        "height": height,
        "weight": weight,
        "age": age,
        "gender": gender,
        "email": email
    }
    if avatar_url:
        update_data["avatar_url"] = avatar_url

    users_col.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_data}
    )

    bmr = calculate_bmr(weight, height, age, gender)
    tdee = calculate_tdee(bmr)
    return JSONResponse({
        "success": True,
        "message": "Cập nhật thông tin thành công!",
        "data": {
            "height": height,
            "weight": weight,
            "age": age,
            "gender": gender,
            "email": email,
            "avatar_url": avatar_url,
            "bmr": int(bmr),
            "tdee": int(tdee)
        }
    })

@app.post("/ban-user")
async def ban_user(
    request: Request,
    user_id: str = Cookie(None),
    data: dict = Body(...)
):
    if not user_id:
        return JSONResponse({"success": False, "message": "Chưa đăng nhập"})
    admin = users_col.find_one({"_id": ObjectId(user_id)})
    if not admin or admin.get("role") != "admin":
        return JSONResponse({"success": False, "message": "Bạn không có quyền"})
    target_id = data.get("user_id")
    ban = data.get("ban")
    if not target_id:
        return JSONResponse({"success": False, "message": "Thiếu user_id"})
    if str(target_id) == str(user_id):
        return JSONResponse({"success": False, "message": "Không thể tự ban chính mình!"})

    result = users_col.update_one(
        {"_id": ObjectId(target_id)},
        {"$set": {"is_banned": bool(ban)}}
    )
    if result.modified_count == 1:
        msg = "Đã khóa tài khoản!" if ban else "Đã mở khóa tài khoản!"
        return JSONResponse({"success": True, "message": msg})
    else:
        return JSONResponse({"success": False, "message": "Không tìm thấy user hoặc không thay đổi"})

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))  

@app.post("/chatbot")
async def chatbot_endpoint(request: Request):
    data = await request.json()
    messages = data.get("messages", [])
    meals = data.get("meals", [])
    logs = data.get("logs", [])
    summary = data.get("summary", {})
    activities = data.get("activities", [])

    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("models/gemini-1.5-flash-latest")
        meal_list = "\n".join([f"- {m['name']} (Calories: {m['calories']}, Protein: {m['protein']}g, Carbs: {m['carbs']}g, Fat: {m['fat']}g)" for m in meals])
        log_list = "\n".join([f"- {l['meal']['name']} x{l['quantity']} ({l['meal']['calories']*l['quantity']} cal)" for l in logs])
        activity_list = "\n".join([f"- {a['activity']} {a['duration']} phút ({a['calories_burned']} kcal)" for a in activities])
        summary_text = f"Tổng hôm nay: {summary.get('calories', 0)} cal, {summary.get('protein', 0)}g protein, {summary.get('carbs', 0)}g carbs, {summary.get('fat', 0)}g fat."

        prompt = (
            "Bạn là trợ lý dinh dưỡng SmartCalories, hãy xưng hô thân thiện là 'bạn' với người dùng.\n"
            "Danh sách món ăn hiện có:\n" + meal_list +
            "\n---\nNhật ký hôm nay:\n" + log_list +
            "\n---\nPhân tích hôm nay:\n" + summary_text +
            "\n---\nHoạt động thể chất hôm nay:\n" + activity_list +
            "\n---\n"
            + "\n".join([m.get("content", "") for m in messages])
        )
        response = model.generate_content(prompt)
        reply = response.text
        return JSONResponse({"reply": reply})
    except Exception as e:
        print("Lỗi gọi Gemini API:", e)
        return JSONResponse({"reply": "Xin lỗi, có lỗi xảy ra."})

@app.get("/export-csv")
def export_csv(
    request: Request,
    mode: str = "today",
    user_id: str = Cookie(None)
):
    if not user_id:
        return RedirectResponse("/login", status_code=302)

    user_obj_id = ObjectId(user_id)
    vn_tz = pytz.timezone("Asia/Ho_Chi_Minh")
    today = datetime.now(vn_tz).strftime('%Y-%m-%d')

    match_stage = {"user_id": user_obj_id}
    if mode == "today":
        match_stage["date"] = today

    pipeline = [
        {"$match": match_stage},
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

    filename = f"log_data_{today}.csv" if mode == "today" else "log_data_all.csv"

    return StreamingResponse(
        io.BytesIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

#Đổi quyền người dùng
@app.post("/change-role")
async def change_role(
    request: Request,
    user_id: str = Cookie(None),
    data: dict = Body(...)
):
    # Kiểm tra đăng nhập
    if not user_id:
        return JSONResponse({"success": False, "message": "Chưa đăng nhập"})
    admin = users_col.find_one({"_id": ObjectId(user_id)})
    if not admin or admin.get("role") != "admin":
        return JSONResponse({"success": False, "message": "Bạn không có quyền"})
    target_id = data.get("user_id")
    new_role = data.get("role")
    if not target_id or not new_role:
        return JSONResponse({"success": False, "message": "Thiếu thông tin"})
    if str(target_id) == str(user_id):
        return JSONResponse({"success": False, "message": "Không thể đổi quyền chính mình!"})
    user = users_col.find_one({"_id": ObjectId(target_id)})
    if not user:
        return JSONResponse({"success": False, "message": "Không tìm thấy user!"})
    users_col.update_one({"_id": ObjectId(target_id)}, {"$set": {"role": new_role}})
    return JSONResponse({"success": True, "message": "Đã đổi quyền thành công!"})

@app.post("/delete-user")
async def delete_user(
    request: Request,
    user_id: str = Cookie(None),
    data: dict = Body(...)
):
    # Kiểm tra đăng nhập và quyền admin
    if not user_id:
        return JSONResponse({"success": False, "message": "Chưa đăng nhập"})
    admin = users_col.find_one({"_id": ObjectId(user_id)})
    if not admin or admin.get("role") != "admin":
        return JSONResponse({"success": False, "message": "Bạn không có quyền"})
    target_id = data.get("user_id")
    if not target_id:
        return JSONResponse({"success": False, "message": "Thiếu user_id"})
    if str(target_id) == str(user_id):
        return JSONResponse({"success": False, "message": "Không thể tự xóa chính mình!"})
    result = users_col.delete_one({"_id": ObjectId(target_id)})
    if result.deleted_count == 1:
        return JSONResponse({"success": True, "message": "Đã xóa người dùng thành công!"})
    else:
        return JSONResponse({"success": False, "message": "Không tìm thấy user hoặc không xóa được!"})

@app.get("/activity-log", response_class=HTMLResponse)
async def activity_log(request: Request, user_id: str = Cookie(None)):
    # Chỉ cho admin xem
    if not user_id:
        return HTMLResponse("<div class='text-red-500'>Chưa đăng nhập</div>")
    user = users_col.find_one({"_id": ObjectId(user_id)})
    if not user or user.get("role") != "admin":
        return HTMLResponse("<div class='text-red-500'>Bạn không có quyền xem nhật ký này</div>")
    # Lấy database từ một collection bất kỳ
    db = meals_col.database
    logs = []
    if "activity_logs" in db.list_collection_names():
        logs = list(db["activity_logs"].find().sort("time", -1).limit(50))
    if not logs:
        return HTMLResponse("<div class='text-gray-500'>Chưa có nhật ký hoạt động nào.</div>")
    html = "<table class='min-w-full text-sm'><thead><tr><th>Thời gian</th><th>Người dùng</th><th>Hành động</th></tr></thead><tbody>"
    for log in logs:
        html += f"<tr><td>{log.get('time','')}</td><td>{log.get('user','')}</td><td>{log.get('action','')}</td></tr>"
    html += "</tbody></table>"
    return HTMLResponse(html)

@app.get("/login-log", response_class=HTMLResponse)
async def login_log(request: Request, user_id: str = Cookie(None)):
    # Chỉ cho admin xem
    if not user_id:
        return HTMLResponse("<div class='text-red-500'>Chưa đăng nhập</div>")
    user = users_col.find_one({"_id": ObjectId(user_id)})
    if not user or user.get("role") != "admin":
        return HTMLResponse("<div class='text-red-500'>Bạn không có quyền xem nhật ký này</div>")
    db = meals_col.database
    logs = []
    if "login_logs" in db.list_collection_names():
        logs = list(db["login_logs"].find().sort("time", -1).limit(50))
    if not logs:
        return HTMLResponse("<div class='text-gray-500'>Chưa có nhật ký đăng nhập nào.</div>")
    html = "<table class='min-w-full text-sm'><thead><tr><th>Thời gian</th><th>Người dùng</th><th>IP</th></tr></thead><tbody>"
    for log in logs:
        html += f"<tr><td>{log.get('time','')}</td><td>{log.get('user','')}</td><td>{log.get('ip','')}</td></tr>"
    html += "</tbody></table>"
    return HTMLResponse(html)
     
# Kiểm tra phiên đăng nhập
@app.get("/check-session")
def check_session(user_id: str = Cookie(None), session_token: str = Cookie(None)):
    if not user_id:
        return {"valid": False, "reason": "logout"}
    user = users_col.find_one({"_id": ObjectId(user_id)})
    if not user or user.get("is_banned", False):
        return {"valid": False, "reason": "ban"}
    if session_token != user.get("session_token"):
        return {"valid": False, "reason": "other_login"}
    return {"valid": True}

def reset_logs_job():
    db = meals_col.database
    db["activity_logs"].delete_many({})
    db["login_logs"].delete_many({})

scheduler = BackgroundScheduler()
scheduler.add_job(reset_logs_job, 'cron', hour=0, minute=1)  
scheduler.start()

# Đăng xuất
@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("user_id", path="/")
    return response
