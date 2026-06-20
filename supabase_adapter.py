"""
supabase_adapter.py
===================
يحتوي على دالة المحول لتوطين بيانات Supabase وتمريرها بالصيغة القديمة المتوافقة مع خط أنابيب المعالجة.
"""

from __future__ import annotations
from typing import Any, List, Dict
from database import create_signed_url

MONTH_MAP = {
    1: 'كانون الثاني', 2: 'شباط', 3: 'آذار', 4: 'نيسان',
    5: 'أيار', 6: 'حزيران', 7: 'تموز', 8: 'آب',
    9: 'أيلول', 10: 'تشرين الأول', 11: 'تشرين الثاني', 12: 'كانون الأول'
}


def adapt_supabase_to_legacy_format(submission: Dict[str, Any], tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    تحويل بيانات التقرير والمهام من تنسيق Supabase إلى التنسيق المتوقع في خط أنابيب المعالجة (data_parser).

    Args:
        submission: قاموس يحتوي على بيانات التقرير الأساسية من جدول submissions.
        tasks: قائمة قواميس تحتوي على المهام المرتبطة بالتقرير من جدول tasks.

    Returns:
        قاموس ببيانات التقرير المهيكلة والمتوافقة مع خط الأنابيب القديم.
    """
    # 1. تحديد اسم المكتب (سواء كان ممرراً مباشرة أو مستخرجاً من كائن المكتب المرتبط)
    office_name = submission.get("office_name")
    if not office_name and "offices" in submission:
        office_name = submission["offices"].get("name") if submission["offices"] else "Unknown Office"
    if not office_name:
        office_name = "Unknown Office"

    # 2. توليد رابط موقع مؤقت (Signed URL) لملف PDF الخطة الشهرية إن وجد
    plan_file_path = submission.get("plan_file_path")
    has_plan = submission.get("has_plan", False)
    monthly_plan_link = ""

    if has_plan and plan_file_path:
        try:
            # توليد رابط موقع صالح لمدة 24 ساعة (86400 ثانية) لتجنب انتهاء الصلاحية أثناء المعالجة الطويلة
            monthly_plan_link = create_signed_url("monthly-plans", plan_file_path, expires_in=86400)
        except Exception as e:
            # في حال الفشل نترك الرابط فارغاً مع تسجيل تحذير بالخلفية
            print(f"⚠️ Warning: Failed to generate signed URL for {plan_file_path}: {e}")
            monthly_plan_link = ""

    month_num = submission.get("month", 1)

    legacy_data = {
        "timestamp":         str(submission.get("created_at", "")),
        "target_month_num":  month_num,
        "target_month_name": MONTH_MAP.get(month_num, ""),
        "office_name":       office_name,
        "submitter":         submission.get("submitter_name", ""),
        "submitter_phone":   submission.get("submitter_phone", ""),
        "monthly_plan_link": monthly_plan_link,
        "general_challenges":submission.get("general_challenges", ""),
        "additional_notes":  submission.get("additional_notes", ""),
        "tasks":             []
    }

    # 3. تحويل المهام لتطابق التسميات القديمة
    for t in tasks:
        legacy_data["tasks"].append({
            "manager":       t.get("manager_name", ""),
            "manager_phone": t.get("manager_phone", ""),
            "name":          t.get("task_name", ""),
            "description":   t.get("task_description", ""),
            "type":          t.get("task_type", ""),
            "mechanism":     t.get("execution_mechanism", ""),
            "status":        t.get("task_status", ""),
            "issues":        t.get("issues", ""),
            "file_link":     ""  # حقل احتياطي فارغ متوافق مع Sheets
        })

    return legacy_data
