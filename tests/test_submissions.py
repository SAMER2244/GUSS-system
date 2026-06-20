"""
test_submissions.py — اختبارات وحدوية لمسارات استقبال التقارير (submissions)
========================================================================
تتحقق من صحة استقبال البيانات، التحقق من المكاتب، رفع الملفات، والتعامل مع الأخطاء.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from io import BytesIO

from web_server import app

@pytest.fixture
def client():
    """تهيئة عميل اختبار FastAPI."""
    return TestClient(app)


# ─── 1. اختبار قائمة المكاتب ────────────────────────────────────────────────
@patch("routes.submissions.get_supabase_client")
def test_offices_list_success(mock_get_client, client):
    """التحقق من جلب قائمة المكاتب بنجاح."""
    mock_db = MagicMock()
    mock_get_client.return_value = mock_db
    
    # محاكاة الاستجابة من Supabase
    mock_execute_result = MagicMock()
    mock_execute_result.data = [
        {"id": 1, "name": "مكتب المتابعة و التقييم"},
        {"id": 2, "name": "المكتب الاعلامي"}
    ]
    mock_db.table.return_value.select.return_value.order.return_value.execute.return_value = mock_execute_result

    response = client.get("/api/offices-list")
    assert response.status_code == 200
    data = response.json()
    assert "offices" in data
    assert len(data["offices"]) == 2
    assert data["offices"][0]["name"] == "مكتب المتابعة و التقييم"
    mock_db.table.assert_called_with("offices")


@patch("routes.submissions.get_supabase_client")
def test_offices_list_db_error(mock_get_client, client):
    """التحقق من التعامل مع خطأ الاتصال بقاعدة البيانات عند جلب المكاتب."""
    mock_get_client.side_effect = RuntimeError("Connection failed")

    response = client.get("/api/offices-list")
    assert response.status_code == 503
    assert "قاعدة البيانات غير متاحة" in response.json()["detail"]


# ─── 2. اختبار رفع ملفات الخطط ──────────────────────────────────────────────
@patch("routes.submissions.get_supabase_client")
def test_upload_plan_success(mock_get_client, client):
    """التحقق من نجاح رفع ملف PDF صالح وحجم مناسب."""
    mock_db = MagicMock()
    mock_get_client.return_value = mock_db
    
    # محاكاة رفع الملف
    mock_storage = MagicMock()
    mock_db.storage.from_.return_value = mock_storage

    pdf_content = b"%PDF-1.4 dummy pdf content"
    files = {"file": ("plan.pdf", BytesIO(pdf_content), "application/pdf")}

    response = client.post("/api/upload-plan", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "file_path" in data
    assert ".pdf" in data["file_path"]
    
    mock_db.storage.from_.assert_called_with("monthly-plans")
    mock_storage.upload.assert_called_once()


def test_upload_plan_invalid_type(client):
    """التحقق من رفض رفع ملف غير PDF (مثل TXT)."""
    files = {"file": ("test.txt", BytesIO(b"dummy text"), "text/plain")}

    response = client.post("/api/upload-plan", files=files)
    assert response.status_code == 400
    assert "يُسمح فقط بملفات PDF" in response.json()["detail"]


def test_upload_plan_too_large(client):
    """التحقق من رفض رفع ملف يتجاوز الحجم الأقصى (10MB)."""
    # 11 MB of dummy content
    large_pdf = b"%PDF-1.4 " + b"x" * (11 * 1024 * 1024)
    files = {"file": ("large.pdf", BytesIO(large_pdf), "application/pdf")}

    response = client.post("/api/upload-plan", files=files)
    assert response.status_code == 413
    assert "يتجاوز الحد الأقصى" in response.json()["detail"]


# ─── 3. اختبار تقديم تقرير شهري ─────────────────────────────────────────────
@patch("routes.submissions.get_supabase_client")
def test_submit_report_success(mock_get_client, client):
    """التحقق من نجاح إرسال تقرير شهري جديد وحفظ المهام المرتبطة به."""
    mock_db = MagicMock()
    mock_get_client.return_value = mock_db

    # 1. محاكاة وجود المكتب
    mock_office_res = MagicMock()
    mock_office_res.data = [{"id": 5}]
    
    # 2. محاكاة حفظ التقرير وإرجاع الـ ID
    mock_sub_res = MagicMock()
    mock_sub_res.data = [{"id": 42}]

    # إعداد تسلسل الإرجاع لعمليات execute
    # الأولى: eq().execute() للمكتب
    # الثانية: insert().execute() للتقرير
    # الثالثة: insert().execute() للمهام
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_office_res
    
    # لتسهيل محاكاة العمليات المتعددة على الجداول المختلفة:
    def mock_table_routing(table_name):
        mock_tbl = MagicMock()
        if table_name == "offices":
            mock_tbl.select.return_value.eq.return_value.execute.return_value = mock_office_res
        elif table_name == "submissions":
            mock_tbl.insert.return_value.execute.return_value = mock_sub_res
        elif table_name == "tasks":
            mock_tbl.insert.return_value.execute.return_value = MagicMock()
        return mock_tbl

    mock_db.table.side_effect = mock_table_routing

    payload = {
        "office_name": "المكتب الاعلامي",
        "submitter_name": "أحمد صالح",
        "submitter_phone": "0999888777",
        "month": 6,
        "year": 2026,
        "has_plan": True,
        "plan_file_path": "20260620_123456_abcdef.pdf",
        "tasks": [
            {
                "manager_name": "ليلى حسن",
                "manager_phone": "0991111111",
                "task_name": "تنظيم ورشة عمل قانونية",
                "task_description": "ورشة تدريبية حول حقوق الطالب الجامعي",
                "task_type": "ضمن الخطة الشهرية",
                "execution_mechanism": "حضوري في قاعة المؤتمرات",
                "task_status": "مكتملة",
                "issues": ""
            }
        ],
        "general_challenges": "شُحّ الموارد المالية",
        "additional_notes": "نرجو الدعم المالي للمكتب"
    }

    response = client.post("/api/submit-report", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["submission_id"] == 42
    assert "تم تقديم التقرير بنجاح" in data["message"]


@patch("routes.submissions.get_supabase_client")
def test_submit_report_unknown_office(mock_get_client, client):
    """التحقق من رفض الطلب إذا كان اسم المكتب غير معروف/مسجل."""
    mock_db = MagicMock()
    mock_get_client.return_value = mock_db

    # محاكاة عدم وجود المكتب (قائمة فارغة)
    mock_office_res = MagicMock()
    mock_office_res.data = []
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_office_res

    payload = {
        "office_name": "مكتب وهمي غير موجود",
        "submitter_name": "أحمد صالح",
        "month": 6,
        "year": 2026,
        "has_plan": False,
        "tasks": [
            {
                "manager_name": "سامر صالح",
                "task_name": "مهمة 1",
                "task_type": "ضمن الخطة الشهرية",
                "task_status": "مكتملة"
            }
        ]
    }

    response = client.post("/api/submit-report", json=payload)
    assert response.status_code == 404
    assert "غير مسجل في النظام" in response.json()["detail"]


@patch("routes.submissions.get_supabase_client")
def test_submit_report_duplicate(mock_get_client, client):
    """التحقق من رفض التقرير المكرر لنفس المكتب والشهر والسنة (HTTP 409)."""
    mock_db = MagicMock()
    mock_get_client.return_value = mock_db

    # محاكاة وجود المكتب
    mock_office_res = MagicMock()
    mock_office_res.data = [{"id": 5}]
    
    # محاكاة حدوث استثناء فريد/تكرار عند الإدراج في قاعدة البيانات
    mock_tbl_offices = MagicMock()
    mock_tbl_offices.select.return_value.eq.return_value.execute.return_value = mock_office_res
    
    mock_tbl_submissions = MagicMock()
    mock_tbl_submissions.insert.side_effect = Exception("23505: duplicate key value violates unique constraint office_month_year")

    def mock_table_routing(table_name):
        if table_name == "offices":
            return mock_tbl_offices
        if table_name == "submissions":
            return mock_tbl_submissions
        return MagicMock()

    mock_db.table.side_effect = mock_table_routing

    payload = {
        "office_name": "المكتب الاعلامي",
        "submitter_name": "أحمد صالح",
        "month": 6,
        "year": 2026,
        "has_plan": False,
        "tasks": [
            {
                "manager_name": "سامر صالح",
                "task_name": "مهمة 1",
                "task_type": "ضمن الخطة الشهرية",
                "task_status": "مكتملة"
            }
        ]
    }

    response = client.post("/api/submit-report", json=payload)
    assert response.status_code == 409
    assert "يوجد تقرير مسجل مسبقاً" in response.json()["detail"]
