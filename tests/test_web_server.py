"""
test_web_server.py — اختبارات وحدوية لخادم الويب web_server.py
===========================================================
تختبر مسارات الـ API وحالات خادم FastAPI باستخدام TestClient ومحاكاة الدوال الخارجية.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from pathlib import Path
import os
import yaml

from web_server import app, pipeline_state, state_lock
import config as cfg


@pytest.fixture
def client():
    """تهيئة عميل اختبار FastAPI."""
    return TestClient(app)


@pytest.fixture
def auth_client(client):
    """تهيئة عميل اختبار FastAPI مسجل الدخول."""
    # تسجيل الدخول للحصول على الكوكي
    response = client.post("/api/login", json={
        "username": cfg.GUSS_ADMIN_USERNAME,
        "password": cfg.GUSS_ADMIN_PASSWORD
    })
    assert response.status_code == 200
    return client


def test_index_route(client):
    """يتحقق من أن مسار الصفحة الرئيسية يستجيب بنجاح."""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.text or "<!DOCTYPE html>" in response.text


def test_login_failed(client):
    """يتحقق من فشل تسجيل الدخول عند إدخال بيانات خاطئة."""
    response = client.post("/api/login", json={
        "username": "wrong_user",
        "password": "wrong_password"
    })
    assert response.status_code == 401


def test_login_success(client):
    """يتحقق من نجاح تسجيل الدخول بالبيانات الصحيحة."""
    response = client.post("/api/login", json={
        "username": cfg.GUSS_ADMIN_USERNAME,
        "password": cfg.GUSS_ADMIN_PASSWORD
    })
    assert response.status_code == 200
    assert "guss_session" in response.cookies


def test_logout(auth_client):
    """يتحقق من نجاح تسجيل الخروج وإزالة الكوكي."""
    response = auth_client.post("/api/logout")
    assert response.status_code == 200
    # الكوكي يجب أن يُحذف أو تنتهي صلاحيته
    assert "guss_session" not in auth_client.cookies or auth_client.cookies["guss_session"] == ""


def test_api_status_unauthorized(client):
    """يتحقق من رفض الوصول إلى حالة المعالجة دون تسجيل دخول."""
    response = client.get("/api/status")
    assert response.status_code == 401


def test_api_status_route(auth_client):
    """يتحقق من إرجاع حالة المعالجة بشكل صحيح للمستخدم المصرح له."""
    response = auth_client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "progress" in data
    assert "results" in data


def test_api_reset_route(auth_client):
    """يتحقق من إعادة تعيين الحالة بنجاح للمستخدم المصرح له."""
    with state_lock:
        pipeline_state["status"] = "completed"
        pipeline_state["progress"] = 100.0
        
    response = auth_client.post("/api/reset")
    assert response.status_code == 200
    assert response.json()["status"] == "reset"
    
    # التحقق من تصفير الحالة
    status_response = auth_client.get("/api/status")
    assert status_response.json()["status"] == "idle"
    assert status_response.json()["progress"] == 0.0


@patch("web_server.get_supabase_client")
def test_api_process_route_success(mock_get_supabase, auth_client):
    """يتحقق من بدء المعالجة بالخلفية بنجاح عند توفير submission_id صالح."""
    mock_db = MagicMock()
    mock_get_supabase.return_value = mock_db
    
    mock_res = MagicMock()
    mock_res.data = [{"id": 123}]
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_res

    # تصفير الحالة
    auth_client.post("/api/reset")

    payload = {
        "submission_id": 123
    }
    
    with patch("web_server._background_pipeline_runner") as mock_runner:
        response = auth_client.post("/api/process", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "started"
        mock_runner.assert_called_once_with(submission_id=123)


@patch("web_server.get_supabase_client")
def test_api_process_route_not_found(mock_get_supabase, auth_client):
    """يتحقق من إرجاع خطأ 404 عند تمرير submission_id غير موجود بقاعدة البيانات."""
    mock_db = MagicMock()
    mock_get_supabase.return_value = mock_db
    
    mock_res = MagicMock()
    mock_res.data = []
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_res

    payload = {
        "submission_id": 999
    }
    
    response = auth_client.post("/api/process", json=payload)
    assert response.status_code == 404
    assert "غير موجود" in response.json()["detail"]


def test_api_settings_get_and_post(auth_client):
    """يتحقق من جلب وتحديث الإعدادات بنجاح."""
    # جلب الإعدادات الحالية
    get_res = auth_client.get("/api/settings")
    assert get_res.status_code == 200
    settings = get_res.json()
    assert "gemini_api_key" in settings
    assert "spreadsheet_name" in settings
    
    # حفظ الإعدادات الأصلية
    orig_api_key = cfg.GEMINI_API_KEY
    orig_sheet_name = cfg.SPREADSHEET_NAME
    
    # تحديث الإعدادات
    new_spreadsheet = "جدول اختبار مؤقت"
    update_payload = {
        "spreadsheet_name": new_spreadsheet,
        "gemini_api_key": "AIzaSyTestKey1234"
    }
    
    # محاكاة حفظ الملف في بيئة الاختبار لتجنب تخريب إعدادات المستخدم الحقيقية
    settings_file = Path(cfg.BASE_DIR) / "settings.yaml"
    backup_content = None
    if settings_file.exists():
        with open(settings_file, "r", encoding="utf-8") as f:
            backup_content = f.read()
            
    try:
        post_res = auth_client.post("/api/settings", json=update_payload)
        assert post_res.status_code == 200
        assert post_res.json()["status"] == "success"
        
        # التأكد من انعكاس التغيير في الذاكرة
        assert cfg.SPREADSHEET_NAME == new_spreadsheet
        assert cfg.GEMINI_API_KEY == "AIzaSyTestKey1234"
        
        # التأكد من كتابتها في الملف
        with open(settings_file, "r", encoding="utf-8") as f:
            written_yaml = yaml.safe_load(f)
            assert written_yaml["sheets"]["spreadsheet_name"] == new_spreadsheet
            assert written_yaml["ai"]["api_key"] == "AIzaSyTestKey1234"
            
    finally:
        # استعادة الملف والذاكرة بعد الاختبار
        if backup_content is not None:
            with open(settings_file, "w", encoding="utf-8") as f:
                f.write(backup_content)
        elif settings_file.exists():
            settings_file.unlink()
        cfg.SPREADSHEET_NAME = orig_sheet_name
        cfg.GEMINI_API_KEY = orig_api_key
