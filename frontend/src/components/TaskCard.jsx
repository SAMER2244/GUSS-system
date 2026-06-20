import React from 'react';

export default function TaskCard({ task, index, onChange, onDelete, errors = {} }) {
  const handleChange = (e) => {
    const { name, value } = e.target;
    onChange(index, name, value);
  };

  return (
    <div className="task-card animate-slide-up">
      <div className="task-card-header">
        <h4 className="task-card-title">
          <i className="fa-solid fa-list-check"></i>
          المهمة / المشروع #{index + 1}
        </h4>
        {index > 0 && (
          <button 
            type="button" 
            onClick={() => onDelete(index)} 
            className="btn-delete-task"
            title="حذف هذه المهمة"
          >
            <i className="fa-solid fa-trash-can"></i>
            حذف المهمة
          </button>
        )}
      </div>

      {/* 1. Manager Name & Phone row */}
      <div className="form-row">
        <div className="form-group">
          <label className="form-label">
            اسم المسؤول عن المهمة أو المشروع
            <span className="required-star">*</span>
          </label>
          <input
            type="text"
            name="manager_name"
            value={task.manager_name}
            onChange={handleChange}
            placeholder="الاسم الكامل للمسؤول"
            className="form-control"
          />
          {errors.manager_name && <span className="alert alert-danger" style={{ padding: '0.4rem 0.8rem', margin: '0.2rem 0 0' }}>{errors.manager_name}</span>}
        </div>

        <div className="form-group">
          <label className="form-label">
            رقم هاتف المسؤول
            <span className="required-star">*</span>
          </label>
          <input
            type="tel"
            name="manager_phone"
            value={task.manager_phone}
            onChange={handleChange}
            placeholder="رقم الهاتف (مثال: 09xxxxxxxx)"
            className="form-control"
            dir="ltr"
            style={{ textAlign: 'right' }}
          />
          {errors.manager_phone && <span className="alert alert-danger" style={{ padding: '0.4rem 0.8rem', margin: '0.2rem 0 0' }}>{errors.manager_phone}</span>}
        </div>
      </div>

      {/* 2. Task Name & Task Type row */}
      <div className="form-row">
        <div className="form-group">
          <label className="form-label">
            اسم المهمة / المشروع
            <span className="required-star">*</span>
          </label>
          <input
            type="text"
            name="task_name"
            value={task.task_name}
            onChange={handleChange}
            placeholder="أدخل اسم المهمة أو المشروع"
            className="form-control"
          />
          <span className="form-help-text" style={{ background: 'transparent', padding: '0', border: 'none', fontSize: '0.8rem', marginTop: '0.1rem', color: 'var(--text-secondary)' }}>
            وصف قصير يوضح المهمة والهدف منها.
          </span>
          {errors.task_name && <span className="alert alert-danger" style={{ padding: '0.4rem 0.8rem', margin: '0.2rem 0 0' }}>{errors.task_name}</span>}
        </div>

        <div className="form-group">
          <label className="form-label">
            نوع المهمة
            <span className="required-star">*</span>
          </label>
          <select
            name="task_type"
            value={task.task_type}
            onChange={handleChange}
            className="form-control"
          >
            <option value="ضمن الخطة الشهرية">ضمن الخطة الشهرية</option>
            <option value="خارج الخطة الشهرية">خارج الخطة الشهرية</option>
          </select>
          {errors.task_type && <span className="alert alert-danger" style={{ padding: '0.4rem 0.8rem', margin: '0.2rem 0 0' }}>{errors.task_type}</span>}
        </div>
      </div>

      {/* 3. Execution Mechanism */}
      <div className="form-group">
        <label className="form-label">
          آلية التنفيذ
          <span className="required-star">*</span>
        </label>
        <textarea
          name="execution_mechanism"
          value={task.execution_mechanism}
          onChange={handleChange}
          placeholder="اكتب آلية التنفيذ بالتفصيل..."
          className="form-control"
          rows="5"
          style={{ resize: 'vertical' }}
        />
        <div className="form-help-text" style={{ fontSize: '0.8rem', lineHeight: '1.4' }}>
          <p style={{ fontWeight: 'bold', marginBottom: '0.25rem' }}>يرجى تقديم شرح موجز للخطوات العملية والوسائل التي تم اتباعها لإنجاز هذه المهمة. يفضل التركيز على النقاط التالية لضمان دقة التوثيق الإداري:</p>
          <div style={{ paddingRight: '0.5rem' }}>
            <div><span className="form-help-bullet">•</span> <strong>التنسيق الداخلي:</strong> كيف تم توزيع الأدوار بين أعضاء الفريق أو اللجان المختصة؟</div>
            <div><span className="form-help-bullet">•</span> <strong>الوسائل المستخدمة:</strong> هل تم الاعتماد على اجتماعات دورية (Google Meet مثلاً)، أم مراسلات مباشرة، أم أدوات تقنية محددة؟</div>
            <div><span className="form-help-bullet">•</span> <strong>التعاون البيني:</strong> هل تطلب التنفيذ التنسيق مع مكاتب أخرى؟</div>
            <div><span className="form-help-bullet">•</span> <strong>المراحل التنفيذية:</strong> ذكر المحطات الرئيسية التي مرت بها المهمة من التخطيط وحتى التنفيذ الميداني.</div>
            <div><span className="form-help-bullet">•</span> <strong>عدد المستفيدين:</strong> ذكر عدد المستفيدين بشكل تقديري من هذه المهمة.</div>
          </div>
          <p style={{ marginTop: '0.25rem', fontStyle: 'italic' }}>يرجى تحري الدقة في كتابة آلية التنفيذ لمساعدة مكتب المتابعة والتقييم على فهم المنهجية المتبعة وتقدير حجم الجهد المبذول في كل نشاط.</p>
        </div>
        {errors.execution_mechanism && <span className="alert alert-danger" style={{ padding: '0.4rem 0.8rem', margin: '0.2rem 0 0' }}>{errors.execution_mechanism}</span>}
      </div>

      {/* 4. Task Status & Issues row */}
      <div className="form-row">
        <div className="form-group">
          <label className="form-label">
            حالة المهمة
            <span className="required-star">*</span>
          </label>
          <select
            name="task_status"
            value={task.task_status}
            onChange={handleChange}
            className="form-control"
          >
            <option value="مكتملة">مكتملة</option>
            <option value="قيد التنفيذ">قيد التنفيذ</option>
            <option value="ملغاة">ملغاة</option>
          </select>
          <span className="form-help-text" style={{ background: 'transparent', padding: '0', border: 'none', fontSize: '0.8rem', marginTop: '0.1rem', color: 'var(--text-secondary)' }}>
            في حال تم إلغاؤها، يرجى ذكر السبب بوضوح في قسم "المشاكل أو العقبات".
          </span>
          {errors.task_status && <span className="alert alert-danger" style={{ padding: '0.4rem 0.8rem', margin: '0.2rem 0 0' }}>{errors.task_status}</span>}
        </div>

        <div className="form-group">
          <label className="form-label">
            المشاكل أو العقبات (إن وجدت)
          </label>
          <textarea
            name="issues"
            value={task.issues}
            onChange={handleChange}
            placeholder="اذكر أي مشاكل أو عقبات واجهت تنفيذ المهمة..."
            className="form-control"
            rows="3"
            style={{ resize: 'vertical' }}
          />
          {errors.issues && <span className="alert alert-danger" style={{ padding: '0.4rem 0.8rem', margin: '0.2rem 0 0' }}>{errors.issues}</span>}
        </div>
      </div>
    </div>
  );
}
