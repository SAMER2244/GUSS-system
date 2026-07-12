import pytest
from unittest.mock import patch, MagicMock

import migrate_legacy_plan_files

class TestLegacyPlanMigration:

    def test_extract_drive_id_valid_and_invalid(self):
        """يميز صح بين رابط Drive قديم ومسار Supabase Storage حالي."""
        from drive_uploader import _extract_drive_id
        
        # رابط قديم صحيح (شكل 1)
        old_url_1 = "https://drive.google.com/open?id=1A2b3C4d5E6f7G8h9I0j_K-LmNoPqRsTu"
        assert _extract_drive_id(old_url_1) == "1A2b3C4d5E6f7G8h9I0j_K-LmNoPqRsTu"
        
        # رابط قديم صحيح (شكل 2)
        old_url_2 = "https://drive.google.com/file/d/1A2b3C4d5E6f7G8h9I0j_K-LmNoPqRsTu/view"
        assert _extract_drive_id(old_url_2) == "1A2b3C4d5E6f7G8h9I0j_K-LmNoPqRsTu"
        
        # مسار Supabase جديد
        new_path = "20260712_123456_abcdef.pdf"
        assert _extract_drive_id(new_path) is None

    @patch("migrate_legacy_plan_files.get_supabase_client")
    @patch("migrate_legacy_plan_files._build_oauth_service")
    @patch("migrate_legacy_plan_files.check_drive_access")
    @patch("migrate_legacy_plan_files.download_drive_file")
    @patch("migrate_legacy_plan_files.upload_to_supabase")
    def test_successful_commit_updates_db(self, mock_upload, mock_download, mock_check, mock_service, mock_db):
        """ينجح تحديث plan_file_path بعد رفع ناجح."""
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance
        
        # Mocking Select Query
        mock_select = mock_db_instance.table.return_value.select.return_value.ilike.return_value.execute
        mock_select.return_value.data = [
            {"id": 1, "office_id": 10, "plan_file_path": "https://drive.google.com/open?id=test_id_12345"}
        ]
        
        mock_check.return_value = (True, "متاح")
        mock_download.return_value = b"pdf_content"
        mock_upload.return_value = "20260712_newfile.pdf"
        
        with patch("sys.argv", ["migrate_legacy_plan_files.py", "--commit"]):
            migrate_legacy_plan_files.main()
            
        # التأكد من أنه قام بالرفع والتحديث
        mock_upload.assert_called_once()
        mock_db_instance.table.return_value.update.assert_called_once_with({"plan_file_path": "20260712_newfile.pdf"})
        mock_db_instance.table.return_value.update.return_value.eq.assert_called_once_with("id", 1)
        mock_db_instance.table.return_value.update.return_value.eq.return_value.execute.assert_called_once()

    @patch("migrate_legacy_plan_files.get_supabase_client")
    @patch("migrate_legacy_plan_files._build_oauth_service")
    @patch("migrate_legacy_plan_files.check_drive_access")
    @patch("migrate_legacy_plan_files.download_drive_file")
    @patch("migrate_legacy_plan_files.upload_to_supabase")
    def test_failure_does_not_stop_execution(self, mock_upload, mock_download, mock_check, mock_service, mock_db):
        """يسجل الفشل بشكل صحيح دون إيقاف بقية الصفوف عند فشل رابط واحد."""
        mock_db_instance = MagicMock()
        mock_db.return_value = mock_db_instance
        
        # صفين: الأول يفشل، الثاني ينجح
        mock_select = mock_db_instance.table.return_value.select.return_value.ilike.return_value.execute
        mock_select.return_value.data = [
            {"id": 1, "office_id": 10, "plan_file_path": "https://drive.google.com/open?id=fail_id_12345"},
            {"id": 2, "office_id": 11, "plan_file_path": "https://drive.google.com/open?id=success_id_6789"}
        ]
        
        mock_check.return_value = (True, "متاح")
        
        # تحميل الملف الأول سيفشل، والثاني سينجح
        def download_side_effect(service, file_id):
            if file_id == "fail_id_12345":
                raise Exception("فشل التنزيل")
            return b"pdf_content"
        mock_download.side_effect = download_side_effect
        
        mock_upload.return_value = "20260712_success.pdf"
        
        with patch("sys.argv", ["migrate_legacy_plan_files.py", "--commit"]):
            migrate_legacy_plan_files.main()
            
        # تم استدعاء الرفع للصف الثاني فقط
        mock_upload.assert_called_once()
        # تم تحديث قاعدة البيانات للصف الثاني فقط
        mock_db_instance.table.return_value.update.assert_called_once_with({"plan_file_path": "20260712_success.pdf"})
        mock_db_instance.table.return_value.update.return_value.eq.assert_called_once_with("id", 2)
