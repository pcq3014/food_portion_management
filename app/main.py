from fastapi import FastAPI, Request, Form, Cookie, HTTPException, Response, Query, Body
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi import UploadFile, File, status
from app.database import meals_col, logs_col, users_col
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
import secrets
from bson import ObjectId
import pytz
import csv
import io
import json
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

@app.post("/register")
def register_user(
    request: Request,
    fullname: str = Form(...),
    username: str = Form(...),
    email: str = Form(...),  # Thêm email
    password: str = Form(...),
    confirm_password: str = Form(...)
):
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
    return response

@app.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_form(request: Request):
    return templates.TemplateResponse("forgot-password.html", {"request": request})

@app.post("/forgot-password", response_class=HTMLResponse)
async def forgot_password_submit(request: Request, email: str = Form(...)):
    user = users_col.find_one({"username": email}) or users_col.find_one({"email": email})
    message = "Đặt lại mật khẩu đã được gửi vào email."
    if user:
        token = secrets.token_urlsafe(32)
        reset_tokens[token] = {
            "user_id": str(user["_id"]),
            "expires": datetime.utcnow() + timedelta(minutes=30)
        }
        reset_link = str(request.url_for('reset_password_form')) + f"?token={token}"
        email_message = MessageSchema(
            subject="Đặt lại mật khẩu SmartCalories",
            recipients=[user["email"]],
            body=f"""
                <p>Xin chào {user.get('fullname', '')},</p>
                <p>Bạn vừa yêu cầu đặt lại mật khẩu cho tài khoản SmartCalories.</p>
                <p>Nhấn vào liên kết sau để đặt lại mật khẩu (có hiệu lực trong 30 phút):<br>
                <a href="{reset_link}">{reset_link}</a></p>
                <p>Nếu bạn không yêu cầu, hãy bỏ qua email này.</p>
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

# Trang chính
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
    for meal in meals_col.find(meal_query):
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

    # ✅ Truyền fullname vào template
    users = []
    if user and user.get("role") == "admin":
        for u in users_col.find():
            u["_id"] = str(u["_id"])
            u["is_banned"] = u.get("is_banned", False)
            users.append(u)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "meals": meals,
        "logs": logs,
        "summary": summary,
        "fullname": fullname,
        "user": user,  # Thêm dòng này để Jinja2 không lỗi
        "today": today,
        "search": search,
        "goals": goals,
        "missing": missing,
        "bmr": int(bmr) if bmr else None,
        "tdee": int(tdee) if tdee else None,
        "suggested_meals": suggested_meals,
        "nutrient_priority": nutrient_priority,
        "view": view,
        "users": users
    })
# tạo favicon
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("app/static/favicon.ico")

# Các route thêm, sửa, xóa món ăn, ghi nhật ký... giữ nguyên không đổi


@app.post("/add-meal")
async def add_meal(
    name: str = Form(...),
    calories: int = Form(...),
    carbs: int = Form(...),
    protein: int = Form(...),
    fat: int = Form(...),
    image_url: str = Form(None)  
):
    meals_col.insert_one({
        "name": name,
        "calories": calories,
        "carbs": carbs,
        "protein": protein,
        "fat": fat,
        "image_url": image_url  
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
    if not user or user.get("role") != "admin":
        return JSONResponse({"error": "Bạn không có quyền xóa!"}, status_code=403)
    meals_col.delete_one({"_id": ObjectId(meal_id)})
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

# Đăng xuất
@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("user_id", path="/")
    return response
