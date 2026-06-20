import React, { useState } from 'react';

export default function ClosingStep({ formData, updateFormData, onSubmit, onPrev, isSubmitting }) {
  const [errors, setErrors] = useState({});

  const handleChange = (e) => {
    const { name, value } = e.target;
    updateFormData({ [name]: value });
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: null }));
    }
  };

  const validate = () => {
    const newErrors = {};
    if (!formData.general_challenges.trim()) {
      newErrors.general_challenges = 'هذا الحقل إلزامي.';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (validate()) {
      onSubmit();
    }
  };

  return (
    <form onSubmit={handleSubmit} className="animate-slide-up">
      {/* Description */}
      <div className="form-help-text" style={{ marginBottom: '2rem' }}>
        <p style={{ fontWeight: 'bold', marginBottom: '0.5rem' }}>
          البيانات الختامية للتقرير
        </p>
        <p style={{ fontSize: '0.85rem', lineHeight: '1.5' }}>
          يرجى تدوين أي تحديات أو عقبات واجهت سير العمل في المكتب بشكل عام خلال هذا الشهر، والتي لم تقتصر على مهمة محددة. يشمل ذلك (على سبيل المثال لا الحصر):
        </p>
        <ul style={{ listStyle: 'none', paddingRight: '0.8rem', fontSize: '0.82rem', marginTop: '0.5rem' }}>
          <li><span className="form-help-bullet">•</span> <strong>التنسيق الإداري:</strong> أي تأخير أو عدم استجابة من مكاتب أخرى أثر على أداء المكتب.</li>
          <li><span className="form-help-bullet">•</span> <strong>الموارد البشرية:</strong> نقص في عدد المتطوعين، تراجع في الأداء، أو ضغوطات غير متوقعة.</li>
          <li><span className="form-help-bullet">•</span> <strong>الاحتياجات اللوجستية:</strong> نقص في المعدات أو الأدوات اللازمة للتنفيذ.</li>
          <li><span className="form-help-bullet">•</span> <strong>المقترحات:</strong> أي ملاحظات ترونها ضرورية لتطوير آليات العمل.</li>
        </ul>
        <p style={{ marginTop: '0.5rem', fontStyle: 'italic', fontSize: '0.82rem' }}>
          ملاحظة: تساهم هذه البيانات في تمكين مكتب المتابعة والتقييم من تقديم تحليل موضوعي للإدارة حول بيئة العمل المحيطة بالمكاتب.
        </p>
      </div>

      {/* 1. General Challenges */}
      <div className="form-group">
        <label className="form-label">
          التحديات والملاحظات الإدارية العامة
          <span className="required-star">*</span>
        </label>
        <textarea
          name="general_challenges"
          value={formData.general_challenges}
          onChange={handleChange}
          placeholder="اكتب التحديات والملاحظات الإدارية العامة بالتفصيل..."
          className="form-control"
          rows="6"
          style={{ resize: 'vertical' }}
        />
        {errors.general_challenges && <span className="alert alert-danger" style={{ padding: '0.4rem 0.8rem', margin: '0.2rem 0 0' }}>{errors.general_challenges}</span>}
      </div>

      {/* 2. Additional Notes */}
      <div className="form-group">
        <label className="form-label">
          ملاحظات إضافية (اختياري)
        </label>
        <textarea
          name="additional_notes"
          value={formData.additional_notes}
          onChange={handleChange}
          placeholder="أي ملاحظات إضافية ترغب في تدوينها..."
          className="form-control"
          rows="4"
          style={{ resize: 'vertical' }}
        />
      </div>

      {/* Button navigation */}
      <div className="btn-group">
        <button 
          type="button" 
          onClick={onPrev} 
          className="btn btn-secondary"
          disabled={isSubmitting}
        >
          <i className="fa-solid fa-arrow-right btn-icon"></i>
          السابق
        </button>
        
        <button 
          type="submit" 
          className="btn btn-primary"
          disabled={isSubmitting}
        >
          {isSubmitting ? (
            <>
              <i className="fa-solid fa-circle-notch fa-spin btn-icon"></i>
              جاري الإرسال...
            </>
          ) : (
            <>
              إرسال التقرير النهائي
              <i className="fa-solid fa-paper-plane btn-icon"></i>
            </>
          )}
        </button>
      </div>
    </form>
  );
}
