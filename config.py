"""
config.py
=========
الإعدادات المركزية لنظام توليد التقارير الآلي.
جميع الثوابت والمسارات تُعرَّف هنا لتسهيل الصيانة والتوسع.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ─── تحميل المتغيرات من ملف .env ───────────────────────────────────────────
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# ─── إعدادات Google Sheets ──────────────────────────────────────────────────
SERVICE_ACCOUNT_FILE: str = str(BASE_DIR / "credentials.json")
SPREADSHEET_NAME: str = "نظام المتابعة الدوري - الاتحاد العام لطلبة سوريا"
# اختياري: استخدام الرابط المباشر بدلاً من الاسم
# SPREADSHEET_URL: str = "https://docs.google.com/spreadsheets/d/YOUR_ID"

SCOPES: list[str] = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive",   # read + write (needed for upload)
]

# ─── إعدادات Gemini AI ──────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = "gemini-2.5-flash"

# ─── إعدادات Groq AI ────────────────────────────────────────────────────────
# يدعم مفتاحًا واحدًا أو قائمة مفاتيح مفصولة بفواصل في GROQ_API_KEYS
# للتوافق الخلفي: إذا كان GROQ_API_KEY محدداً فقط، يُعامَل كقائمة من عنصر واحد
_raw_keys: str = os.getenv("GROQ_API_KEYS", "") or os.getenv("GROQ_API_KEY", "")
GROQ_API_KEYS: list[str] = [k.strip() for k in _raw_keys.split(",") if k.strip()]
GROQ_API_KEY:  str = GROQ_API_KEYS[0] if GROQ_API_KEYS else ""   # backward-compat alias
GROQ_MODEL:    str = "llama-3.1-8b-instant"   # high-limit model — replaces 70b for throughput
GROQ_CURRENT_KEY_INDEX: int = 0              # مبدئي — يُحدَّث في ai_engine عند التدوير

# ─── Parallel Orchestrator — نماذج كل قسم ──────────────────────────────────
GROQ_MODEL_SUMMARY:    str = "llama-3.3-70b-versatile"  # سلسلة: قدرة توليف عالية
GROQ_MODEL_TASKS:      str = "llama-3.1-8b-instant"     # سرعة عالية — للبيانات الهيكلية JSON
GROQ_MODEL_CHALLENGES: str = "llama-3.1-8b-instant"     # Groq fallback للتحديات
GROQ_MODEL_FALLBACK:   str = "llama-3.1-8b-instant"     # Fallback عالمي عند إخفاق Gemini/Groq
GEMINI_MODEL_GEMMA4:   str = "gemma-4-31b-it"   # Gemma 4 عبر Gemini API — Thread 4 + Fallback

# ─── اختيار المزوّد: GROQ | GEMINI ──────────────────────────────────────────
LLM_PROVIDER:  str = os.getenv("LLM_PROVIDER", "GROQ").upper()

# ─── بنية الأعمدة (117 عمود) ────────────────────────────────────────────────
# Indices are 0-based
COL_TIMESTAMP: int = 0
COL_OFFICE_NAME: int = 1
COL_SUBMITTER: int = 2
COL_SUBMITTER_PHONE: int = 3
COL_MONTHLY_PLAN_LINK: int = 4   # رابط PDF الخطة الشهرية

# المهام: تبدأ من العمود 5 (index 5) بخطوة 10 أعمدة
TASK_START_INDEX: int = 5
TASK_CHUNK_SIZE: int = 10        # 10 أعمدة لكل مهمة
TASK_DATA_COLS: int = 9          # نأخذ أول 9 أعمدة من كل chunk (نتجاهل العمود العاشر)
MAX_TASKS: int = 11              # أقصى عدد للمهام (cols 5–114)

# داخل كل Chunk (offset من بداية الـ chunk):
TASK_COL_MANAGER: int = 0
TASK_COL_MANAGER_PHONE: int = 1
TASK_COL_TASK_NAME: int = 2
TASK_COL_DESCRIPTION: int = 3
TASK_COL_TYPE: int = 4
TASK_COL_MECHANISM: int = 5
TASK_COL_STATUS: int = 6
TASK_COL_ISSUES: int = 7
TASK_COL_FILE_LINK: int = 8
# العمود رقم 9 (index 9) هو "هل تريد إضافة مهمة أخرى؟" — يُتجاهل

# الحقول الختامية
COL_GENERAL_CHALLENGES: int = 115
COL_ADDITIONAL_NOTES: int = 116

# ─── إعدادات المخرجات ───────────────────────────────────────────────────────
REPORTS_DIR: Path = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# ─── إعدادات Google Drive Upload ───────────────────────────────────────
# ID المجلد الجذر على Drive: ارشيف_الاتحاد_العام_لطلبة_سوريا
ROOT_FOLDER_ID: str = "1UUuwLBOjFy4NkrTPI8ZG5WStTMjHsf42"
# اسم مجلد النظام داخل سنة كل عام
DRIVE_SYSTEM_FOLDER: str = "نظام_المتابعة_الدورية"

# ─── OAuth2 User Credentials (للرفع فقط — يتجاوز حصة Service Account) ──
# حمّل هذا الملف من Google Cloud Console → OAuth 2.0 Client IDs → Desktop App
OAUTH_CLIENT_FILE: str = str(BASE_DIR / "oauth_client.json")
# يُنشَأ تلقائيًا بعد أول تفويض ناجح
OAUTH_TOKEN_FILE:  str = str(BASE_DIR / "token.json")
