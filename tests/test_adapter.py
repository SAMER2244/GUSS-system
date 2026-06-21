"""
test_adapter.py — اختبارات وحدوية لمحول البيانات supabase_adapter.py
================================================================
يتحقق من أن adapt_supabase_to_legacy_format تقوم بتحويل بيانات Supabase
إلى الهيكل والقاموس المتوقع تماماً في خط المعالجة القديم.
"""
import pytest
from unittest.mock import patch
from supabase_adapter import adapt_supabase_to_legacy_format


@patch("supabase_adapter.create_signed_url")
def test_adapt_supabase_to_legacy_format(mock_create_signed_url):
    """يتحقق من صحة مفاتيح وبنية البيانات الناتجة من دالة المحول."""
    mock_create_signed_url.return_value = "https://supabase.co/signed-url-plan.pdf"

    submission = {
        "id": 42,
        "created_at": "2026-06-20T12:00:00Z",
        "month": 6,
        "year": 2026,
        "submitter_name": "أحمد صالح",
        "submitter_phone": "0999888777",
        "has_plan": True,
        "plan_file_path": "uploads/20260620_plan.pdf",
        "general_challenges": "شح الموارد المالية وصعوبة التنقل",
        "additional_notes": "يرجى تقديم الدعم العاجل",
        "offices": {"name": "مكتب دمشق"}
    }

    tasks = [
        {
            "id": 10,
            "submission_id": 42,
            "manager_name": "ليلى حسن",
            "manager_phone": "0991111111",
            "task_name": "تنظيم ورشة عمل قانونية",
            "task_description": "ورشة تدريبية حول حقوق الطالب الجامعي",
            "task_type": "ضمن الخطة الشهرية",
            "execution_mechanism": "حضوري في قاعة المؤتمرات",
            "task_status": "مكتملة",
            "issues": "",
            "task_order": 0
        }
    ]

    result = adapt_supabase_to_legacy_format(submission, tasks)

    # 1. التحقق من الحقول الأساسية في القاموس العلوي
    assert result["timestamp"] == "2026-06-20T12:00:00Z"
    assert result["target_month_num"] == 6
    assert result["target_month_name"] == "حزيران"
    assert result["office_name"] == "مكتب دمشق"
    assert result["submitter"] == "أحمد صالح"
    assert result["submitter_phone"] == "0999888777"
    assert result["monthly_plan_link"] == "https://supabase.co/signed-url-plan.pdf"
    assert result["general_challenges"] == "شح الموارد المالية وصعوبة التنقل"
    assert result["additional_notes"] == "يرجى تقديم الدعم العاجل"

    # 2. التحقق من توليد الـ Signed URL للملف
    mock_create_signed_url.assert_called_once_with("monthly-plans", "uploads/20260620_plan.pdf", expires_in=86400)

    # 3. التحقق من هيكل المهام الفرعية والـ Key Mapping
    assert len(result["tasks"]) == 1
    adapted_task = result["tasks"][0]
    assert adapted_task["manager"] == "ليلى حسن"
    assert adapted_task["manager_phone"] == "0991111111"
    assert adapted_task["name"] == "تنظيم ورشة عمل قانونية"
    assert adapted_task["description"] == "ورشة تدريبية حول حقوق الطالب الجامعي"
    assert adapted_task["type"] == "ضمن الخطة الشهرية"
    assert adapted_task["mechanism"] == "حضوري في قاعة المؤتمرات"
    assert adapted_task["status"] == "مكتملة"
    assert adapted_task["issues"] == ""
    assert adapted_task["file_link"] == ""  # حقل Sheets الاحتياطي الفارغ


def test_adapt_supabase_to_legacy_format_with_null_fields():
    """يتحقق من أن القيم الخالية (None/NULL) في الحقول الاختيارية القادمة من قاعدة البيانات يتم تحويلها تلقائياً إلى نصوص فارغة."""
    submission = {
        "id": 43,
        "created_at": None,
        "month": 7,
        "year": 2026,
        "submitter_name": "سامر صالح",
        "submitter_phone": None,
        "has_plan": False,
        "plan_file_path": None,
        "general_challenges": None,
        "additional_notes": None,
        "offices": {"name": "المكتب الاعلامي"}
    }

    tasks = [
        {
            "id": 11,
            "submission_id": 43,
            "manager_name": "أحمد علي",
            "manager_phone": None,
            "task_name": "مهمة تدقيق",
            "task_description": None,
            "task_type": "ضمن الخطة الشهرية",
            "execution_mechanism": None,
            "task_status": "قيد التنفيذ",
            "issues": None,
            "task_order": 0
        }
    ]

    result = adapt_supabase_to_legacy_format(submission, tasks)

    # التحقق من أن القيم None تحولت إلى نصوص فارغة ""
    assert result["timestamp"] == ""
    assert result["submitter_phone"] == ""
    assert result["general_challenges"] == ""
    assert result["additional_notes"] == ""
    assert result["monthly_plan_link"] == ""

    # المهام الفرعية
    assert len(result["tasks"]) == 1
    adapted_task = result["tasks"][0]
    assert adapted_task["manager_phone"] == ""
    assert adapted_task["description"] == ""
    assert adapted_task["mechanism"] == ""
    assert adapted_task["issues"] == ""
