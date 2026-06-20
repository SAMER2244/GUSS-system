"""
test_report_generator.py — اختبارات وحدوية لـ report_generator.py
==================================================================
تختبر _extract_task_insights() و _normalize() بدون اتصال شبكي.
"""
import json
import pytest
from report_generator import _extract_task_insights, _normalize


class TestNormalize:
    """اختبارات _normalize()."""

    def test_removes_spaces(self):
        assert _normalize("مهمة أولى") == _normalize("مهمةأولى")

    def test_case_insensitive(self):
        assert _normalize("Hello World") == _normalize("hello world")

    def test_removes_rtl_marks(self):
        assert _normalize("\u200fمهمة\u200e") == _normalize("مهمة")


class TestExtractTaskInsights:
    """اختبارات _extract_task_insights()."""

    def test_valid_json_block(self):
        """JSON صحيح داخل كتلة ```json ... ```."""
        ai_text = '''
        Here is the analysis:
        ```json
        [
            {"task_id": "1", "original_name": "تنظيم ندوة", "ai_insight": "تم بنجاح"},
            {"task_id": "2", "original_name": "ورشة عمل", "ai_insight": "بحاجة لمتابعة"}
        ]
        ```
        '''
        result = _extract_task_insights(ai_text)

        assert "by_id" in result
        assert "by_name" in result
        assert "by_id_arabic" in result
        assert "by_norm" in result
        assert "1" in result["by_id"]
        assert "2" in result["by_id"]
        assert result["by_id"]["1"]["ai_insight"] == "تم بنجاح"

    def test_bare_json_array(self):
        """JSON مباشر بدون ``` ```."""
        ai_text = '[{"task_id": "1", "original_name": "ندوة حقوقية", "ai_insight": "ممتاز"}]'
        result = _extract_task_insights(ai_text)

        assert "1" in result["by_id"]
        assert "ندوة حقوقية" in result["by_name"]

    def test_no_json_returns_empty(self):
        """نص بدون JSON يُرجع قواميس فارغة."""
        ai_text = "هذا نص عادي بدون أي JSON."
        result = _extract_task_insights(ai_text)

        assert result["by_id"] == {}
        assert result["by_name"] == {}
        assert result["by_id_arabic"] == {}
        assert result["by_norm"] == {}

    def test_arabic_ordinal_mapping(self):
        """التعرف على المعرّفات العربية (الأول، الثاني...)."""
        ai_text = '''```json
        [{"task_id": "الأول", "original_name": "مهمة", "ai_insight": "جيد"}]
        ```'''
        result = _extract_task_insights(ai_text)

        assert "1" in result["by_id_arabic"]

    def test_name_lookup(self):
        """البحث بالاسم الكامل."""
        ai_text = '''[{"task_id": "1", "original_name": "تنظيم معرض فني", "ai_insight": "ناجح"}]'''
        result = _extract_task_insights(ai_text)

        assert "تنظيم معرض فني" in result["by_name"]

    def test_truncated_json_repair(self):
        """إصلاح JSON مقطوع."""
        ai_text = '[{"task_id": "1", "original_name": "ندوة", "ai_insight": "تم"}, {"task_id": "2", "original_name": "ورشة", "ai_in'
        result = _extract_task_insights(ai_text)

        # يجب أن يُسترجع المهمة الأولى على الأقل
        assert len(result["by_id"]) >= 1

    def test_dict_shape_invariant(self):
        """التحقق من شكل القاموس المُرجَع دائماً."""
        for text in ["", "no json", '[{"task_id":"1","original_name":"x","ai_insight":"y"}]']:
            result = _extract_task_insights(text)
            assert set(result.keys()) == {"by_id", "by_id_arabic", "by_name", "by_norm"}
