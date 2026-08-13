import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { cn } from '../utils/cn.js';

const ToastContext = createContext(null);

let idCounter = 0;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const dismiss = useCallback((id) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const show = useCallback(
    ({ title, description, variant = 'default', duration = 4500 }) => {
      idCounter += 1;
      const id = `toast-${idCounter}`;
      setToasts((current) => [...current, { id, title, description, variant }]);
      if (duration > 0) {
        window.setTimeout(() => dismiss(id), duration);
      }
      return id;
    },
    [dismiss],
  );

  const toast = useMemo(
    () => ({
      success: (title, description) => show({ title, description, variant: 'success' }),
      error: (title, description) => show({ title, description, variant: 'error' }),
      info: (title, description) => show({ title, description, variant: 'info' }),
    }),
    [show],
  );

  return (
    <ToastContext.Provider value={{ toast, dismiss }}>
      {children}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="pointer-events-none fixed inset-x-0 top-4 z-50 flex flex-col items-end gap-2 px-4"
      >
        {toasts.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => dismiss(item.id)}
            className={cn(
              'pointer-events-auto w-full max-w-sm rounded-xl border px-4 py-3 text-left shadow-lg transition',
              item.variant === 'error'
                ? 'border-rose-500/40 bg-rose-950/60 text-rose-100'
                : item.variant === 'success'
                  ? 'border-emerald-500/40 bg-emerald-950/60 text-emerald-100'
                  : 'border-white/10 bg-zinc-900/90 text-zinc-100',
            )}
          >
            {item.title ? <div className="text-sm font-semibold">{item.title}</div> : null}
            {item.description ? (
              <div className="mt-1 text-xs opacity-80">{item.description}</div>
            ) : null}
          </button>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error('useToast must be used inside ToastProvider');
  }
  return ctx;
}