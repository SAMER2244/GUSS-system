import React, { useState, useEffect, useRef } from 'react';

const STATIC_OFFICES = [
  'مكتب المتابعة و التقييم',
  'المكتب الاعلامي',
  'المكتب المالي',
  'مكتب العلاقات',
  'مكتب اسطنبول',
  'المكتب التقني',
  'المكتب الاكاديمي',
  'مكتب وحدة البحث العلمي',
  'المكتب القانوني',
  'مكتب الموارد البشرية',
  'مكتب الربط الداخلي',
  'مكتب شؤون الطلبة'
];

const MONTHS = [
  { val: 1, name: 'كانون الثاني (1)' },
  { val: 2, name: 'شباط (2)' },
  { val: 3, name: 'آذار (3)' },
  { val: 4, name: 'نيسان (4)' },
  { val: 5, name: 'أيار (5)' },
  { val: 6, name: 'حزيران (6)' },
  { val: 7, name: 'تموز (7)' },
  { val: 8, name: 'آب (8)' },
  { val: 9, name: 'أيلول (9)' },
  { val: 10, name: 'تشرين الأول (10)' },
  { val: 11, name: 'تشرين الثاني (11)' },
  { val: 12, name: 'كانون الأول (12)' }
];

export default function BasicInfoStep({ formData, updateFormData, onNext, onPrev, isRestoredPlan }) {
  const [offices, setOffices] = useState(STATIC_OFFICES);
  const [loadingOffices, setLoadingOffices] = useState(true);
  const [errors, setErrors] = useState({});
  const fileInputRef = useRef(null);

  useEffect(() => {
    // Fetch offices from API
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '';
    fetch(`${apiBaseUrl}/api/offices-list`)
      .then(res => {
        if (!res.ok) throw new Error('Failed to load offices');
        return res.json();
      })
      .then(data => {
        if (data && data.offices) {
          setOffices(data.offices.map(o => o.name));
        } else {
          setOffices(STATIC_OFFICES);
        }
      })
      .catch(err => {
        console.error('Error fetching offices:', err);
        setOffices(STATIC_OFFICES); // Fallback to hardcoded list
      })
      .finally(() => {
        setLoadingOffices(false);
      });
  }, []);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    const val = type === 'checkbox' ? checked : value;
    updateFormData({ [name]: val });
    
    // Clear error for this field
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: null }));
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (file.type !== 'application/pdf') {
        setErrors(prev => ({ ...prev, plan_file: 'يُسمح فقط بملفات PDF حصراً.' }));
        return;
      }
      if (file.size > 10 * 1024 * 1024) {
        setErrors(prev => ({ ...prev, plan_file: 'حجم الملف يتجاوز الحد الأقصى المسموح (10 ميغابايت).' }));
        return;
      }
      updateFormData({ plan_file: file });
      setErrors(prev => ({ ...prev, plan_file: null }));
    }
  };

  const handleRemoveFile = (e) => {
    e.stopPropagation();
    updateFormData({ plan_file: null });
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const validate = () => {
    const newErrors = {};
    if (!formData.office_name) {
      newErrors.office_name = 'هذا الحقل إلزامي.';
    } else if (formData.office_name === 'غير ذلك' && !formData.custom_office_name.trim()) {
      newErrors.custom_office_name = 'يرجى كتابة اسم المكتب.';
    }
    
    if (!formData.submitter_name.trim()) {
      newErrors.submitter_name = 'هذا الحقل إلزامي.';
    }
    
    if (!formData.submitter_phone.trim()) {
      newErrors.submitter_phone = 'هذا الحقل إلزامي.';
    }
    
    if (!formData.month) {
      newErrors.month = 'هذا الحقل إلزامي.';
    }

    if (formData.has_plan && !formData.plan_file) {
      newErrors.plan_file = 'يرجى رفع ملف خطة الشهر بصيغة PDF.';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleNext = () => {
    if (validate()) {
      onNext();
    }
  };

  return (
    <div className="animate-slide-up">
      {/* 1. Office dropdown */}
      <div className="form-group">
        <label className="form-label">
          اسم المكتب / القسم
          <span className="required-star">*</span>
        </label>
        <select
          name="office_name"
          value={formData.office_name}
          onChange={handleChange}
          className="form-control"
        >
          <option value="">-- اختر المكتب أو القسم --</option>
          {offices.map((office, idx) => (
            <option key={idx} value={office}>{office}</option>
          ))}
          <option value="غير ذلك">غير ذلك</option>
        </select>
        {errors.office_name && <span className="alert alert-danger" style={{ padding: '0.4rem 0.8rem', margin: '0.2rem 0 0' }}>{errors.office_name}</span>}
      </div>

      {/* 1.1 Custom Office name (if "غير ذلك" is selected) */}
      {formData.office_name === 'غير ذلك' && (
        <div className="form-group animate-slide-up">
          <label className="form-label">
            اسم المكتب الجديد / القسم غير المدرج
            <span className="required-star">*</span>
          </label>
          <input
            type="text"
            name="custom_office_name"
            value={formData.custom_office_name}
            onChange={handleChange}
            placeholder="أدخل اسم المكتب هنا..."
            className="form-control"
          />
          {errors.custom_office_name && <span className="alert alert-danger" style={{ padding: '0.4rem 0.8rem', margin: '0.2rem 0 0' }}>{errors.custom_office_name}</span>}
        </div>
      )}

      {/* 2. Submitter Name & Phone row */}
      <div className="form-row">
        <div className="form-group">
          <label className="form-label">
            المسؤول عن تعبئة النموذج
            <span className="required-star">*</span>
          </label>
          <input
            type="text"
            name="submitter_name"
            value={formData.submitter_name}
            onChange={handleChange}
            placeholder="الاسم الثلاثي واللقب"
            className="form-control"
          />
          {errors.submitter_name && <span className="alert alert-danger" style={{ padding: '0.4rem 0.8rem', margin: '0.2rem 0 0' }}>{errors.submitter_name}</span>}
        </div>

        <div className="form-group">
          <label className="form-label">
            رقم الهاتف
            <span className="required-star">*</span>
          </label>
          <input
            type="tel"
            name="submitter_phone"
            value={formData.submitter_phone}
            onChange={handleChange}
            placeholder="رقم الهاتف للتواصل (مثال: 09xxxxxxxx)"
            className="form-control"
            dir="ltr"
            style={{ textAlign: 'right' }}
          />
          {errors.submitter_phone && <span className="alert alert-danger" style={{ padding: '0.4rem 0.8rem', margin: '0.2rem 0 0' }}>{errors.submitter_phone}</span>}
        </div>
      </div>

      {/* 3. Month & Year row */}
      <div className="form-row">
        <div className="form-group">
          <label className="form-label">
            هذا التقرير خاص بالشهر
            <span className="required-star">*</span>
          </label>
          <select
            name="month"
            value={formData.month}
            onChange={handleChange}
            className="form-control"
          >
            {MONTHS.map(m => (
              <option key={m.val} value={m.val}>{m.name}</option>
            ))}
          </select>
          {errors.month && <span className="alert alert-danger" style={{ padding: '0.4rem 0.8rem', margin: '0.2rem 0 0' }}>{errors.month}</span>}
        </div>

        <div className="form-group">
          <label className="form-label">
            العام
            <span className="required-star">*</span>
          </label>
          <select
            name="year"
            value={formData.year}
            onChange={handleChange}
            className="form-control"
          >
            <option value="2026">2026</option>
            <option value="2025">2025</option>
            <option value="2027">2027</option>
          </select>
        </div>
      </div>

      {/* 4. Has Plan toggle & Upload Plan Section */}
      <div className="form-group" style={{ marginTop: '0.5rem' }}>
        <label className="toggle-wrapper">
          <input
            type="checkbox"
            name="has_plan"
            checked={formData.has_plan}
            onChange={handleChange}
            className="toggle-input"
          />
          <div className="toggle-custom"></div>
          <span style={{ fontWeight: '700', fontSize: '0.95rem' }}>
            هل يوجد خطة شهرية معتمدة ومكتوبة لهذا الشهر؟
          </span>
        </label>
      </div>

      {formData.has_plan && (
        <div className="form-group animate-slide-up" style={{ marginTop: '0.5rem' }}>
          <label className="form-label">
            رفع ملف الخطة الشهرية (PDF فقط)
            <span className="required-star">*</span>
          </label>
          
          <div className="form-help-text" style={{ marginBottom: '1rem' }}>
            يرجى رفع ملف بصيغة PDF حصراً يحتوي على خطة الشهر الخاصة بالمكتب.
            يمكنك الاطلاع على: {' '}
            <a 
              href="https://drive.google.com/drive/u/2/folders/1GLJuIK9BgHqmIOAn9IiDgxvUqh4GTenm" 
              target="_blank" 
              rel="noopener noreferrer" 
              className="guide-link"
            >
              مثال عن الخطة شهرية
            </a>
          </div>

          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept="application/pdf"
            style={{ display: 'none' }}
          />

          {isRestoredPlan && !formData.plan_file && (
            <div className="alert alert-danger" style={{ padding: '0.75rem 1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <i className="fa-solid fa-circle-exclamation alert-icon" style={{ fontSize: '1.2rem', marginTop: 0 }}></i>
              <div style={{ fontWeight: 700 }}>يرجى إعادة رفع ملف الخطة الشهرية</div>
            </div>
          )}

          {!formData.plan_file ? (
            <div 
              className="file-upload-card" 
              onClick={() => fileInputRef.current && fileInputRef.current.click()}
            >
              <i className="fa-solid fa-cloud-arrow-up file-upload-icon"></i>
              <span style={{ fontWeight: 700 }}>انقر هنا لاختيار ملف PDF أو إسقاطه</span>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>الحد الأقصى للحجم: 10 ميغابايت</span>
            </div>
          ) : (
            <div className="selected-file-info animate-scale-up">
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
                <i className="fa-solid fa-file-pdf" style={{ color: 'var(--success)', fontSize: '1.5rem' }}></i>
                <span className="file-name">{formData.plan_file.name}</span>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  ({(formData.plan_file.size / (1024 * 1024)).toFixed(2)} MB)
                </span>
              </div>
              <button 
                type="button" 
                onClick={handleRemoveFile} 
                className="btn-remove-file"
                title="إلغاء اختيار الملف"
              >
                <i className="fa-solid fa-circle-xmark"></i>
              </button>
            </div>
          )}

          {errors.plan_file && (
            <span className="alert alert-danger" style={{ padding: '0.4rem 0.8rem', margin: '0.5rem 0 0' }}>
              <i className="fa-solid fa-triangle-exclamation alert-icon"></i>
              {errors.plan_file}
            </span>
          )}
        </div>
      )}

      {/* Button navigation */}
      <div className="btn-group">
        <button type="button" onClick={onPrev} className="btn btn-secondary">
          <i className="fa-solid fa-arrow-right btn-icon"></i>
          السابق
        </button>
        <button type="button" onClick={handleNext} className="btn btn-primary">
          التالي
          <i className="fa-solid fa-arrow-left btn-icon"></i>
        </button>
      </div>
    </div>
  );
}
