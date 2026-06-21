"""
models.py — Pydantic Models for Form Submissions & Dashboard
=============================================================
نماذج البيانات (Pydantic) لاستقبال وإرجاع بيانات الفورم الشهري
ولوحة التحكم (submissions list/detail/patch/delete).

ملاحظة: النماذج الموجودة في web_server.py (ProcessRequest, LoginRequest, ...) تبقى كما هي.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ─── Task Model ─────────────────────────────────────────────────────────────
class TaskInput(BaseModel):
    """بيانات مهمة واحدة ضمن التقرير الشهري."""

    manager_name: str = Field(
        ...,
        min_length=1,
        description="اسم المسؤول عن المهمة أو المشروع"
    )
    manager_phone: Optional[str] = Field(
        default=None,
        description="رقم هاتف المسؤول"
    )
    task_name: str = Field(
        ...,
        min_length=1,
        description="اسم المهمة أو المشروع"
    )
    task_description: Optional[str] = Field(
        default=None,
        description="وصف قصير يوضح المهمة والهدف منها"
    )
    task_type: str = Field(
        ...,
        description="نوع المهمة: 'ضمن الخطة الشهرية' أو 'خارج الخطة الشهرية'"
    )
    execution_mechanism: Optional[str] = Field(
        default=None,
        description="آلية التنفيذ — شرح الخطوات العملية"
    )
    task_status: str = Field(
        ...,
        description="حالة المهمة: 'مكتملة' أو 'قيد التنفيذ' أو 'ملغاة'"
    )
    issues: Optional[str] = Field(
        default=None,
        description="المشاكل أو العقبات (إن وجدت)"
    )


# ─── Submission Request ─────────────────────────────────────────────────────
class SubmitReportRequest(BaseModel):
    """
    طلب تقديم تقرير شهري جديد.

    يُرسَل من الفورم العام (بدون auth) ويحتوي على جميع بيانات التقرير:
    - بيانات المكتب ومقدم التقرير
    - الشهر والسنة المستهدفين
    - معلومات الخطة الشهرية
    - قائمة المهام (مهمة واحدة على الأقل)
    - التحديات والملاحظات الختامية
    """

    office_name: str = Field(
        ...,
        min_length=1,
        description="اسم المكتب / القسم"
    )
    submitter_name: str = Field(
        ...,
        min_length=1,
        description="الاسم الثلاثي واللقب لمقدم التقرير"
    )
    submitter_phone: Optional[str] = Field(
        default=None,
        description="رقم هاتف مقدم التقرير"
    )
    month: int = Field(
        ...,
        ge=1,
        le=12,
        description="الشهر المستهدف بالتقرير (1-12)"
    )
    year: int = Field(
        ...,
        ge=2020,
        le=2100,
        description="السنة المستهدفة بالتقرير"
    )
    has_plan: bool = Field(
        default=False,
        description="هل لديكم خطة شهرية مكتوبة ومعتمدة لهذا الشهر؟"
    )
    plan_file_path: Optional[str] = Field(
        default=None,
        description="مسار ملف الخطة الشهرية في Supabase Storage (يُملأ بعد الرفع)"
    )
    tasks: List[TaskInput] = Field(
        ...,
        min_length=1,
        description="قائمة المهام — مهمة واحدة على الأقل"
    )
    general_challenges: Optional[str] = Field(
        default=None,
        description="التحديات والملاحظات الإدارية العامة"
    )
    additional_notes: Optional[str] = Field(
        default=None,
        description="ملاحظات إضافية (اختياري)"
    )


# ─── Submission Response ────────────────────────────────────────────────────
class SubmitReportResponse(BaseModel):
    """استجابة ناجحة لتقديم تقرير."""

    status: str = "success"
    submission_id: int
    message: str


# ─── Dashboard Models — Read ─────────────────────────────────────────────────

class SubmissionListItem(BaseModel):
    """عنصر في قائمة التقارير — يُرجعه GET /api/submissions."""

    id: int
    office_name: str
    submitter_name: str
    month: int
    year: int
    status: str
    created_at: str
    drive_report_link: Optional[str] = None


class SubmissionDetail(BaseModel):
    """تفاصيل تقرير كاملة — يُرجعها GET /api/submissions/{id}."""

    id: int
    office_id: int
    office_name: str
    submitter_name: str
    submitter_phone: Optional[str] = None
    month: int
    year: int
    has_plan: bool
    plan_file_path: Optional[str] = None
    general_challenges: Optional[str] = None
    additional_notes: Optional[str] = None
    status: str
    created_at: str
    drive_report_link: Optional[str] = None
    tasks: List[Dict[str, Any]] = []


# ─── Dashboard Models — Patch ────────────────────────────────────────────────

class PatchTaskInput(BaseModel):
    """بيانات مهمة واحدة لاستبدال قائمة المهام عبر PATCH."""

    manager_name: str = Field(..., min_length=1)
    manager_phone: Optional[str] = None
    task_name: str = Field(..., min_length=1)
    task_description: Optional[str] = None
    task_type: str = Field(...)
    execution_mechanism: Optional[str] = None
    task_status: str = Field(...)
    issues: Optional[str] = None


class PatchSubmissionRequest(BaseModel):
    """
    طلب تعديل تقرير موجود — PATCH /api/submissions/{id}.

    جميع الحقول اختيارية؛ يُعدَّل فقط ما يُرسَل.
    إذا أُرسلت tasks يجب أن تحتوي عنصراً واحداً على الأقل.
    """

    submitter_name: Optional[str] = None
    submitter_phone: Optional[str] = None
    general_challenges: Optional[str] = None
    additional_notes: Optional[str] = None
    month: Optional[int] = Field(default=None, ge=1, le=12)
    year: Optional[int] = Field(default=None, ge=2020, le=2100)
    tasks: Optional[List[PatchTaskInput]] = None

