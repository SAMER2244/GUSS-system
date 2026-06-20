import React, { useEffect, useState } from 'react';

export default function ThemeToggle() {
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('theme') || 'dark'; // default to dark as requested
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => (prev === 'light' ? 'dark' : 'light'));
  };

  return (
    <button 
      type="button" 
      onClick={toggleTheme} 
      className="theme-toggle-btn"
      title={theme === 'light' ? 'تفعيل الوضع الداكن' : 'تفعيل الوضع المضيء'}
    >
      <i className={`fa-solid ${theme === 'light' ? 'fa-moon' : 'fa-sun'}`}></i>
    </button>
  );
}
