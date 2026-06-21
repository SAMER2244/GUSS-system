"""
routes/submissions.py — Form Submission Endpoint
=================================================
يوفر endpoint عام (بدون auth) لاستقبال التقارير الشهرية من الفورم المستقل.
يخزّن البيانات في Supabase (offices → submissions → tasks).

Endpoint:
    POST /api/submit-report — تقديم تقرير شهري جديد
    GET  /api/offices-list  — قائمة المكاتب المتاحة (للقائمة المنسدلة)
    POST /api/upload-plan   — رفع ملف الخطة الشهرية PDF
"""

from __future__ import annotations

import json
import traceback
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status, BackgroundTasks
from fastapi.responses import JSONResponse

from database import get_supabase_client, create_signed_url
from models import SubmitReportRequest, SubmitReportResponse
from logger import get_logger

_log = get_logger("submissions")

router = APIRouter(prefix="/api", tags=["submissions"])


# ─── GET /api/offices-list ──────────────────────────────────────────────────
@router.get("/offices-list")
def api_offices_list():
    """
    جلب قائمة المكاتب المتاحة من قاعدة البيانات.
    يُستخدم لملء القائمة المنسدلة في الفورم العام (بدون auth).
    """
    try:
        db = get_supabase_client()
        result = db.table("offices").select("id, name").order("name").execute()
        return {"offices": result.data}

    except RuntimeError as e:
        _log.error(f"Database connection error in offices-list: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="خدمة قاعدة البيانات غير متاحة حالياً. يرجى المحاولة لاحقاً."
        )
    except Exception as e:
        _log.error(f"Unexpected error fetching offices list: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="حدث خطأ غير متوقع أثناء جلب قائمة المكاتب."
        )


# ─── POST /api/upload-plan ──────────────────────────────────────────────────
@router.post("/upload-plan")
async def api_upload_plan(file: UploadFile = File(...)):
    """
    رفع ملف الخطة الشهرية (PDF) إلى Supabase Storage.
    يُرجع مسار الملف في Storage لاستخدامه عند تقديم التقرير.

    القيود:
    - صيغة PDF فقط
    - حجم أقصى: 10 ميغابايت
    """
    # ── التحقق من نوع الملف ──
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="يُسمح فقط بملفات PDF. نوع الملف المُرسل غير صالح."
        )

    # ── قراءة محتوى الملف ──
    try:
        contents = await file.read()
    except Exception as e:
        _log.error(f"Failed to read uploaded file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="فشلت قراءة الملف المُرفق."
        )

    # ── التحقق من الحجم (10 MB) ──
    max_size = 10 * 1024 * 1024  # 10 MB
    if len(contents) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="حجم الملف يتجاوز الحد الأقصى المسموح (10 ميغابايت)."
        )

    # ── توليد اسم فريد للملف ──
    unique_id = uuid.uuid4().hex[:12]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = f"{timestamp}_{unique_id}.pdf"

    # ── الرفع إلى Supabase Storage ──
    try:
        db = get_supabase_client()
        db.storage.from_("monthly-plans").upload(
            path=file_path,
            file=contents,
            file_options={"content-type": "application/pdf"}
        )
        _log.info(f"✅ Plan PDF uploaded: {file_path} ({len(contents)} bytes)")

        return {
            "status": "success",
            "file_path": file_path,
            "message": "تم رفع ملف الخطة الشهرية بنجاح."
        }

    except Exception as e:
        _log.error(f"Failed to upload plan PDF: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"فشل رفع الملف إلى التخزين السحابي: {str(e)}"
        )


# ─── POST /api/submit-report ────────────────────────────────────────────────
@router.post("/submit-report", response_model=SubmitReportResponse)
def api_submit_report(request: SubmitReportRequest, background_tasks: BackgroundTasks):
    """
    استقبال تقرير شهري جديد من الفورم العام (بدون auth).

    المنطق:
    1. التحقق من وجود المكتب في جدول offices
    2. إنشاء سطر في submissions بحالة 'pending'
    3. إنشاء أسطر المهام في tasks
    4. إرجاع submission_id عند النجاح
    """
    try:
        db = get_supabase_client()

        # ── 1. التحقق من وجود المكتب ────────────────────────────────────
        office_result = (
            db.table("offices")
            .select("id")
            .eq("name", request.office_name)
            .execute()
        )

        if not office_result.data:
            _log.warning(f"Submission rejected — unknown office: '{request.office_name}'")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"المكتب '{request.office_name}' غير مسجل في النظام. "
                       f"يرجى اختيار مكتب من القائمة المتاحة."
            )

        office_id = office_result.data[0]["id"]

        # ── 2. إنشاء سطر التقرير في submissions ────────────────────────
        submission_data = {
            "office_id": office_id,
            "submitter_name": request.submitter_name.strip(),
            "submitter_phone": (request.submitter_phone or "").strip() or None,
            "month": request.month,
            "year": request.year,
            "has_plan": request.has_plan,
            "plan_file_path": (request.plan_file_path or "").strip() or None,
            "general_challenges": (request.general_challenges or "").strip() or None,
            "additional_notes": (request.additional_notes or "").strip() or None,
            "status": "pending",
        }

        submission_result = (
            db.table("submissions")
            .insert(submission_data)
            .execute()
        )

        if not submission_result.data:
            raise RuntimeError("فشل إنشاء سطر التقرير في قاعدة البيانات.")

        submission_id = submission_result.data[0]["id"]
        _log.info(
            f"📝 Submission created: id={submission_id}, "
            f"office='{request.office_name}', month={request.month}/{request.year}"
        )

        # ── 3. إنشاء أسطر المهام في tasks ──────────────────────────────
        tasks_data = []
        for idx, task in enumerate(request.tasks, start=1):
            tasks_data.append({
                "submission_id": submission_id,
                "task_order": idx,
                "manager_name": task.manager_name.strip(),
                "manager_phone": (task.manager_phone or "").strip() or None,
                "task_name": task.task_name.strip(),
                "task_description": (task.task_description or "").strip() or None,
                "task_type": task.task_type.strip(),
                "execution_mechanism": (task.execution_mechanism or "").strip() or None,
                "task_status": task.task_status.strip(),
                "issues": (task.issues or "").strip() or None,
            })

        if tasks_data:
            tasks_result = db.table("tasks").insert(tasks_data).execute()
            _log.info(f"   ✅ {len(tasks_data)} tasks inserted for submission {submission_id}")

        # ── 4. تشغيل المعالجة بالخلفية تلقائياً ──
        try:
            from web_server import _background_pipeline_runner
            background_tasks.add_task(_background_pipeline_runner, submission_id=submission_id)
            _log.info(f"   🚀 Automatically queued background processing for submission {submission_id}")
        except Exception as bg_err:
            _log.error(f"⚠️ Failed to queue background processing for submission {submission_id}: {bg_err}")

        # ── 5. إرجاع الاستجابة الناجحة ─────────────────────────────────
        return SubmitReportResponse(
            status="success",
            submission_id=submission_id,
            message=f"تم تقديم التقرير بنجاح وتفعيل المعالجة بالخلفية. رقم التقرير: {submission_id}"
        )

    except HTTPException:
        # إعادة رفع أخطاء HTTP كما هي (مثل 404 للمكتب غير الموجود)
        raise

    except Exception as e:
        _log.error(f"❌ Failed to submit report: {e}\n{traceback.format_exc()}")

        # التحقق من أخطاء التكرار (UNIQUE constraint)
        error_str = str(e).lower()
        if "unique" in error_str or "duplicate" in error_str or "23505" in error_str:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"يوجد تقرير مسجل مسبقاً لهذا المكتب عن شهر {request.month}/{request.year}. "
                       f"لا يمكن تقديم تقرير مكرر لنفس الفترة."
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"حدث خطأ غير متوقع أثناء حفظ التقرير: {str(e)}"
        )
