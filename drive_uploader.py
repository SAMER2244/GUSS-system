"""
drive_uploader.py  —  V2.3 (Logging + Exceptions)
====================================================
يرفع التقرير والمرفقات إلى Google Drive ضمن هيكلية:

    ROOT → [السنة] → نظام_المتابعة_الدورية → [المكتب] → [الشهر]
                                                              ├── التقرير.docx
                                                              ├── مرفق_مهمة_1
                                                              └── مرفق_مهمة_2

القواعد:
    - لا تكرار مجلدات (Strict No-Duplicate).
    - استبدال التقرير القديم بنفس الاسم تلقائيًا.
    - نسخ المرفقات مباشرةً على Drive (بدون تحميل محلي).
    - أي فشل في مرفق لا يوقف العملية الكاملة.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import config as cfg
from logger import get_logger
from exceptions import DriveUploadError

_log = get_logger("drive")


# ─── MIME Types ──────────────────────────────────────────────────────────────
_FOLDER_MIME = "application/vnd.google-apps.folder"
_DOCX_MIME   = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
_PDF_MIME    = "application/pdf"
_UPLOAD_SCOPES = ["https://www.googleapis.com/auth/drive"]

# أسماء الشهور بالعربية
_MONTHS_AR = [
    "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
    "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
]


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _current_month_folder() -> str:
    """يُعيد اسم مجلد الشهر الحالي بالعربية، مثال: مارس_2026."""
    now = datetime.now()
    return f"{_MONTHS_AR[now.month - 1]}_{now.year}"


def _extract_drive_id(url: str) -> str | None:
    """
    يستخرج file_id من أي صيغة رابط Google Drive.

    يدعم:
      - https://drive.google.com/file/d/{ID}/view
      - https://drive.google.com/open?id={ID}
      - https://docs.google.com/.../d/{ID}/...
    """
    if not url:
        return None
    patterns = [
        r"/d/([a-zA-Z0-9_-]{10,})",
        r"[?&]id=([a-zA-Z0-9_-]{10,})",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


# ─── OAuth2 Service Builder ───────────────────────────────────────────────────
def _build_oauth_service():
    """
    يبني خدمة Drive v3 بـ OAuth2 User Credentials.
    - أول تشغيل:  يفتح المتصفح → يحفظ token.json
    - التشغيلات اللاحقة: يُحمِّل التوكن ويُجدِّده تلقائياً
    - إذا انتهى التوكن أو أُلغي: يحذفه ويُعيد المصادقة تلقائياً
    """
    token_path  = Path(cfg.OAUTH_TOKEN_FILE)
    client_path = Path(cfg.OAUTH_CLIENT_FILE)

    creds: Credentials | None = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), _UPLOAD_SCOPES)

    # تجديد التوكن إن انتهت صلاحيته
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds, token_path)
        except Exception as refresh_err:
            # invalid_grant أو أي خطأ تجديد → نحذف التوكن ونُعيد التفويض
            _log.info("   🔄 Token expired/invalid (%s) — re-authorizing...", refresh_err.__class__.__name__)
            token_path.unlink(missing_ok=True)
            creds = None

    # فتح المتصفح إذا لم يوجد توكن صالح
    if not creds or not creds.valid:
        if not client_path.exists():
            raise DriveUploadError(
                f"❌ ملف OAuth غير موجود: {client_path}\n"
                "   حمّله من: Google Cloud Console → OAuth 2.0 Client IDs → Desktop App"
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(client_path), _UPLOAD_SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)
        _save_token(creds, token_path)

    return build("drive", "v3", credentials=creds, cache_discovery=False)



def _save_token(creds: Credentials, token_path: Path) -> None:
    with open(token_path, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    _log.debug("💾 token.json saved")


# ─── Folder Helpers ───────────────────────────────────────────────────────────
def _find_folder(service, name: str, parent_id: str) -> str | None:
    """يبحث عن مجلد بالاسم داخل parent_id. يُعيد folder_id أو None."""
    escaped = name.replace("'", "\\'")
    query = (
        f"mimeType='{_FOLDER_MIME}' "
        f"and name='{escaped}' "
        f"and '{parent_id}' in parents "
        f"and trashed=false"
    )
    result = (
        service.files()
        .list(
            q=query,
            fields="files(id, name)",
            spaces="drive",
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        )
        .execute()
    )
    files = result.get("files", [])
    return files[0]["id"] if files else None


def _create_folder(service, name: str, parent_id: str) -> str:
    """يُنشئ مجلدًا جديداً ويُعيد folder_id."""
    meta = {"name": name, "mimeType": _FOLDER_MIME, "parents": [parent_id]}
    return (
        service.files()
        .create(body=meta, fields="id", supportsAllDrives=True)
        .execute()["id"]
    )


def _get_or_create_folder(service, name: str, parent_id: str) -> str:
    """يُعيد folder_id — يبحث أولاً، وينشئ فقط إذا لم يجد."""
    existing = _find_folder(service, name, parent_id)
    if existing:
        _log.debug("📁 Existing folder: '%s'", name)
        return existing
    new_id = _create_folder(service, name, parent_id)
    _log.info("📁 Created folder: '%s'  → %s", name, new_id)
    return new_id


# ─── File Helpers ─────────────────────────────────────────────────────────────
def _find_file(service, name: str, parent_id: str) -> str | None:
    """يبحث عن ملف بالاسم داخل parent_id. يُعيد file_id أو None."""
    escaped = name.replace("'", "\\'")
    query = (
        f"name='{escaped}' "
        f"and '{parent_id}' in parents "
        f"and trashed=false"
    )
    result = (
        service.files()
        .list(
            q=query,
            fields="files(id, name)",
            spaces="drive",
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        )
        .execute()
    )
    files = result.get("files", [])
    return files[0]["id"] if files else None


def _delete_file(service, file_id: str) -> None:
    """يحذف ملفًا."""
    service.files().delete(fileId=file_id, supportsAllDrives=True).execute()
    _log.debug("🗑️  Old file deleted: %s", file_id)


# ─── Attachments ──────────────────────────────────────────────────────────────
def _copy_attachments(service, tasks: list[dict], month_id: str) -> None:
    """
    ينسخ مرفقات المهام مباشرةً إلى مجلد الشهر على Drive (بدون تحميل محلي).

    لكل مهمة: يستخرج file_id من file_link، ثم يستخدم files().copy()
    لنقل الملف إلى month_id. إذا فشل مرفق يكمل الباقي.
    """
    copied = 0
    for task in tasks:
        link = task.get("file_link", "").strip()
        if not link:
            continue

        file_id = _extract_drive_id(link)
        if not file_id:
            _log.warning("⚠️  Could not extract ID from link: %s", link[:60])
            continue

        try:
            # جلب اسم الملف الأصلي
            meta = (
                service.files()
                .get(fileId=file_id, fields="name", supportsAllDrives=True)
                .execute()
            )
            file_name = meta.get("name", f"مرفق_{task.get('name', 'مهمة')}")

            # نسخ مباشر إلى مجلد الشهر
            service.files().copy(
                fileId=file_id,
                body={"name": file_name, "parents": [month_id]},
                supportsAllDrives=True,
                fields="id",
            ).execute()

            _log.info("📎 Attachment copied: %s", file_name)
            copied += 1

        except Exception as e:
            task_name = task.get("name", "")
            _log.warning("⚠️  Failed to copy attachment «%s»: %s", task_name, e)

    if copied:
        _log.info("📎 Total attachments copied: %d", copied)


# ─── Main Upload Function ─────────────────────────────────────────────────────
def upload_report(
    local_path: str | Path,
    office_name: str,
    office_data: dict | None = None,
) -> str:
    """
    يرفع التقرير والمرفقات إلى المسار الهرمي المُحدَّث على Drive.

    المسار:
        ROOT → [السنة] → نظام_المتابعة_الدورية → [المكتب] → [الشهر]

    Args:
        local_path:  المسار المحلي لملف .docx
        office_name: اسم المكتب
        office_data: البيانات الكاملة للمكتب (للوصول إلى روابط المرفقات)

    Returns:
        file_id التقرير المرفوع.
    """
    local_path = Path(local_path)
    if not local_path.exists():
        raise DriveUploadError(f"الملف غير موجود: {local_path}")

    _log.info("☁️  Building Drive service (OAuth2)...")
    service = _build_oauth_service()

    current_year  = str(datetime.now().year)
    if office_data and office_data.get("target_month_name"):
        current_month = f"{office_data['target_month_name']}_{current_year}"
    else:
        current_month = _current_month_folder()
    _log.debug("📂 Root  ->  %s", cfg.ROOT_FOLDER_ID)

    # ── بناء الهيكلية الهرمية ────────────────────────────────────────────
    year_id   = _get_or_create_folder(service, current_year,            cfg.ROOT_FOLDER_ID)
    system_id = _get_or_create_folder(service, cfg.DRIVE_SYSTEM_FOLDER, year_id)
    office_id = _get_or_create_folder(service, office_name,             system_id)
    month_id  = _get_or_create_folder(service, current_month,           office_id)

    # ── استبدال التقرير القديم إن وُجد ──────────────────────────────────
    file_name   = local_path.name
    old_file_id = _find_file(service, file_name, month_id)
    if old_file_id:
        _delete_file(service, old_file_id)

    # ── رفع التقرير الجديد ───────────────────────────────────────────────
    file_meta = {"name": file_name, "parents": [month_id]}
    media = MediaFileUpload(str(local_path), mimetype=_DOCX_MIME, resumable=False)
    uploaded = (
        service.files()
        .create(
            body=file_meta,
            media_body=media,
            fields="id, webViewLink",
            supportsAllDrives=True,
        )
        .execute()
    )

    file_id   = uploaded.get("id", "")
    view_link = uploaded.get("webViewLink", "")
    _log.info("✅ Report uploaded: %s", file_name)
    _log.info("🔗 %s", view_link)

    # ── V2.3: رفع نسخة PDF مرآتية إن وُجدت ──────────────────────────────────
    pdf_path = local_path.with_suffix(".pdf")
    if pdf_path.exists():
        pdf_name = pdf_path.name
        # حذف النسخة القديمة إن وُجدت
        old_pdf_id = _find_file(service, pdf_name, month_id)
        if old_pdf_id:
            _delete_file(service, old_pdf_id)

        pdf_meta = {"name": pdf_name, "parents": [month_id]}
        pdf_media = MediaFileUpload(str(pdf_path), mimetype=_PDF_MIME, resumable=False)
        service.files().create(
            body=pdf_meta,
            media_body=pdf_media,
            fields="id",
            supportsAllDrives=True
        ).execute()
        _log.info("✅ PDF mirror uploaded: %s", pdf_name)

    # ── نسخ مرفقات المهام ────────────────────────────────────────────────
    if office_data:
        tasks = office_data.get("tasks", [])
        tasks_with_links = [t for t in tasks if t.get("file_link", "").strip()]
        if tasks_with_links:
            _log.info("📎 Copying %d attachments...", len(tasks_with_links))
            _copy_attachments(service, tasks_with_links, month_id)
        else:
            _log.debug("📎 No task attachments found.")

    return file_id
