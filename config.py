"""
config.py
=========
الإعدادات المركزية لنظام توليد التقارير الآلي.
جميع الثوابت والمسارات تُعرَّف هنا لتسهيل الصيانة والتوسع.

الإعدادات تُحمَّل من ثلاثة مصادر (بالأولوية):
  1. متغيرات البيئة (.env) — للمفاتيح السرية
  2. settings.yaml — للإعدادات القابلة للتعديل
  3. القيم الافتراضية المُضمَّنة — كشبكة أمان
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ─── تحميل المتغيرات من ملف .env ───────────────────────────────────────────
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# ─── تحميل settings.yaml (اختياري — القيم الافتراضية كشبكة أمان) ──────────
_settings: dict = {}
try:
    import yaml
    _yaml_path = BASE_DIR / "settings.yaml"
    if _yaml_path.exists():
        with open(_yaml_path, "r", encoding="utf-8") as _f:
            _settings = yaml.safe_load(_f) or {}
except ImportError:
    pass  # PyYAML غير مثبت — نستخدم القيم الافتراضية


def _cfg(section: str, key: str, default):
    """يقرأ قيمة من settings.yaml بمسار section.key مع قيمة افتراضية."""
    return _settings.get(section, {}).get(key, default)


# هيكل الأعمدة (Schema Configuration)
SCHEMA_CFG: dict = _settings.get("schema", {})

# ─── إعدادات Google Sheets ──────────────────────────────────────────────────
SERVICE_ACCOUNT_FILE: str = str(BASE_DIR / "credentials.json")
SPREADSHEET_NAME: str = os.getenv("SPREADSHEET_NAME", _cfg("sheets", "spreadsheet_name", "نظام المتابعة الدوري - الاتحاد العام لطلبة سوريا"))

SCOPES: list[str] = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive",   # read + write (needed for upload)
]

# ─── إعدادات Gemini AI ──────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", _cfg("ai", "api_key", ""))
GEMINI_MODEL_DEFAULT:  str = os.getenv("GEMINI_MODEL_DEFAULT", _cfg("ai", "default_model",  "gemini-3.5-flash"))
GEMINI_MODEL_FALLBACK: str = os.getenv("GEMINI_MODEL_FALLBACK", _cfg("ai", "fallback_model", "gemini-3.1-flash-lite"))
GEMINI_TEMPERATURE:  float = float(os.getenv("GEMINI_TEMPERATURE", _cfg("ai", "temperature", 0.3)))
GEMINI_FALLBACK_WAIT:  int = int(os.getenv("GEMINI_FALLBACK_WAIT", _cfg("ai", "fallback_wait_seconds", 30)))

# max_output_tokens
_ai_tokens: dict = _settings.get("ai", {}).get("max_tokens", {})
GEMINI_MAX_TOKENS_TASKS:   int = _ai_tokens.get("tasks",   8192)
GEMINI_MAX_TOKENS_DEFAULT: int = _ai_tokens.get("default", 4096)

# ─── إعدادات خط الأنابيب ────────────────────────────────────────────────────
PIPELINE_COOLDOWN:    int = _cfg("pipeline", "cooldown_seconds", 10)
PLAN_TEXT_MAX_CHARS:  int = _cfg("pipeline", "plan_text_max_chars", 6000)

# ─── إعدادات Sheets Retry ───────────────────────────────────────────────────
SHEETS_RETRY_MAX:        int   = _cfg("sheets", "retry_max", 3)
SHEETS_RETRY_BASE_DELAY: float = _cfg("sheets", "retry_base_delay", 5.0)

# ─── إعدادات طابور معالجة الذكاء الاصطناعي ──────────────────────────────────
# تُقرأ من settings.yaml قسم queue — لا تُضمَّن كأرقام صلبة في أي مكان
QUEUE_MIN_DELAY_SECONDS: int   = _cfg("queue", "min_delay_seconds", 60)
QUEUE_MAX_ATTEMPTS:      int   = _cfg("queue", "max_attempts", 3)
QUEUE_BACKOFF_MULTIPLIER: int  = _cfg("queue", "backoff_multiplier", 2)
QUEUE_STUCK_THRESHOLD_MINUTES: int = _cfg("queue", "stuck_row_threshold_minutes", 30)


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
ROOT_FOLDER_ID:     str = os.getenv("ROOT_FOLDER_ID", _cfg("drive", "root_folder_id", "1UUuwLBOjFy4NkrTPI8ZG5WStTMjHsf42"))
DRIVE_SYSTEM_FOLDER: str = os.getenv("DRIVE_SYSTEM_FOLDER", _cfg("drive", "system_folder_name", "نظام_المتابعة_الدورية"))

# ─── إعدادات التقرير ────────────────────────────────────────────────────
REPORT_FONT:               str = _cfg("report", "font_family",         "Cairo")
REPORT_INSTITUTIONAL_COLOR: str = _cfg("report", "institutional_color", "#1F4A37")
REPORT_GOLD_COLOR:          str = _cfg("report", "gold_color",         "#DDB557")

# ─── ثوابت الألوان (RGBColor) لاستخدامها في التقارير ────────────────────
def _hex_to_rgb(hex_color: str):
    """Converts '#RRGGBB' to RGBColor object."""
    from docx.shared import RGBColor
    h = hex_color.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

COLOR_PRIMARY:     object = _hex_to_rgb(REPORT_INSTITUTIONAL_COLOR)  # أخضر المؤسسة
COLOR_ACCENT:      object = _hex_to_rgb(REPORT_GOLD_COLOR)           # ذهبي المؤسسة
COLOR_TEXT:         object = _hex_to_rgb("#000000")                    # أسود
COLOR_SECONDARY:   object = _hex_to_rgb("#444444")                    # رمادي داكن
COLOR_PRIMARY_HEX: str    = REPORT_INSTITUTIONAL_COLOR.lstrip("#")    # "1F4A37" للـ XML

# ─── OAuth2 User Credentials (للرفع فقط — يتجاوز حصة Service Account) ──
OAUTH_CLIENT_FILE: str = str(BASE_DIR / "oauth_client.json")
OAUTH_TOKEN_FILE:  str = str(BASE_DIR / "token.json")

# ─── إعدادات تسجيل الدخول والتوكن ──────────────────────────────────────────
GUSS_ADMIN_USERNAME: str = os.getenv("GUSS_ADMIN_USERNAME", _cfg("auth", "admin_username", "admin"))
GUSS_ADMIN_PASSWORD: str = os.getenv("GUSS_ADMIN_PASSWORD", _cfg("auth", "admin_password", "guss2026"))
JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", _cfg("auth", "jwt_secret_key", "guss_secret_key_2026_xyz"))
