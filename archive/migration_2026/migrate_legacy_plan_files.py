import argparse
import io
import sys
import uuid
from datetime import datetime, timezone
import requests
from pathlib import Path

from googleapiclient.http import MediaIoBaseDownload

# الاستيراد من المشروع الحالي
from database import get_supabase_client
from drive_uploader import _build_oauth_service, _extract_drive_id

def check_drive_access(service, file_id: str) -> tuple[bool, str]:
    """يتحقق من قابلية الوصول للملف على Google Drive باستخدام الـ API."""
    try:
        meta = service.files().get(fileId=file_id, fields="id, name, size", supportsAllDrives=True).execute()
        size_kb = int(meta.get("size", 0)) / 1024
        return True, f"متاح (الاسم: {meta.get('name')}, الحجم: {size_kb:.1f} KB)"
    except Exception as e:
        return False, str(e)

def download_drive_file(service, file_id: str) -> bytes:
    """يحمل الملف من Google Drive إلى الذاكرة."""
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    return fh.getvalue()

def upload_to_supabase(db, contents: bytes) -> str:
    """يرفع الملف إلى Supabase Storage ويُعيد المسار الجديد."""
    unique_id = uuid.uuid4().hex[:12]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    file_path = f"{timestamp}_{unique_id}.pdf"
    
    db.storage.from_("monthly-plans").upload(
        path=file_path,
        file=contents,
        file_options={"content-type": "application/pdf"}
    )
    return file_path

def main() -> None:
    parser = argparse.ArgumentParser(description="ترحيل خطط الإكسل المرفوعة على Google Drive إلى Supabase Storage.")
    parser.add_argument("--commit", action="store_true", help="تنفيذ الرفع الفعلي (بدونه: dry-run فقط)")
    args = parser.parse_args()

    db = get_supabase_client()
    
    print("\n🔍 البحث عن روابط Google Drive في جدول submissions...")
    # استخراج جميع الصفوف التي تحتوي على رابط Drive
    result = db.table("submissions").select("id, office_id, plan_file_path").ilike("plan_file_path", "https://drive.google.com/%").execute()
    
    submissions = result.data
    if not submissions:
        print("✅ لا توجد ملفات خطط تحتاج ترحيل (جميع الروابط داخلية).")
        return

    print(f"📁 تم العثور على {len(submissions)} submission تحتوي على رابط Google Drive.\n")
    
    print("☁️  جاري بناء خدمة Google Drive (OAuth2)...")
    try:
        service = _build_oauth_service()
    except Exception as e:
        print(f"❌ فشل الاتصال بـ Google Drive API: {e}")
        sys.exit(1)

    successful = 0
    failed = []

    print(f"{'═'*90}")
    if not args.commit:
        print("🔍 وضع DRY-RUN (لن يتم النقل الفعلي)")
    else:
        print("🚀 وضع COMMIT (يتم النقل الفعلي)")
    print(f"{'═'*90}\n")

    for sub in submissions:
        sub_id = sub["id"]
        off_id = sub["office_id"]
        old_url = sub["plan_file_path"]
        
        file_id = _extract_drive_id(old_url)
        if not file_id:
            print(f"⚠️  [ID:{sub_id}] تعذر استخراج file_id من الرابط: {old_url}")
            failed.append({"id": sub_id, "error": "Invalid Drive URL"})
            continue
        
        # 1) فحص الوصول (Dry-run أو تمهيد للـ Commit)
        is_accessible, info_or_error = check_drive_access(service, file_id)
        
        if not is_accessible:
            print(f"❌ [ID:{sub_id}] الرابط غير قابل للوصول: {info_or_error}")
            failed.append({"id": sub_id, "error": f"Drive Access Error: {info_or_error}"})
            continue
            
        if not args.commit:
            print(f"✅ [ID:{sub_id}] Office:{off_id} | {info_or_error} | الرابط: {old_url}")
            continue

        # 2) وضع Commit: تحميل ورفع
        try:
            print(f"⏳ [ID:{sub_id}] جاري التحميل من Drive...")
            contents = download_drive_file(service, file_id)
            
            print(f"⏳ [ID:{sub_id}] جاري الرفع إلى Supabase...")
            new_path = upload_to_supabase(db, contents)
            
            print(f"⏳ [ID:{sub_id}] جاري تحديث قاعدة البيانات...")
            db.table("submissions").update({"plan_file_path": new_path}).eq("id", sub_id).execute()
            
            print(f"✅ [ID:{sub_id}] اكتمل النقل بنجاح! المسار الجديد: {new_path}")
            successful += 1
            
        except Exception as e:
            print(f"❌ [ID:{sub_id}] فشل أثناء النقل: {e}")
            failed.append({"id": sub_id, "error": str(e)})

    # ملخص النهاية
    print(f"\n{'═'*90}")
    print("📊 ملخص العملية:")
    if args.commit:
        print(f"   نجاح: {successful} / {len(submissions)}")
        print(f"   فشل : {len(failed)}")
        if failed:
            print("\n🚨 تفاصيل الفشل:")
            for f in failed:
                print(f"   - [ID:{f['id']}] {f['error']}")
    else:
        print("   تم الانتهاء من الفحص (Dry-Run). استخدم --commit للتنفيذ.")
    print(f"{'═'*90}\n")

if __name__ == "__main__":
    main()
