"""
test_data_parser.py — اختبارات وحدوية لـ data_parser.py
=======================================================
تختبر دالة get_task_statistics() بالإحصائيات والبيانات المهيكلة للمكتب.
"""
import pytest
from data_parser import get_task_statistics


class TestGetTaskStatistics:
    """مجموعة اختبارات get_task_statistics()."""

    def test_mixed_statuses(self):
        """يختبر الإحصائيات مع حالات مختلطة."""
        office_data = {
            "tasks": [
                {"status": "مكتملة", "issues": ""},
                {"status": "قيد التنفيذ", "issues": "تأخر المورد"},
                {"status": "جارٍ العمل عليها", "issues": ""}
            ]
        }
        stats = get_task_statistics(office_data)

        assert stats["total"] == 3
        assert stats["completed"] == 1
        assert stats["in_progress"] == 2
        assert stats["pending"] == 0
        assert stats["has_issues"] == 1
        assert stats["completion_rate"] == 33.3

    def test_empty_tasks(self):
        """يختبر الإحصائيات بدون مهام."""
        data = {"tasks": []}
        stats = get_task_statistics(data)

        assert stats["total"] == 0
        assert stats["completed"] == 0
        assert stats["in_progress"] == 0
        assert stats["pending"] == 0
        assert stats["has_issues"] == 0
        assert stats["completion_rate"] == 0.0

    def test_completion_rate(self):
        """يتحقق من صحة حساب نسبة الإنجاز والتقريب."""
        office_data = {
            "tasks": [
                {"status": "مكتملة", "issues": ""},
                {"status": "قيد التنفيذ", "issues": ""}
            ]
        }
        stats = get_task_statistics(office_data)

        # مهمة 1 مكتملة من أصل 2 -> 50.0%
        assert stats["completion_rate"] == 50.0
