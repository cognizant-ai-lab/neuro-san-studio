import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';

const Ctx = createContext(null);

export function ToasterProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const push = useCallback((type, message) => {
    const id = Math.random().toString(36).slice(2);
    setToasts(t => [...t, { id, type, message }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 4000);
  }, []);
  useEffect(() => {
    const handler = (e) => {
      const { type, message } = e.detail || {};
      if (!type || !message) return;
      push(type, message);
    };
    window.addEventListener('toast', handler);
    return () => window.removeEventListener('toast', handler);
  }, [push]);
  const api = {
    success: (m) => push('success', m),
    info: (m) => push('info', m),
    error: (m) => push('error', m),
  };
  return (
    <Ctx.Provider value={api}>
      {children}
      <div aria-live="polite" aria-atomic="true" style={{ position:'fixed', right:16, bottom:16, display:'grid', gap:8, zIndex:1000 }}>
        {toasts.map(t => (
          <div key={t.id} role="status" className="toast" style={{
            background:'var(--color-surface)',
            border:'1px solid var(--color-border)',
            borderRadius:12,
            padding:'8px 12px',
            boxShadow:'0 10px 30px rgba(0,0,0,0.25), 0 0 0 1px rgba(255,255,255,0.03) inset',
            color:'var(--color-text)'
          }}>
            <strong style={{ color: t.type==='error'?'#f87171': t.type==='success'?'#22c55e':'#38bdf8' }}>{t.type.toUpperCase()}</strong>
            <div>{t.message}</div>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useToaster() {
  return useContext(Ctx) || { success: ()=>{}, info: ()=>{}, error: ()=>{} };
}

