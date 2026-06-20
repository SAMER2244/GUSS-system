import React, { useState } from 'react';
import TaskCard from './TaskCard';

export default function TasksStep({ formData, updateFormData, onNext, onPrev }) {
  const [taskErrors, setTaskErrors] = useState([]);

  const handleTaskChange = (index, field, value) => {
    const updatedTasks = [...formData.tasks];
    updatedTasks[index] = {
      ...updatedTasks[index],
      [field]: value
    };
    updateFormData({ tasks: updatedTasks });

    // Clear error for this specific task field
    if (taskErrors[index] && taskErrors[index][field]) {
      const newErrors = [...taskErrors];
      newErrors[index] = {
        ...newErrors[index],
        [field]: null
      };
      setTaskErrors(newErrors);
    }
  };

  const handleAddTask = () => {
    const updatedTasks = [...formData.tasks, {
      manager_name: '',
      manager_phone: '',
      task_name: '',
      task_description: '',
      task_type: 'ضمن الخطة الشهرية',
      execution_mechanism: '',
      task_status: 'مكتملة',
      issues: ''
    }];
    updateFormData({ tasks: updatedTasks });
    setTaskErrors([...taskErrors, {}]);
  };

  const handleDeleteTask = (index) => {
    if (index === 0) return; // Prevent deleting first task
    const updatedTasks = formData.tasks.filter((_, i) => i !== index);
    const updatedErrors = taskErrors.filter((_, i) => i !== index);
    updateFormData({ tasks: updatedTasks });
    setTaskErrors(updatedErrors);
  };

  const validate = () => {
    let isValid = true;
    const newErrors = [];

    formData.tasks.forEach((task, idx) => {
      const errors = {};
      if (!task.manager_name.trim()) {
        errors.manager_name = 'هذا الحقل إلزامي.';
        isValid = false;
      }
      if (!task.manager_phone.trim()) {
        errors.manager_phone = 'هذا الحقل إلزامي.';
        isValid = false;
      }
      if (!task.task_name.trim()) {
        errors.task_name = 'هذا الحقل إلزامي.';
        isValid = false;
      }
      if (!task.execution_mechanism.trim()) {
        errors.execution_mechanism = 'هذا الحقل إلزامي.';
        isValid = false;
      }
      newErrors[idx] = errors;
    });

    setTaskErrors(newErrors);
    return isValid;
  };

  const handleNext = () => {
    if (validate()) {
      onNext();
    }
  };

  return (
    <div className="animate-slide-up">
      <div className="form-help-text" style={{ marginBottom: '2rem' }}>
        <p style={{ fontWeight: 'bold', marginBottom: '0.5rem' }}>
          يرجى تدوين المهام التي تم العمل عليها خلال هذا الشهر بدقة.
        </p>
        <p style={{ fontSize: '0.85rem', lineHeight: '1.5' }}>
          سيتم مقارنة هذه البيانات مع الخطة الشهرية لتقييم نسبة الإنجاز وتحليل الأداء وتفادي المشاكل والعقبات المستقبلية.
          عند إضافة كل مهمة، يرجى مراعاة الآتي:
        </p>
        <ul style={{ listStyle: 'none', paddingRight: '0.8rem', fontSize: '0.82rem', marginTop: '0.5rem' }}>
          <li><span className="form-help-bullet">•</span> <strong>تحديد النوع:</strong> ميز بوضوح بين المهام التي كانت مدرجة أصلاً في الخطة، والمهام التي استُجدت نتيجة تكليفات الإدارة أو ظروف الميدان.</li>
          <li><span className="form-help-bullet">•</span> <strong>واقعية التنفيذ:</strong> اشرح الآلية الفعلية التي تمت بها المهمة، مع ذكر أي تعاون جرى مع مكاتب أخرى.</li>
          <li><span className="form-help-bullet">•</span> <strong>تحديث الحالة:</strong> كن دقيقاً في اختيار حالة المهمة (مكتملة، قيد التنفيذ، أو ملغاة)، مع ذكر الأسباب في حال التعثر.</li>
          <li><span className="form-help-bullet">•</span> <strong>رصد العقبات:</strong> ذكر المشاكل المرتبطة بمهمة معينة يساعدنا في توثيق العوائق التقنية أو الإدارية بشكل تراكمي.</li>
        </ul>
      </div>

      {/* Render Tasks Loops */}
      {formData.tasks.map((task, index) => (
        <TaskCard
          key={index}
          task={task}
          index={index}
          onChange={handleTaskChange}
          onDelete={handleDeleteTask}
          errors={taskErrors[index]}
        />
      ))}

      {/* Add Task Button */}
      <button 
        type="button" 
        onClick={handleAddTask} 
        className="btn-add-task"
        style={{ marginTop: '1rem' }}
      >
        <i className="fa-solid fa-circle-plus"></i>
        إضافة مهمة أخرى
      </button>

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
