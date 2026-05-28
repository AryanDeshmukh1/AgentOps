import { useEffect, useState, createContext, useContext, useCallback } from 'react';
import { X, CheckCircle2, AlertTriangle, Info, AlertCircle } from 'lucide-react';
import clsx from 'clsx';

const ToastContext = createContext(null);

let nextId = 1;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const dismiss = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const toast = useCallback(({ title, message, variant = 'info', duration = 5000 }) => {
    const id = nextId++;
    setToasts(prev => [...prev, { id, title, message, variant }]);
    if (duration > 0) {
      setTimeout(() => dismiss(id), duration);
    }
    return id;
  }, [dismiss]);

  return (
    <ToastContext.Provider value={{ toast, dismiss }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm pointer-events-none">
        {toasts.map(t => (
          <ToastCard key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}

const VARIANTS = {
  success: { icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-950/80 border-emerald-700' },
  warning: { icon: AlertTriangle, color: 'text-amber-400', bg: 'bg-amber-950/80 border-amber-700' },
  danger: { icon: AlertCircle, color: 'text-red-400', bg: 'bg-red-950/80 border-red-700' },
  info: { icon: Info, color: 'text-sky-400', bg: 'bg-sky-950/80 border-sky-700' },
};

function ToastCard({ toast, onDismiss }) {
  const variant = VARIANTS[toast.variant] || VARIANTS.info;
  const Icon = variant.icon;
  return (
    <div
      className={clsx(
        'pointer-events-auto flex items-start gap-3 px-3 py-2.5 rounded-lg border backdrop-blur shadow-lg',
        'animate-in slide-in-from-right-4 duration-200',
        variant.bg,
      )}
    >
      <Icon className={clsx('w-4 h-4 mt-0.5 shrink-0', variant.color)} />
      <div className="flex-1 min-w-0">
        {toast.title && <div className="text-sm font-medium text-slate-100">{toast.title}</div>}
        {toast.message && <div className="text-xs text-slate-300 mt-0.5">{toast.message}</div>}
      </div>
      <button
        onClick={onDismiss}
        className="text-slate-500 hover:text-slate-300 shrink-0"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}