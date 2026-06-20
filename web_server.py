"""
web_server.py
=============
خادم FastAPI لتوفير واجهة مستخدم تفاعلية (Web UI) لنظام GUSS.
يسمح بتحديد المكاتب وجلب البيانات وتوليد التقارير في الخلفية مع تتبع لحظي للحالة.
"""

import os
import sys
import threading
import traceback
import copy
import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, List, Optional
from pydantic import BaseModel
import jwt

from fastapi import FastAPI, BackgroundTasks, HTTPException, status, Depends, Response, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import config as cfg
from database import get_supabase_client
from supabase_adapter import adapt_supabase_to_legacy_format
from pdf_handler import get_plan_text
from ai_engine import get_orchestrator
from report_generator import build_report
from drive_uploader import upload_report
from exceptions import GUSSError
from logger import get_logger
from routes.submissions import router as submissions_router

# تهيئة التطبيق والمسجل
app = FastAPI(title="GUSS Report System Web API", version="3.2")
_log = get_logger("web_server")

# إعداد CORS للسماح بالطلبات من الفرونت إند المستضيف على Netlify
allowed_origins_raw = os.getenv("ALLOWED_ORIGIN", "http://localhost:5173").strip()
origins = [o.strip() for o in allowed_origins_raw.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# تسجيل router الفورم الجديد (Supabase submissions)
app.include_router(submissions_router)

# تأمين وحماية مفتاح التوكن الافتراضي
if cfg.JWT_SECRET_KEY == "guss_secret_key_2026_xyz":
    _log.warning("⚠️ JWT_SECRET_KEY uses a default public value! Generating a secure random secret key for this session.")
    cfg.JWT_SECRET_KEY = secrets.token_hex(32)

# قفل التعديل على الإعدادات لمنع الوصول المتزامن للملف
settings_lock = threading.Lock()

# إنشاء مجلد الملفات الثابتة إذا لم يكن موجوداً
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)

# حالة التشغيل المشتركة (تتم حمايتها بقفل Lock)
state_lock = threading.Lock()
pipeline_state = {
    "status": "idle",          # idle, running, completed, failed
    "progress": 0.0,           # نسبة الإنجاز الإجمالية 0..100
    "current_office": "",       # اسم المكتب الجاري معالجته حالياً
    "current_stage": "",        # المرحلة الحالية (Downloading, Auditing, ...)
    "total_offices": 0,
    "processed_offices": 0,
    "results": [],             # قائمة بالتقارير المكتملة أو الأخطاء
}

# ─── Pydantic Models ────────────────────────────────────────────────────────
class ProcessRequest(BaseModel):
    submission_id: int


class LoginRequest(BaseModel):
    username: str
    password: str


class SettingsUpdateRequest(BaseModel):
    gemini_api_key: Optional[str] = None
    spreadsheet_name: Optional[str] = None
    drive_system_folder: Optional[str] = None
    default_model: Optional[str] = None
    fallback_model: Optional[str] = None
    admin_username: Optional[str] = None
    admin_password: Optional[str] = None


# ─── JWT Utilities ──────────────────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, cfg.JWT_SECRET_KEY, algorithm="HS256")
    return encoded_jwt


def get_current_user(request: Request):
    token = request.cookies.get("guss_session")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="غير مصرح بالوصول. يرجى تسجيل الدخول أولاً."
        )
    try:
        payload = jwt.decode(token, cfg.JWT_SECRET_KEY, algorithms=["HS256"])
        username = payload.get("sub")
        if username != cfg.GUSS_ADMIN_USERNAME:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="المستخدم غير مصرح له."
            )
        return username
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="جلسة غير صالحة أو منتهية الصلاحية. يرجى تسجيل الدخول مجدداً."
        )


def hash_password(plain_password: str) -> str:
    """توليد هاش آمن لكلمة المرور باستخدام salt عشوائي و SHA256."""
    salt = secrets.token_hex(8)
    h = hashlib.sha256((salt + plain_password).encode("utf-8")).hexdigest()
    return f"sha256${salt}${h}"


def safe_filename(name: str) -> str:
    """يستبدل الأحرف غير الصالحة في أسماء الملفات بشرطات سفلية."""
    import re
    return re.sub(r'[\\/*?:"<>| ]', '_', name)


def get_report_filename(office_name: str, target_month_num: int = None) -> str:
    """يُنشئ اسم ملف التقرير: YYYY-MM_OfficeName.docx"""
    if target_month_num:
        month_str = f"{datetime.now().year}-{target_month_num:02d}"
    else:
        month_str = datetime.now().strftime("%Y-%m")

    safe_name = safe_filename(office_name)
    return f"{month_str}_{safe_name}.docx"


def check_password(plain_password: str, stored_password: str) -> bool:
    """التحقق من تطابق كلمة المرور مع الهاش أو القيمة النصية الخام للتوافقية."""
    if stored_password.startswith("sha256$"):
        parts = stored_password.split("$")
        if len(parts) == 3:
            salt = parts[1]
            h = parts[2]
            return hashlib.sha256((salt + plain_password).encode("utf-8")).hexdigest() == h
    return stored_password == plain_password


# ─── Pipeline Runner Thread ──────────────────────────────────────────────────
def _background_pipeline_runner(submission_id: int):
    """خيط خلفي لتشغيل خط الأنابيب وتحديث الحالة لتقرير محدد من قاعدة البيانات."""
    global pipeline_state
    
    try:
        db = get_supabase_client()
        
        # 1. جلب التقرير والمهام من قاعدة البيانات
        with state_lock:
            pipeline_state["current_stage"] = "جاري جلب بيانات التقرير من قاعدة البيانات..."
            
        submission_res = db.table("submissions").select("*, offices(name)").eq("id", submission_id).execute()
        if not submission_res.data:
            raise GUSSError(f"التقرير رقم {submission_id} غير موجود في قاعدة البيانات.")
            
        submission = submission_res.data[0]
        office_name = submission.get("offices", {}).get("name") if submission.get("offices") else "Unknown Office"
        
        tasks_res = db.table("tasks").select("*").eq("submission_id", submission_id).order("task_order").execute()
        tasks = tasks_res.data
        
        # 2. تطبيق المحول لتكييف الحقول
        office_data = adapt_supabase_to_legacy_format(submission, tasks)
        
        with state_lock:
            pipeline_state["current_office"] = office_name
            pipeline_state["current_stage"] = "تحليل بيانات التقرير..."
            pipeline_state["progress"] = 10.0
            
        if not office_data.get("tasks"):
            raise GUSSError("لم يتم العثور على أي مهام نشطة في هذا التقرير.")
            
        # 3. تحميل PDF الخطة
        with state_lock:
            pipeline_state["current_stage"] = "جاري تحميل وقراءة خطة الـ PDF..."
            pipeline_state["progress"] = 30.0
            
        plan_text = ""
        pdf_status = ""
        plan_link = office_data.get("monthly_plan_link", "")
        if plan_link:
            try:
                plan_text, pdf_status = get_plan_text(plan_link)
            except Exception as e:
                _log.warning(f"{office_name}: Failed to read PDF: {e}. Proceeding with empty plan.")
                
        # 4. مراجعة وتدقيق الذكاء الاصطناعي
        with state_lock:
            pipeline_state["current_stage"] = "جاري التدقيق والمقارنة بالذكاء الاصطناعي (Gemini)..."
            pipeline_state["progress"] = 50.0
            
        orchestrator = get_orchestrator()
        ai_results = orchestrator.analyze(
            office_data=office_data,
            plan_text=plan_text
        )
        
        # 5. توليد تقرير Word
        with state_lock:
            pipeline_state["current_stage"] = "جاري إنشاء ملف التقرير Word..."
            pipeline_state["progress"] = 75.0
            
        month_num = office_data["target_month_num"]
        filename = get_report_filename(office_name, month_num)
        output_path = Path(cfg.REPORTS_DIR) / filename
        report_path = build_report(
            office_data=office_data,
            ai_analysis=ai_results,
            output_path=output_path,
            plan_text=plan_text,
            pdf_status=pdf_status
        )
        
        # 6. الرفع إلى Google Drive
        with state_lock:
            pipeline_state["current_stage"] = "جاري رفع التقرير والمرفقات إلى Google Drive..."
            pipeline_state["progress"] = 90.0
            
        file_id = upload_report(
            local_path=report_path,
            office_name=office_name,
            office_data=office_data
        )
        drive_link = f"https://drive.google.com/file/d/{file_id}/view?usp=drivesdk"
        
        # 7. تحديث حالة التقرير في قاعدة البيانات إلى 'processed'
        db.table("submissions").update({"status": "processed"}).eq("id", submission_id).execute()
        
        # إنجاز ناجح
        _log.info(f"Submission {submission_id} for {office_name} processed successfully!")
        with state_lock:
            pipeline_state["status"] = "completed"
            pipeline_state["progress"] = 100.0
            pipeline_state["current_office"] = ""
            pipeline_state["current_stage"] = "اكتملت المعالجة بنجاح!"
            pipeline_state["results"].append({
                "office": office_name,
                "status": "Success",
                "report_name": report_path.name,
                "drive_link": drive_link
            })
            
    except Exception as e:
        error_msg = f"Error processing submission {submission_id}: {e}"
        _log.error(f"{error_msg}\n{traceback.format_exc()}")
        
        # تحديث حالة التقرير في قاعدة البيانات إلى 'failed'
        try:
            db = get_supabase_client()
            db.table("submissions").update({"status": "failed"}).eq("id", submission_id).execute()
        except Exception as db_err:
            _log.error(f"Failed to update status to failed in database: {db_err}")
            
        with state_lock:
            pipeline_state["status"] = "failed"
            pipeline_state["progress"] = 100.0
            pipeline_state["current_office"] = ""
            pipeline_state["current_stage"] = f"فشلت المعالجة: {str(e)}"
            pipeline_state["results"].append({
                "office": f"Report #{submission_id}",
                "status": "Error",
                "details": str(e)
            })


# ─── API Routes ─────────────────────────────────────────────────────────────
@app.post("/api/login")
def api_login(request: LoginRequest, response: Response):
    if request.username == cfg.GUSS_ADMIN_USERNAME and check_password(request.password, cfg.GUSS_ADMIN_PASSWORD):
        token = create_access_token(data={"sub": request.username})
        secure_cookie = os.getenv("GUSS_COOKIE_SECURE", "false").lower() == "true"
        response.set_cookie(
            key="guss_session",
            value=token,
            httponly=True,
            samesite="lax",
            secure=secure_cookie,
            max_age=7 * 24 * 3600
        )
        return {"status": "success", "username": request.username}
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="اسم المستخدم أو كلمة المرور غير صحيحة."
    )


@app.post("/api/logout")
def api_logout(response: Response):
    response.delete_cookie(key="guss_session")
    return {"status": "success"}


@app.get("/api/user/me")
def api_user_me(current_user: str = Depends(get_current_user)):
    return {"username": current_user}


def mask_api_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 12:
        return "****"
    return f"{key[:8]}...{key[-4:]}"


@app.get("/api/settings")
def api_get_settings(current_user: str = Depends(get_current_user)):
    return {
        "gemini_api_key": mask_api_key(cfg.GEMINI_API_KEY),
        "spreadsheet_name": cfg.SPREADSHEET_NAME,
        "drive_system_folder": cfg.DRIVE_SYSTEM_FOLDER,
        "default_model": cfg.GEMINI_MODEL_DEFAULT,
        "fallback_model": cfg.GEMINI_MODEL_FALLBACK,
        "admin_username": cfg.GUSS_ADMIN_USERNAME,
        "admin_password": "********"
    }


@app.post("/api/settings")
def api_update_settings(request: SettingsUpdateRequest, current_user: str = Depends(get_current_user)):
    with settings_lock:
        settings_path = Path(cfg.BASE_DIR) / "settings.yaml"
        import yaml
        
        if settings_path.exists():
            with open(settings_path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f) or {}
        else:
            yaml_data = {}
            
        if "ai" not in yaml_data:
            yaml_data["ai"] = {}
        if "sheets" not in yaml_data:
            yaml_data["sheets"] = {}
        if "drive" not in yaml_data:
            yaml_data["drive"] = {}
        if "auth" not in yaml_data:
            yaml_data["auth"] = {}
            
        updated = False
        
        if request.gemini_api_key is not None:
            val = request.gemini_api_key.strip()
            if val and not (val.endswith("XXXX") or "..." in val or "*" in val):
                yaml_data["ai"]["api_key"] = val
                cfg.GEMINI_API_KEY = val
                updated = True
            elif not val:
                yaml_data["ai"]["api_key"] = ""
                cfg.GEMINI_API_KEY = ""
                updated = True
                
        if request.spreadsheet_name is not None:
            val = request.spreadsheet_name.strip()
            yaml_data["sheets"]["spreadsheet_name"] = val
            cfg.SPREADSHEET_NAME = val
            updated = True
            
        if request.drive_system_folder is not None:
            val = request.drive_system_folder.strip()
            yaml_data["drive"]["system_folder_name"] = val
            cfg.DRIVE_SYSTEM_FOLDER = val
            updated = True
            
        if request.default_model is not None:
            val = request.default_model.strip()
            if val:
                yaml_data["ai"]["default_model"] = val
                cfg.GEMINI_MODEL_DEFAULT = val
                updated = True
                
        if request.fallback_model is not None:
            val = request.fallback_model.strip()
            if val:
                yaml_data["ai"]["fallback_model"] = val
                cfg.GEMINI_MODEL_FALLBACK = val
                updated = True
                
        if request.admin_username is not None:
            val = request.admin_username.strip()
            if val:
                yaml_data["auth"]["admin_username"] = val
                cfg.GUSS_ADMIN_USERNAME = val
                updated = True
                
        if request.admin_password is not None:
            val = request.admin_password.strip()
            if val and val != "********":
                hashed = hash_password(val)
                yaml_data["auth"]["admin_password"] = hashed
                cfg.GUSS_ADMIN_PASSWORD = hashed
                updated = True
                
        if updated:
            with open(settings_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(yaml_data, f, allow_unicode=True, default_flow_style=False)
                
        return {"status": "success", "message": "تم تحديث الإعدادات بنجاح."}


@app.post("/api/process")
def api_process_offices(request: ProcessRequest, background_tasks: BackgroundTasks, current_user: str = Depends(get_current_user)):
    """بدء تشغيل خط الأنابيب لتقرير محدد في الخلفية."""
    global pipeline_state
    
    # التحقق من وجود التقرير بقاعدة البيانات أولاً
    try:
        db = get_supabase_client()
        res = db.table("submissions").select("id").eq("id", request.submission_id).execute()
        if not res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"التقرير رقم {request.submission_id} غير موجود في قاعدة البيانات."
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطأ أثناء التحقق من التقرير في قاعدة البيانات: {str(e)}"
        )
        
    with state_lock:
        if pipeline_state["status"] == "running":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="هناك عملية معالجة قيد التشغيل بالفعل حالياً. يرجى الانتظار لحين انتهائها."
            )
            
        # تصفير الحالة لعملية جديدة
        pipeline_state["status"] = "running"
        pipeline_state["progress"] = 0.0
        pipeline_state["current_office"] = ""
        pipeline_state["current_stage"] = "جاري بدء معالجة خط الأنابيب..."
        pipeline_state["total_offices"] = 1
        pipeline_state["processed_offices"] = 0
        pipeline_state["results"] = []

    # تشغيل المهمة في الخلفية دون حظر استجابة الـ HTTP
    background_tasks.add_task(
        _background_pipeline_runner,
        submission_id=request.submission_id
    )
    return {"status": "started"}



@app.get("/api/status")
def api_get_status(current_user: str = Depends(get_current_user)):
    """الحصول على حالة المعالجة اللحظية."""
    with state_lock:
        return copy.deepcopy(pipeline_state)


@app.post("/api/reset")
def api_reset_status(current_user: str = Depends(get_current_user)):
    """إعادة تعيين الحالة إلى idle بعد الانتهاء."""
    global pipeline_state
    with state_lock:
        if pipeline_state["status"] == "running":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="لا يمكن إعادة تعيين الحالة أثناء تشغيل المعالجة."
            )
        pipeline_state["status"] = "idle"
        pipeline_state["progress"] = 0.0
        pipeline_state["current_office"] = ""
        pipeline_state["current_stage"] = ""
        pipeline_state["total_offices"] = 0
        pipeline_state["processed_offices"] = 0
        pipeline_state["results"] = []
    return {"status": "reset"}


@app.get("/api/reports")
def api_list_reports(current_user: str = Depends(get_current_user)):
    """سرد قائمة التقارير التي تم توليدها محلياً والمخزنة في مجلد reports."""
    reports_dir = Path(cfg.REPORTS_DIR)
    if not reports_dir.exists():
        return {"reports": []}
        
    files = []
    # البحث عن ملفات docx وتصفيتها
    for path in reports_dir.glob("*.docx"):
        if path.is_file():
            stat = path.stat()
            files.append({
                "name": path.name,
                "size_kb": round(stat.st_size / 1024, 1),
                "created_at": stat.st_mtime
            })
            
    # ترتيب الملفات من الأحدث للأقدم
    files.sort(key=lambda x: x["created_at"], reverse=True)
    return {"reports": files}


@app.get("/api/download/{filename}")
def api_download_report(filename: str, current_user: str = Depends(get_current_user)):
    """تنزيل ملف تقرير محدد بأمان."""
    reports_dir = Path(cfg.REPORTS_DIR).resolve()
    target_path = Path(reports_dir / filename).resolve()
    
    # حماية أمنية لمنع التنقل خارج مجلد التقارير (Directory Traversal)
    if not target_path.exists() or not target_path.is_file() or target_path.parent != reports_dir:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="الملف المطلوب غير موجود أو غير مصرح بالوصول إليه."
        )
        
    return FileResponse(
        path=target_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


# ─── Serve Front-End Files ──────────────────────────────────────────────────
@app.get("/")
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        # إنشاء ملف ترحيبي بسيط في حال عدم وجود الواجهة بعد
        return JSONResponse(
            content={"message": "GUSS Server is running. Frontend static files are not yet created."},
            status_code=status.HTTP_200_OK
        )
    return FileResponse(index_file)

# ربط المجلد كملفات ثابتة لباقي المحتويات (JS, CSS)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")


# ─── Launch Server ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    # التشغيل محلياً على المنفذ 8000
    print("\n" + "="*70)
    print("🚀 GUSS Web Application server starting...")
    print("   Open your browser and navigate to: http://localhost:8000")
    print("="*70 + "\n")
    uvicorn.run("web_server:app", host="0.0.0.0", port=8000, reload=True)
