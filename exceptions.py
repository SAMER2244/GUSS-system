"""
exceptions.py  —  استثناءات مخصصة لنظام GUSS
================================================
يوفر استثناءات متخصصة لكل طبقة من طبقات النظام
لتسهيل معالجة الأخطاء وتتبعها وتصنيفها.
"""

from __future__ import annotations


class GUSSError(Exception):
    """الاستثناء الأساسي لجميع أخطاء نظام GUSS."""

    def __init__(self, message: str, context: dict | None = None) -> None:
        self.context = context or {}
        super().__init__(message)


class ConfigurationError(GUSSError):
    """خطأ في إعدادات النظام أو الملفات المطلوبة."""
    pass


class SheetConnectionError(GUSSError):
    """خطأ في الاتصال بـ Google Sheets أو قراءة البيانات."""
    pass


class PDFExtractionError(GUSSError):
    """خطأ في تحميل أو استخراج نص PDF."""
    pass


class AIAnalysisError(GUSSError):
    """خطأ في تحليل الذكاء الاصطناعي."""

    def __init__(
        self,
        message: str,
        section: str = "",
        model: str = "",
        context: dict | None = None,
    ) -> None:
        self.section = section
        self.model = model
        super().__init__(message, context)


class ReportGenerationError(GUSSError):
    """خطأ في توليد التقرير."""
    pass


class DriveUploadError(GUSSError):
    """خطأ في رفع الملفات إلى Google Drive."""
    pass
