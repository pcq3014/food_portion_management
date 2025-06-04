# --- 1. IMPORTS ---
import os
import re
import io
import csv
import json
import time
import pytz
import secrets
import threading
import requests 
from datetime import datetime, timedelta
from threading import Lock

from fastapi import (
    FastAPI, Request, Form, Cookie, HTTPException, Response, Query, Body, UploadFile, File
)
from fastapi.responses import (
    HTMLResponse, RedirectResponse, StreamingResponse, FileResponse, JSONResponse
)
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from dotenv import load_dotenv
from passlib.hash import bcrypt
from bson import ObjectId
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig

import cloudinary
import cloudinary.uploader
import google.generativeai as genai

from app.database import meals_col, logs_col, users_col, activities_col

# --- 2. CONFIG & GLOBALS ---

# Chạy .env để lấy biến môi trường
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Khởi tạo Cloudinary
cloudinary.config(
    cloud_name="df4esejf8",
    api_key="673739585779132",
    api_secret="_s-PaBNgEJuBLdtRrRE62gQm4n0"
)

# Cấu hình email
conf = ConnectionConfig(
    MAIL_USERNAME="smartcalories.vn@gmail.com",
    MAIL_PASSWORD="zpln zcew qcti koba",
    MAIL_FROM="smartcalories.vn@gmail.com",
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,      
    MAIL_SSL_TLS=False,     
    USE_CREDENTIALS=True
)

# Khởi tạo cache và lock
chatbot_temp_cache = {}
last_register_time = {}
register_lock = Lock()
reset_tokens = {}

# Bảng chuyển đổi hoạt động thể chất sang MET
activity_met_table = {
    "walking": 3.5,
    "running": 7.5,
    "cycling": 6.8,
    "swimming": 8.0,
    "yoga": 2.5,
    "weightlifting": 3.0,
    "jumping_rope": 10.0,
}

# Hàm tính toán lượng calo đốt cháy dựa trên MET
def fix_objectid(obj):
    if isinstance(obj, list):
        return [fix_objectid(item) for item in obj]
    if isinstance(obj, dict):
        return {k: (str(v) if isinstance(v, ObjectId) else fix_objectid(v)) for k, v in obj.items()}
    return obj

# Hàm hỗ trợ lấy user hiện tại
def get_current_user_id(user_id: str = Cookie(None)) -> ObjectId:
    if not user_id:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")
    return ObjectId(user_id)

# Kiểm tra thao tác quá nhanh
def is_too_fast(user, action, seconds=3):
    now = time.time()
    last_time = user.get(f"last_{action}_time", 0)
    if now - last_time < seconds:
        return True
    users_col.update_one({"_id": user["_id"]}, {"$set": {f"last_{action}_time": now}})
    return False

# Hàm tính BMR/TDEE
def calculate_bmr(weight, height, age, gender):
    if gender == "male":
        return 88.36 + (13.4 * weight) + (4.8 * height) - (5.7 * age)
    else:
        return 447.6 + (9.2 * weight) + (3.1 * height) - (4.3 * age)

def calculate_tdee(bmr, activity_level=1.55):
    return float(bmr * activity_level)

# Formatter thời gian Việt Nam
def format_vn_datetime(dt_str):
    # dt_str dạng "YYYY-MM-DD HH:MM:SS"
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%H:%M %d/%m/%Y")
    except Exception:
        return dt_str
    
# Hàm ghi log đăng nhập bất đồng bộ
def log_login_async(db, user_fullname, ip, time_str):
    def task():
        doc = {
            "time": time_str,
            "user": user_fullname,
            "ip": ip
        }
        db["login_logs"].insert_one(doc)  
    threading.Thread(target=task, daemon=True).start()

# --- 3. ROUTES ---

# Route đăng ký
@app.get("/register")
def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


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

# Route đăng nhập
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
    # Ghi log đăng nhập với giờ Việt Nam (bất đồng bộ)
    vn_tz = pytz.timezone("Asia/Ho_Chi_Minh")
    now_vn = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(vn_tz)
    db = meals_col.database
    log_login_async(
        db,
        user.get("fullname", ""),
        request.client.host if request.client else "",
        now_vn.strftime("%Y-%m-%d %H:%M:%S"),

    )
    return response
reset_tokens = {}

# Route đăng xuất
@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("user_id", path="/")
    return response

# Route quên mật khẩu
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
            subject="🔐 Yêu cầu đặt lại mật khẩu - SmartCalories",
            recipients=[user["email"]],
            body=f"""
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Đặt lại mật khẩu - SmartCalories</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 40px 20px;
        }}
        
        .email-card {{
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            border-radius: 24px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.1), 0 8px 32px rgba(0, 0, 0, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.2);
            overflow: hidden;
            position: relative;
        }}
        
        .email-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #667eea, #764ba2, #667eea);
            background-size: 200% 100%;
            animation: shimmer 3s ease-in-out infinite;
        }}
        
        @keyframes shimmer {{
            0%, 100% {{ background-position: 0% 50%; }}
            50% {{ background-position: 100% 50%; }}
        }}
        
        .header {{
            text-align: center;
            padding: 48px 40px 32px;
            background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
            border-bottom: 1px solid rgba(226, 232, 240, 0.5);
        }}
        
        .logo-container {{
            display: inline-block;
            position: relative;
            margin-bottom: 24px;
        }}
        
        .logo {{
            width: 80px;
            height: 80px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
            position: relative;
        }}
        
        .logo::after {{
            content: '🔐';
            font-size: 32px;
            color: white;
        }}
        
        .notification-dot {{
            position: absolute;
            top: -4px;
            right: -4px;
            width: 16px;
            height: 16px;
            background: linear-gradient(45deg, #f59e0b, #f97316);
            border-radius: 50%;
            animation: pulse 2s ease-in-out infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ transform: scale(1); }}
            50% {{ transform: scale(1.1); }}
        }}
        
        .brand-name {{
            font-size: 28px;
            font-weight: 700;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin: 0;
            letter-spacing: -0.5px;
        }}
        
        .subtitle {{
            color: #64748b;
            font-size: 16px;
            margin: 8px 0 0;
            font-weight: 500;
        }}
        
        .content {{
            padding: 40px;
        }}
        
        .greeting {{
            font-size: 18px;
            color: #1e293b;
            margin: 0 0 16px;
            font-weight: 600;
        }}
        
        .message {{
            color: #475569;
            font-size: 16px;
            margin: 0 0 24px;
            line-height: 1.7;
        }}
        
        .security-notice {{
            background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
            border: 1px solid #f59e0b;
            border-radius: 16px;
            padding: 20px;
            margin: 24px 0;
            display: flex;
            align-items: flex-start;
            gap: 12px;
        }}
        
        .security-icon {{
            font-size: 20px;
            margin-top: 2px;
        }}
        
        .security-text {{
            flex: 1;
            color: #92400e;
            font-size: 14px;
            line-height: 1.6;
            margin: 0;
        }}
        
        .button-container {{
            text-align: center;
            margin: 40px 0;
        }}
        
        .reset-button {{
            display: inline-block;
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
            text-decoration: none;
            padding: 18px 48px;
            border-radius: 16px;
            font-weight: 600;
            font-size: 16px;
            letter-spacing: 0.5px;
            box-shadow: 0 8px 32px rgba(16, 185, 129, 0.4);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
            border: 2px solid rgba(255, 255, 255, 0.2);
        }}
        
        .reset-button::before {{
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
            transition: left 0.5s ease;
        }}
        
        .reset-button:hover {{
            background: linear-gradient(135deg, #059669 0%, #047857 100%);
            box-shadow: 0 12px 40px rgba(16, 185, 129, 0.5);
            transform: translateY(-2px);
        }}
        
        .reset-button:hover::before {{
            left: 100%;
        }}
        
        .alternative-link {{
            background: #f1f5f9;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 16px;
            margin: 24px 0;
            font-size: 14px;
            color: #64748b;
            word-break: break-all;
        }}
        
        .alternative-link strong {{
            color: #1e293b;
        }}
        
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin: 32px 0;
        }}
        
        .info-item {{
            background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 16px;
            text-align: center;
        }}
        
        .info-icon {{
            font-size: 24px;
            margin-bottom: 8px;
            display: block;
        }}
        
        .info-title {{
            font-weight: 600;
            color: #1e293b;
            font-size: 14px;
            margin: 0 0 4px;
        }}
        
        .info-desc {{
            color: #64748b;
            font-size: 13px;
            margin: 0;
        }}
        
        .footer {{
            background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            color: #94a3b8;
            text-align: center;
            padding: 32px 40px;
            font-size: 14px;
        }}
        
        .footer-logo {{
            font-size: 20px;
            font-weight: 700;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 12px;
        }}
        
        .footer-links {{
            margin: 16px 0;
        }}
        
        .footer-links a {{
            color: #667eea;
            text-decoration: none;
            margin: 0 12px;
            transition: color 0.3s ease;
        }}
        
        .footer-links a:hover {{
            color: #764ba2;
        }}
        
        .copyright {{
            color: #64748b;
            font-size: 12px;
            margin-top: 16px;
        }}
        
        @media (max-width: 600px) {{
            .container {{
                padding: 20px 10px;
            }}
            
            .content {{
                padding: 24px 20px;
            }}
            
            .header {{
                padding: 32px 20px 24px;
            }}
            
            .footer {{
                padding: 24px 20px;
            }}
            
            .info-grid {{
                grid-template-columns: 1fr;
            }}
            
            .reset-button {{
                padding: 14px 32px;
                font-size: 15px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="email-card">
            <!-- Header -->
            <div class="header">
                <div class="logo-container">
                    <div class="logo">
                        <div class="notification-dot"></div>
                    </div>
                </div>
                <h1 class="brand-name">SmartCalories</h1>
                <p class="subtitle">Quản lý dinh dưỡng thông minh</p>
            </div>
            
            <!-- Content -->
            <div class="content">
                <h2 class="greeting">Xin chào {user.get('fullname', 'bạn')}! 👋</h2>
                
                <p class="message">
                    Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản SmartCalories của bạn. 
                    Để đảm bảo tính bảo mật, vui lòng nhấn vào nút bên dưới để tạo mật khẩu mới.
                </p>
                
                <div class="security-notice">
                    <span class="security-icon">🛡️</span>
                    <p class="security-text">
                        <strong>Quan trọng:</strong> Liên kết này chỉ có hiệu lực trong <strong>30 phút</strong> 
                        và chỉ có thể sử dụng một lần duy nhất để đảm bảo an toàn cho tài khoản của bạn.
                    </p>
                </div>
                
                <div class="button-container">
                    <a href="{reset_link}" class="reset-button">
                        🔐 Đặt lại mật khẩu ngay
                    </a>
                </div>
                
                <div class="alternative-link">
                    <strong>Không thể nhấn nút?</strong> Sao chép và dán liên kết sau vào trình duyệt:
                    <br><br>
                    {reset_link}
                </div>
                
                <div class="info-grid">
                    <div class="info-item">
                        <span class="info-icon">⏰</span>
                        <p class="info-title">Thời gian hiệu lực</p>
                        <p class="info-desc">30 phút kể từ bây giờ</p>
                    </div>
                    <div class="info-item">
                        <span class="info-icon">🔒</span>
                        <p class="info-title">Bảo mật cao</p>
                        <p class="info-desc">Liên kết mã hóa an toàn</p>
                    </div>
                    <div class="info-item">
                        <span class="info-icon">📱</span>
                        <p class="info-title">Mọi thiết bị</p>
                        <p class="info-desc">Hoạt động trên máy tính & điện thoại</p>
                    </div>
                </div>
                
                <div class="security-notice" style="background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%); border-color: #ef4444;">
                    <span class="security-icon">⚠️</span>
                    <p class="security-text" style="color: #dc2626;">
                        <strong>Lưu ý bảo mật:</strong> Nếu bạn không yêu cầu đặt lại mật khẩu, 
                        vui lòng bỏ qua email này và liên hệ với chúng tôi ngay lập tức. 
                        Tài khoản của bạn vẫn hoàn toàn an toàn.
                    </p>
                </div>
            </div>
            
            <!-- Footer -->
            <div class="footer">
                <div class="footer-logo">SmartCalories</div>
                <p>Cảm ơn bạn đã tin tưởng sử dụng dịch vụ của chúng tôi!</p>
                
                <div class="footer-links">
                    <a href="#" style="color: #667eea;">Trung tâm trợ giúp</a>
                    <a href="#" style="color: #667eea;">Chính sách bảo mật</a>
                    <a href="#" style="color: #667eea;">Liên hệ hỗ trợ</a>
                </div>
                
                <p class="copyright">
                    © 2025 SmartCalories. Mọi quyền được bảo lưu.<br>
                    Email này được gửi tự động, vui lòng không trả lời.
                </p>
            </div>
        </div>
    </div>
</body>
</html>
            """,
            subtype="html"
        )

        fm = FastMail(conf)
        await fm.send_message(email_message)

    return templates.TemplateResponse(
        "forgot-password.html",
        {"request": request, "message": message}
    )


# Route đặt lại mật khẩu
@app.get("/reset-password", response_class=HTMLResponse)
def reset_password_form(request: Request, token: str = ""):
    info = reset_tokens.get(token)
    if not info or info["expires"] < datetime.utcnow():
        return templates.TemplateResponse(
            "forgot-password.html",
            {"request": request, "error": "Liên kết không hợp lệ hoặc đã hết hạn."}
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
            {"request": request, "error": "Liên kết không hợp lệ hoặc đã hết hạn."}
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

# --- 4. MAIN PAGE, MEAL CRUD, GOALS, LOG ---
# Route trang chính
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
        "calories": float(tdee) if tdee else 2000,
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
        "bmr": float(bmr) if bmr else None,
        "tdee": float(tdee) if tdee else None,
        "suggested_meals": suggested_meals,
        "nutrient_priority": nutrient_priority,
        "view": view,
        "users": users,
        "activities": activities,
    })

# Route thêm món ăn
@app.post("/add-meal")
async def add_meal(
    name: str = Form(...),
    calories: float = Form(...),
    carbs: float = Form(...),
    protein: float = Form(...),
    fat: float = Form(...),
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

# Route chỉnh sửa món ăn
@app.post("/edit-meal/{meal_id}")
async def update_meal(
    meal_id: str,
    name: str = Form(...),
    calories: float = Form(...),
    carbs: float = Form(...),
    protein: float = Form(...),
    fat: float = Form(...),
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

# Route xóa món ăn
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

# Route xem chi tiết món ăn
@app.post("/log-meal")
async def log_meal(
    request: Request,
    meal_id: str = Form(...),
    quantity: float = Form(...),
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

# Route đặt mục tiêu
@app.post("/set-goals")
async def set_goals(
    request: Request,
    response: Response,
    calories: float = Form(...),
    protein: float = Form(...),
    carbs: float = Form(...),
    fat: float = Form(...),
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

# --- 5. ACTIVITY ROUTES ---

# Route hoạt động thể chất
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
    duration: float = Form(...),
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

# Route xem lịch sử hoạt động
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

# --- 6. ADMIN ROUTES ---

# Route chặn người dùng
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

# Route đổi quyền người dùng
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

# Route xóa người dùng
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
    
# Route xem nhật ký hoạt động
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
        return HTMLResponse("""
        <div class='empty-log-state'>
          <div class='empty-icon'>📋</div>
          <h3>Chưa có nhật ký hoạt động</h3>
          <p>Hệ thống chưa ghi nhận hoạt động nào.</p>
        </div>
        """)
    
    html = """
    <div class='log-header'>📋 Nhật ký hoạt động hệ thống</div>
    <table class='activity-log-table'>
        <thead>
            <tr>
                <th>🕐 Thời gian</th>
                <th>👤 Người dùng</th>
                <th>⚡ Hành động</th>
            </tr>
        </thead>
        <tbody>
    """
    
    for log in logs:
        time_formatted = log.get('time', '')
        user_name = log.get('user', 'Không xác định')
        action = log.get('action', 'Không có thông tin')
        
        html += f"""
        <tr>
            <td class='time-cell'>{time_formatted}</td>
            <td class='user-cell'>{user_name}</td>
            <td class='action-cell'>{action}</td>
        </tr>
        """
    
    html += "</tbody></table>"
    return HTMLResponse(html)

# Cập nhật route xem nhật ký đăng nhập
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
        return HTMLResponse("""
        <div class='empty-log-state'>
          <div class='empty-icon'>🔑</div>
          <h3>Chưa có nhật ký đăng nhập</h3>
          <p>Hệ thống chưa ghi nhận đăng nhập nào.</p>
        </div>
        """)
    
    html = """
    <div class='log-header'>🔐 Nhật ký đăng nhập hệ thống</div>
    <table class='login-log-table'>
        <thead>
            <tr>
                <th>🕐 Thời gian</th>
                <th>👤 Người dùng</th>
                <th>🌐 IP Address</th>
                <th>📍 Địa chỉ</th>
                <th>🏢 Nhà mạng</th>
                <th>🗺️ Vị trí bản đồ</th>
            </tr>
        </thead>
        <tbody>
    """
    
    ip_cache = {}
    for log in logs:
        ip = log.get('ip', '')
        if ip in ip_cache:
            data = ip_cache[ip]
        else:
            try:
                resp = requests.get(f"http://ip-api.com/json/{ip}?fields=status,message,city,regionName,country,isp,lat,lon", timeout=2)
                data = resp.json()
            except Exception:
                data = {}
            ip_cache[ip] = data
            
        if data.get("status") == "success":
            city = data.get('city', '')
            region = data.get('regionName', '')
            country = data.get('country', '')
            location = f"{city}, {region}, {country}".strip(', ')
            isp = data.get('isp', 'Không xác định')
            lat = data.get('lat','')
            lon = data.get('lon','')
            if lat and lon:
                latlon = f"<a href='https://maps.google.com/?q={lat},{lon}' target='_blank' class='map-link'>📍 Xem bản đồ</a>"
            else:
                latlon = "<span style='color: #ccc;'>Không có</span>"
        else:
            location = "Không xác định"
            isp = "Không xác định"
            latlon = "<span style='color: #ccc;'>Không có</span>"
            
        time_formatted = log.get('time', '')
        user_name = log.get('user', 'Không xác định')
        ip_formatted = f"<span class='ip-cell'>{ip}</span>" if ip else "<span style='color: #ccc;'>Không có</span>"
        
        html += f"""
        <tr>
            <td class='time-cell'>{time_formatted}</td>
            <td class='user-cell'>{user_name}</td>
            <td>{ip_formatted}</td>
            <td class='location-cell'>{location}</td>
            <td class='isp-cell'>{isp}</td>
            <td>{latlon}</td>
        </tr>
        """
    
    html += "</tbody></table>"
    return HTMLResponse(html)


# --- 7. SCHEDULER & FAVICON ---

# Route chatbot
@app.post("/chatbot")
async def chatbot_endpofloat(request: Request):
    data = await request.json()
    messages = data.get("messages", [])
    meals = data.get("meals", [])
    logs = data.get("logs", [])
    summary = data.get("summary", {})
    activities = data.get("activities", [])

    last_msg = messages[-1]["content"].strip().lower()
    meal_names = [meal["name"].lower() for meal in meals]

    # 🧠 Tự động nhận diện tên món ăn từ các kiểu câu khác nhau
    potential_name = None
    match = re.match(r"(thêm|tạo)\s+món\s+(.+)", last_msg)
    if match:
        potential_name = match.group(2).strip()
    elif any(key in last_msg for key in ["thông tin món", "bao nhiêu calo", "dinh dưỡng món", "calories", "món ăn"]):
        name_match = re.search(r"món\s+(.+?)(?:\?|$)", last_msg)
        if name_match:
            potential_name = name_match.group(1).strip()

    # Nếu phát hiện tên món và chưa có trong danh sách thì gọi Gemini
    if potential_name and potential_name not in meal_names:
        try:
            model = genai.GenerativeModel("models/gemini-1.5-flash-latest")
            prompt = (
                f"Hãy phân tích món '{potential_name}' và ước tính thành phần dinh dưỡng trung bình cho 1 khẩu phần:\n"
                "- Calories (kcal)\n- Protein (g)\n- Carbs (g)\n- Fat (g)\n"
                "- Image URL minh họa từ floaternet (nếu có)\n"
                "Trả về đúng định dạng JSON như sau:\n"
                '{ "name": "Tên món", "calories": ..., "protein": ..., "carbs": ..., "fat": ..., "image_url": "https://..." }'
            )
            response = model.generate_content(prompt)
            json_text = response.text.strip()

            estimate = json.loads(json_text)
            estimate["image_url"] = estimate.get("image_url") or "/static/default-food.jpg"
            chatbot_temp_cache[estimate["name"].lower()] = estimate

            reply = (
                f"Món **{estimate['name']}** (ước tính 1 khẩu phần):\n"
                f"- Calories: {estimate['calories']} kcal\n"
                f"- Protein: {estimate['protein']}g\n"
                f"- Carbs: {estimate['carbs']}g\n"
                f"- Fat: {estimate['fat']}g\n"
                f"- Ảnh minh họa: {estimate['image_url']}\n\n"
                f"👉 Bạn có muốn thêm món này vào danh sách không? Trả lời `đồng ý` để thêm."
            )
            return JSONResponse({"reply": reply})

        except Exception as e:
            prfloat("Gemini error:", e)
            return JSONResponse({"reply": "❌ Không thể lấy thông tin món ăn từ Gemini lúc này."})

    # ✅ Người dùng xác nhận muốn thêm món vào database
    if last_msg in ["đồng ý", "yes", "ok", "thêm"]:
        if chatbot_temp_cache:
            latest = list(chatbot_temp_cache.values())[-1]
            meals_col.insert_one(latest)
            chatbot_temp_cache.clear()
            return JSONResponse({"reply": f"✅ Đã thêm món **{latest['name']}** vào danh sách!"})
        else:
            return JSONResponse({"reply": "❌ Không có món nào đang chờ thêm."})

    # ❓ Không khớp gì đặc biệt → fallback: hỏi Gemini như bình thường
    try:
        model = genai.GenerativeModel("models/gemini-1.5-flash-latest")
        meal_list = "\n".join([f"- {m['name']} (Calories: {m['calories']}, Protein: {m['protein']}g, Carbs: {m['carbs']}g, Fat: {m['fat']}g)" for m in meals])
        log_list = "\n".join([f"- {l['meal']['name']} x{l['quantity']} ({l['meal']['calories']*l['quantity']} cal)" for l in logs])
        activity_list = "\n".join([f"- {a['activity']} {a['duration']} phút ({a['calories_burned']} kcal)" for a in activities])
        summary_text = (
            f"Tổng hôm nay: {summary.get('total_calories', 0)} cal, "
            f"{summary.get('total_protein', 0)}g protein, "
            f"{summary.get('total_carbs', 0)}g carbs, "
            f"{summary.get('total_fat', 0)}g fat."
        )

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
        return JSONResponse({"reply": response.text})

    except Exception as e:
        prfloat("Gemini fallback error:", e)
        return JSONResponse({"reply": "⚠️ Lỗi không xác định khi gọi Gemini."})

# Thêm route mới để thêm món ăn từ chatbot
@app.post("/add-meal-from-chatbot")
async def add_meal_from_chatbot(
    request: Request,
    user_id: str = Cookie(None)
):
    if not user_id:
        return JSONResponse({"success": False, "message": "Chưa đăng nhập"}, status_code=401)
    
    data = await request.json()
    user = users_col.find_one({"_id": ObjectId(user_id)})
    
    if user and is_too_fast(user, "add_meal"):
        return JSONResponse({"success": False, "message": "Bạn thao tác quá nhanh, vui lòng thử lại sau."}, status_code=429)
    
    fullname = user.get("fullname", "") if user else ""
    
    # Validate required fields
    required_fields = ['name', 'calories', 'protein', 'carbs', 'fat']
    for field in required_fields:
        if field not in data:
            return JSONResponse({"success": False, "message": f"Thiếu thông tin {field}"}, status_code=400)
    
    meal_doc = {
        "name": data["name"],
        "calories": float(data["calories"]),
        "protein": float(data["protein"]),
        "carbs": float(data["carbs"]),
        "fat": float(data["fat"]),
        "image_url": data.get("image_url", ""),
        "created_by": fullname,
        "source": "chatbot_ai"
    }
    
    result = meals_col.insert_one(meal_doc)
    
    # Ghi log hoạt động
    db = meals_col.database
    db["activity_logs"].insert_one({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user": fullname,
        "action": f"Thêm món ăn từ AI: {data['name']}"
    })
    
    return JSONResponse({
        "success": True, 
        "message": "Thêm món ăn thành công!",
        "meal_id": str(result.inserted_id)
    })

# Cập nhật route chatbot với tính năng thông minh hơn
@app.post("/chatbot")
async def chatbot_endpoint(request: Request):
    data = await request.json()
    messages = data.get("messages", [])
    meals = data.get("meals", [])
    logs = data.get("logs", [])
    summary = data.get("summary", {})
    activities = data.get("activities", [])

    last_msg = messages[-1]["content"].strip().lower()
    meal_names = [meal["name"].lower() for meal in meals]

    # 🔍 Tìm kiếm món ăn từ nhiều nguồn
    search_patterns = [
        r"tìm\s+(?:kiếm\s+)?(?:món\s+)?(.+)",
        r"(?:thông\s+tin|calories?|dinh\s+dưỡng)\s+(?:món\s+)?(.+)",
        r"(.+)\s+(?:có\s+)?(?:bao\s+nhiêu|bao\s+nhiều)\s+(?:calo|calories?)",
        r"(?:thêm|tạo)\s+món\s+(.+)",
        r"món\s+(.+?)(?:\s+(?:có|là|gì))?(?:\?|$)",
    ]
    
    potential_name = None
    for pattern in search_patterns:
        match = re.search(pattern, last_msg)
        if match:
            potential_name = match.group(1).strip()
            break

    # 🤖 Tích hợp tìm kiếm thông minh từ nhiều nguồn
    if potential_name and potential_name not in meal_names:
        try:
            model = genai.GenerativeModel("models/gemini-1.5-flash-latest")
            
            # Enhanced prompt với nhiều nguồn dữ liệu
            enhanced_prompt = f"""
            Bạn là chuyên gia dinh dưỡng AI. Hãy tìm kiếm và phân tích món ăn "{potential_name}" từ các nguồn đáng tin cậy:

            1. **Tìm kiếm từ cơ sở dữ liệu dinh dưỡng quốc tế:**
            - USDA Food Database
            - Nutrition Data từ các nghiên cứu khoa học
            - Cơ sở dữ liệu dinh dưỡng của các quốc gia

            2. **Tham khảo từ các nguồn ẩm thực:**
            - Công thức nấu ăn truyền thống
            - Thông tin từ các nhà hàng uy tín
            - Dữ liệu từ các ứng dụng theo dõi dinh dưỡng

            3. **Ước tính cho 1 khẩu phần tiêu chuẩn:**
            - Calories (kcal) - chính xác đến đơn vị
            - Protein (g) - làm tròn 1 chữ số thập phân
            - Carbs (g) - làm tròn 1 chữ số thập phân  
            - Fat (g) - làm tròn 1 chữ số thập phân
            - Tìm URL hình ảnh thực tế từ internet (ưu tiên hình ảnh chất lượng cao)

            4. **Bổ sung thông tin hữu ích:**
            - Nguồn gốc món ăn
            - Lợi ích dinh dưỡng
            - Gợi ý cách chế biến healthy

            Trả về định dạng JSON chính xác:
            {{
                "name": "Tên món ăn (tiếng Việt)",
                "calories": số_calories,
                "protein": số_protein,
                "carbs": số_carbs,
                "fat": số_fat,
                "image_url": "URL_hình_ảnh_thực_tế",
                "origin": "Nguồn gốc món ăn",
                "benefits": ["Lợi ích 1", "Lợi ích 2"],
                "cooking_tips": "Gợi ý chế biến healthy"
            }}

            Hãy đảm bảo thông tin chính xác và đáng tin cậy!
            """
            
            response = model.generate_content(enhanced_prompt)
            json_text = response.text.strip()
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', json_text, re.DOTALL)
            if json_match:
                json_text = json_match.group()
            
            try:
                meal_data = json.loads(json_text)
                
                # Validate and clean data
                meal_data["image_url"] = meal_data.get("image_url") or "/static/default-food.jpg"
                meal_data["calories"] = float(meal_data.get("calories", 0))
                meal_data["protein"] = float(meal_data.get("protein", 0))
                meal_data["carbs"] = float(meal_data.get("carbs", 0))
                meal_data["fat"] = float(meal_data.get("fat", 0))
                
                # Store in temp cache
                chatbot_temp_cache[meal_data["name"].lower()] = meal_data
                
                # Create enhanced response
                reply = f"""🔍 **Đã tìm thấy thông tin món: {meal_data['name']}**

MEAL_INFO:{json.dumps(meal_data)}

📊 **Thông tin dinh dưỡng** (1 khẩu phần):
• Calories: **{meal_data['calories']} kcal**
• Protein: **{meal_data['protein']}g**
• Carbs: **{meal_data['carbs']}g** 
• Fat: **{meal_data['fat']}g**

🌍 **Nguồn gốc**: {meal_data.get('origin', 'Không xác định')}

💡 **Lợi ích dinh dưỡng**:
{chr(10).join(['• ' + benefit for benefit in meal_data.get('benefits', ['Cung cấp năng lượng cho cơ thể'])])}

👨‍🍳 **Gợi ý chế biến healthy**: {meal_data.get('cooking_tips', 'Nấu với ít dầu và nhiều rau xanh')}

Bạn có muốn thêm món này vào danh sách không?"""
                
                return JSONResponse({
                    "reply": reply,
                    "meal_data": meal_data
                })
                
            except json.JSONDecodeError:
                # Fallback response
                return JSONResponse({
                    "reply": f"🔍 Tôi đã tìm kiếm món **{potential_name}** nhưng không thể xử lý dữ liệu. Bạn có thể thử với tên món khác không?"
                })

        except Exception as e:
            print(f"Enhanced search error: {e}")
            return JSONResponse({
                "reply": f"❌ Không thể tìm kiếm thông tin món **{potential_name}** lúc này. Vui lòng thử lại sau hoặc kiểm tra lại tên món."
            })

    # ✅ Xác nhận thêm món
    confirmation_words = ["đồng ý", "yes", "ok", "thêm", "có", "được", "thêm vào"]
    if any(word in last_msg for word in confirmation_words):
        if chatbot_temp_cache:
            latest = list(chatbot_temp_cache.values())[-1]
            chatbot_temp_cache.clear()
            return JSONResponse({
                "reply": f"✅ Món **{latest['name']}** đã được chuẩn bị để thêm vào danh sách!\n\nVui lòng nhấn nút **\"Thêm vào danh sách\"** ở phía trên để hoàn tất."
            })
        else:
            return JSONResponse({
                "reply": "❌ Không có món nào đang chờ thêm. Hãy tìm kiếm món ăn trước!"
            })

    # 🧠 Phân tích và tư vấn thông minh
    try:
        model = genai.GenerativeModel("models/gemini-1.5-flash-latest")
        
        # Tạo context chi tiết
        meal_list = "\n".join([
            f"• **{m['name']}** - {m['calories']} cal, Protein: {m['protein']}g, Carbs: {m['carbs']}g, Fat: {m['fat']}g"
            for m in meals
        ])
        
        log_list = "\n".join([
            f"• **{l['meal']['name']}** x{l['quantity']} = {l['meal']['calories']*l['quantity']} cal"
            for l in logs
        ])
        
        activity_list = "\n".join([
            f"• **{a['activity']}** {a['duration']} phút = {a['calories_burned']} kcal đốt cháy"
            for a in activities
        ])
        
        summary_text = (
            f"**Tổng hôm nay**: {summary.get('total_calories', 0)} cal, "
            f"Protein: {summary.get('total_protein', 0)}g, "
            f"Carbs: {summary.get('total_carbs', 0)}g, "
            f"Fat: {summary.get('total_fat', 0)}g"
        )

        enhanced_system_prompt = f"""
        Bạn là SmartCalories AI - trợ lý dinh dưỡng thông minh và thân thiện.

        🎯 **KHẢ NĂNG CỦA BẠN:**
        - Tìm kiếm món ăn từ cơ sở dữ liệu quốc tế
        - Phân tích dinh dưỡng chi tiết và khoa học
        - Tư vấn chế độ ăn cá nhân hóa
        - Gợi ý thực đơn healthy và cân bằng
        - Hướng dẫn hoạt động thể chất phù hợp

        📊 **DỮ LIỆU HIỆN TẠI:**

        **Danh sách món ăn có sẵn:**
        {meal_list}

        **Nhật ký ăn hôm nay:**
        {log_list}

        **Tổng kết dinh dưỡng hôm nay:**
        {summary_text}

        **Hoạt động thể chất hôm nay:**
        {activity_list}

        🎨 **PHONG CÁCH TRẢ LỜI:**
        - Dùng emoji phù hợp và thân thiện
        - Trả lời bằng tiếng Việt tự nhiên
        - Đưa ra lời khuyên thực tế và khoa học
        - Khuyến khích lối sống healthy
        - Sử dụng markdown để format đẹp

        📝 **CÂU HỎI/YÊU CẦU:** {last_msg}

        Hãy trả lời một cách hữu ích, thông minh và thân thiện!
        """

        conversation_context = "\n".join([
            f"**{msg.get('role', 'user')}**: {msg.get('content', '')}"
            for msg in messages[-5:]  # Last 5 messages for context
        ])

        full_prompt = enhanced_system_prompt + "\n\n**Ngữ cảnh cuộc trò chuyện:**\n" + conversation_context

        response = model.generate_content(full_prompt)
        
        return JSONResponse({"reply": response.text})

    except Exception as e:
        print(f"Gemini conversation error: {e}")
        return JSONResponse({
            "reply": "⚠️ Xin lỗi, tôi đang gặp sự cố kỹ thuật. Vui lòng thử lại sau hoặc liên hệ hỗ trợ kỹ thuật!"
        })
    
# Route xuất CSV nhật ký
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

# --- 8. MISC ROUTES ---

# tạo favicon
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("app/static/favicon.ico")

def calculate_burned_calories(weight_kg: float, duration_min: float, met: float) -> float:
    return round(met * weight_kg * (duration_min / 60.0), 2)

def format_vn_datetime(dt_str):
    # dt_str dạng "YYYY-MM-DD HH:MM:SS"
    try:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%H:%M %d/%m/%Y")
    except Exception:
        return dt_str

def reset_logs_job():
    db = meals_col.database
    db["activity_logs"].delete_many({})
    db["login_logs"].delete_many({})
    activities_col.delete_many({}) 

scheduler = BackgroundScheduler()
scheduler.add_job(reset_logs_job, 'cron', day=1, hour=0, minute=1)
scheduler.start()

# --- 9. PROFILE & SESSION ROUTES ---

# Trang thông tin cá nhân
@app.post("/profile")
async def update_profile(
    request: Request,
    height: float = Form(...),
    weight: float = Form(...),
    age: float = Form(...),
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
            "bmr": float(bmr),
            "tdee": float(tdee)
        }
    })

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
