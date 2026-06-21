"""
routes/dashboard.py — Dashboard Endpoints (Admin Only)
=======================================================
يوفر endpoints إدارية محمية بـ JWT لعرض وتعديل وحذف التقارير.

Endpoints:
    GET    /api/submissions          — قائمة التقارير بفلترة اختيارية
    GET    /api/submissions/{id}     — تفاصيل تقرير واحد + مهامه
    PATCH  /api/submissions/{id}     — تعديل حقول التقرير و/أو استبدال مهامه
    DELETE /api/submissions/{id}     — حذف تقرير (CASCADE للمهام + حذف PDF من Storage)

الحماية: جميع الـ endpoints تتطلب JWT cookie صالح (guss_session)
         عبر نفس دالة get_current_user المستخدمة في web_server.py.
"""

from __future__ import annotations

import traceback
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from database import get_supabase_client
from logger import get_logger
from models import (
    PatchSubmissionRequest,
    SubmissionDetail,
    SubmissionListItem,
)

_log = get_logger("dashboard")

router = APIRouter(prefix="/api", tags=["dashboard"])


# ─── Auth dependency (imported lazily to avoid circular import) ──────────────
def _get_current_user(request: Request) -> str:
    """
    تفويض آمن لدالة get_current_user من web_server.
    يُستورد محلياً لتفادي الاستيراد الدائري.
    """
    from web_server import get_current_user  # noqa: PLC0415
    return get_current_user(request)


# ─── GET /api/submissions ────────────────────────────────────────────────────
@router.get("/submissions")
def api_list_submissions(
    office_id: Optional[int] = Query(default=None, description="فلترة بمعرّف المكتب"),
    month: Optional[int] = Query(default=None, ge=1, le=12, description="فلترة بالشهر (1-12)"),
    year: Optional[int] = Query(default=None, ge=2020, le=2100, description="فلترة بالسنة"),
    status: Optional[str] = Query(default=None, description="فلترة بالحالة: pending / processed / failed"),
    current_user: str = Depends(_get_current_user),
):
    """
    جلب قائمة التقارير من Supabase مع إمكانية الفلترة الاختيارية.

    يدعم الفلترة بـ: office_id, month, year, status (منفردةً أو مجتمعةً).
    يُرجع: id, office_name, submitter_name, month, year, status,
            created_at, drive_report_link.
    """
    try:
        db = get_supabase_client()
        query = db.table("submissions").select(
            "id, submitter_name, month, year, status, created_at, "
            "drive_report_link, offices(name)"
        )

        if office_id is not None:
            query = query.eq("office_id", office_id)
        if month is not None:
            query = query.eq("month", month)
        if year is not None:
            query = query.eq("year", year)
        if status is not None:
            query = query.eq("status", status)

        result = query.order("created_at", desc=True).execute()
        rows = result.data or []

        items = []
        for row in rows:
            office_name = ""
            if row.get("offices"):
                office_name = row["offices"].get("name", "")
            items.append(
                SubmissionListItem(
                    id=row["id"],
                    office_name=office_name,
                    submitter_name=row.get("submitter_name", ""),
                    month=row["month"],
                    year=row["year"],
                    status=row["status"],
                    created_at=str(row.get("created_at", "")),
                    drive_report_link=row.get("drive_report_link"),
                )
            )

        return {"submissions": [item.model_dump() for item in items], "total": len(items)}

    except Exception as e:
        _log.error("Error fetching submissions list: %s\n%s", e, traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطأ أثناء جلب قائمة التقارير: {str(e)}"
        )


# ─── GET /api/submissions/{id} ───────────────────────────────────────────────
@router.get("/submissions/{submission_id}")
def api_get_submission(
    submission_id: int,
    current_user: str = Depends(_get_current_user),
):
    """
    جلب تفاصيل تقرير واحد كاملة مع قائمة مهامه.

    يُرجع: جميع أعمدة submissions + قائمة tasks المرتبطة مرتبةً بـ task_order.
    """
    try:
        db = get_supabase_client()

        sub_res = (
            db.table("submissions")
            .select("*, offices(name)")
            .eq("id", submission_id)
            .execute()
        )

        if not sub_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"التقرير رقم {submission_id} غير موجود."
            )

        row = sub_res.data[0]
        office_name = ""
        if row.get("offices"):
            office_name = row["offices"].get("name", "")

        tasks_res = (
            db.table("tasks")
            .select("*")
            .eq("submission_id", submission_id)
            .order("task_order")
            .execute()
        )
        tasks = tasks_res.data or []

        detail = SubmissionDetail(
            id=row["id"],
            office_id=row["office_id"],
            office_name=office_name,
            submitter_name=row.get("submitter_name", ""),
            submitter_phone=row.get("submitter_phone"),
            month=row["month"],
            year=row["year"],
            has_plan=row.get("has_plan", False),
            plan_file_path=row.get("plan_file_path"),
            general_challenges=row.get("general_challenges"),
            additional_notes=row.get("additional_notes"),
            status=row["status"],
            created_at=str(row.get("created_at", "")),
            drive_report_link=row.get("drive_report_link"),
            tasks=tasks,
        )

        return detail.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        _log.error("Error fetching submission %s: %s\n%s", submission_id, e, traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطأ أثناء جلب بيانات التقرير: {str(e)}"
        )


# ─── PATCH /api/submissions/{id} ────────────────────────────────────────────
@router.patch("/submissions/{submission_id}")
def api_patch_submission(
    submission_id: int,
    request: PatchSubmissionRequest,
    current_user: str = Depends(_get_current_user),
):
    """
    تعديل تقرير موجود — يُعدَّل فقط ما يُرسَل.

    إذا أُرسل tasks:
      - يجب أن تحتوي القائمة عنصراً واحداً على الأقل (وإلا خطأ 400).
      - تُحذف جميع المهام القديمة وتُدرج الجديدة بترتيب صحيح.

    الحقول القابلة للتعديل:
        submitter_name, submitter_phone, general_challenges,
        additional_notes, month, year, tasks
    """
    try:
        db = get_supabase_client()

        # ── التحقق من وجود التقرير ─────────────────────────────────────────
        check_res = (
            db.table("submissions")
            .select("id")
            .eq("id", submission_id)
            .execute()
        )
        if not check_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"التقرير رقم {submission_id} غير موجود."
            )

        # ── التحقق من قائمة المهام إذا أُرسلت ──────────────────────────────
        if request.tasks is not None and len(request.tasks) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="يجب أن يحتوي التقرير على مهمة واحدة على الأقل. "
                       "لا يمكن تقديم قائمة مهام فارغة."
            )

        # ── بناء payload الـ submission ────────────────────────────────────
        update_data: dict = {}
        if request.submitter_name is not None:
            update_data["submitter_name"] = request.submitter_name.strip()
        if request.submitter_phone is not None:
            update_data["submitter_phone"] = request.submitter_phone.strip() or None
        if request.general_challenges is not None:
            update_data["general_challenges"] = request.general_challenges.strip() or None
        if request.additional_notes is not None:
            update_data["additional_notes"] = request.additional_notes.strip() or None
        if request.month is not None:
            update_data["month"] = request.month
        if request.year is not None:
            update_data["year"] = request.year

        # ── تحديث submission (إذا وجد شيء للتحديث) ───────────────────────
        if update_data:
            db.table("submissions").update(update_data).eq("id", submission_id).execute()
            _log.info("Submission %s updated: %s", submission_id, list(update_data.keys()))

        # ── استبدال المهام (إذا أُرسلت) ────────────────────────────────────
        if request.tasks is not None:
            # حذف المهام القديمة
            db.table("tasks").delete().eq("submission_id", submission_id).execute()

            # إدراج المهام الجديدة
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

            db.table("tasks").insert(tasks_data).execute()
            _log.info(
                "Tasks replaced for submission %s: %d new tasks",
                submission_id, len(tasks_data)
            )

        return {"status": "success", "message": "تم تحديث التقرير بنجاح."}

    except HTTPException:
        raise
    except Exception as e:
        _log.error("Error patching submission %s: %s\n%s", submission_id, e, traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطأ أثناء تحديث التقرير: {str(e)}"
        )


# ─── DELETE /api/submissions/{id} ────────────────────────────────────────────
@router.delete("/submissions/{submission_id}")
def api_delete_submission(
    submission_id: int,
    current_user: str = Depends(_get_current_user),
):
    """
    حذف تقرير من قاعدة البيانات.

    السلوك:
    1. يتحقق من وجود plan_file_path — إذا موجود يحاول حذف الملف من
       Supabase Storage bucket "monthly-plans" (فشل الحذف لا يوقف العملية).
    2. يحذف السطر من submissions — المهام تُحذف تلقائياً عبر CASCADE.
    """
    try:
        db = get_supabase_client()

        # ── التحقق من وجود التقرير وجلب plan_file_path ────────────────────
        check_res = (
            db.table("submissions")
            .select("id, plan_file_path")
            .eq("id", submission_id)
            .execute()
        )
        if not check_res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"التقرير رقم {submission_id} غير موجود."
            )

        plan_file_path: str | None = check_res.data[0].get("plan_file_path")

        # ── حذف ملف الخطة من Storage (إن وجد) ────────────────────────────
        if plan_file_path:
            try:
                db.storage.from_("monthly-plans").remove([plan_file_path])
                _log.info(
                    "🗑️  Plan file deleted from Storage for submission %s: %s",
                    submission_id, plan_file_path
                )
            except Exception as storage_err:
                _log.warning(
                    "⚠️  Failed to delete plan file '%s' from Storage (submission %s): %s. "
                    "Continuing with DB deletion.",
                    plan_file_path, submission_id, storage_err
                )

        # ── حذف التقرير من قاعدة البيانات (CASCADE يحذف tasks) ────────────
        db.table("submissions").delete().eq("id", submission_id).execute()
        _log.info("✅ Submission %s deleted (with cascaded tasks).", submission_id)

        return {"status": "success", "message": f"تم حذف التقرير رقم {submission_id} بنجاح."}

    except HTTPException:
        raise
    except Exception as e:
        _log.error("Error deleting submission %s: %s\n%s", submission_id, e, traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"خطأ أثناء حذف التقرير: {str(e)}"
        )
