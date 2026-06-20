import React from 'react';

export default function SuccessScreen({ submissionId, formData, onReset }) {
  const officeName = formData.office_name === 'غير ذلك' 
    ? formData.custom_office_name 
    : formData.office_name;

  return (
    <div className="success-screen">
      <div className="success-badge">
        <i className="fa-solid fa-circle-check"></i>
      </div>
      
      <h2>تم تقديم التقرير بنجاح!</h2>
      <p>نشكر جهودكم الكريمة. تم استلام تقريركم الشهري وحفظه بنجاح في منظومة المتابعة الدورية للاتحاد العام لطلبة سوريا.</p>

      <div className="success-info-table">
        <div className="success-info-row">
          <span className="success-info-label">رقم التقرير (ID):</span>
          <span className="success-info-value" style={{ color: 'var(--color-gold)' }}>#{submissionId}</span>
        </div>
        <div className="success-info-row">
          <span className="success-info-label">المكتب / القسم:</span>
          <span className="success-info-value">{officeName}</span>
        </div>
        <div className="success-info-row">
          <span className="success-info-label">مقدم التقرير:</span>
          <span className="success-info-value">{formData.submitter_name}</span>
        </div>
        <div className="success-info-row">
          <span className="success-info-label">الفترة المستهدفة:</span>
          <span className="success-info-value">شهر {formData.month} / {formData.year}</span>
        </div>
        <div className="success-info-row">
          <span className="success-info-label">عدد المهام المرفقة:</span>
          <span className="success-info-value">{formData.tasks.length} مهام</span>
        </div>
        <div className="success-info-row">
          <span className="success-info-label">ملف الخطة المرفق:</span>
          <span className="success-info-value">
            {formData.has_plan && formData.plan_file ? 'تم الرفع (PDF)' : 'لم يتم إرفاق خطة'}
          </span>
        </div>
      </div>

      <div style={{ marginTop: '1.5rem' }}>
        <button 
          type="button" 
          onClick={onReset} 
          className="btn btn-primary"
          style={{ padding: '0.85rem 2.5rem' }}
        >
          <i className="fa-solid fa-rotate-right"></i>
          تقديم تقرير آخر
        </button>
      </div>
    </div>
  );
}
