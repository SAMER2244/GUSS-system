"""
data_parser.py
==============
يحتوي على الدوال الإحصائية والأنواع المشتركة المستخدمة في طبقة الذكاء الاصطناعي والتقارير.
تم تنظيفه وإزالة دوال تحليل صفوف Google Sheets القديمة.
"""

from __future__ import annotations
from typing import Any

OfficeData = dict[str, Any]


def _is_empty(value: str) -> bool:
    """True إذا كانت القيمة فارغة أو تحتوي فراغات فقط."""
    return not value or not value.strip()


def get_task_statistics(office_data: OfficeData) -> dict[str, Any]:
    """
    يُنشئ إحصائيات سريعة عن مهام المكتب (مفيدة لـ AI prompt).

    Args:
        office_data: البيانات المهيكلة للمكتب.

    Returns:
        قاموس بالإحصائيات.
    """
    tasks = office_data.get("tasks", [])
    if not tasks:
        return {"total": 0, "completed": 0, "in_progress": 0, "pending": 0,
                "has_issues": 0, "completion_rate": 0.0}

    completed  = sum(1 for t in tasks if t.get("status") and ("مكتمل" in t["status"] or "منجز" in t["status"]))
    in_progress= sum(1 for t in tasks if t.get("status") and ("جارٍ" in t["status"] or "قيد" in t["status"]))
    has_issues = sum(1 for t in tasks if not _is_empty(t.get("issues", "")))

    return {
        "total":           len(tasks),
        "completed":       completed,
        "in_progress":     in_progress,
        "pending":         len(tasks) - completed - in_progress,
        "has_issues":      has_issues,
        "completion_rate": round(completed / len(tasks) * 100, 1),
    }
