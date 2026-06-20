"""
conftest.py — إعدادات مشتركة لاختبارات pytest
"""
import sys
from pathlib import Path

# إضافة مسار المشروع لـ sys.path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# تهيئة إعدادات افتراضية للاختبارات لضمان عدم تأثرها بالملفات المحلية
import config as cfg
cfg.GUSS_ADMIN_USERNAME = "admin"
cfg.GUSS_ADMIN_PASSWORD = "guss2026"
