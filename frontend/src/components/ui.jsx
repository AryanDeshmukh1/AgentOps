import clsx from 'clsx';

export function Card({ children, className }) {
  return (
    <div className={clsx('rounded-lg border border-slate-800 bg-slate-900/40', className)}>
      {children}
    </div>
  );
}

export function CardHeader({ children, className }) {
  return (
    <div className={clsx('px-5 py-3 border-b border-slate-800', className)}>
      {children}
    </div>
  );
}

export function CardBody({ children, className }) {
  return <div className={clsx('p-5', className)}>{children}</div>;
}

const BADGE_VARIANTS = {
  default:  'bg-slate-700/40 text-slate-300 border-slate-700',
  success:  'bg-emerald-900/40 text-emerald-300 border-emerald-800',
  warning:  'bg-amber-900/40 text-amber-300 border-amber-800',
  danger:   'bg-red-900/40 text-red-300 border-red-800',
  info:     'bg-sky-900/40 text-sky-300 border-sky-800',
  muted:    'bg-slate-800/40 text-slate-500 border-slate-800',
};

export function Badge({ variant = 'default', children, className }) {
  return (
    <span className={clsx(
      'inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-wider border',
      BADGE_VARIANTS[variant] || BADGE_VARIANTS.default,
      className,
    )}>
      {children}
    </span>
  );
}

export function EmptyState({ title, hint, icon: Icon }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {Icon && <Icon className="w-10 h-10 text-slate-700 mb-3" />}
      <div className="text-slate-400 font-medium">{title}</div>
      {hint && <div className="text-xs text-slate-600 mt-1">{hint}</div>}
    </div>
  );
}

export function PageHeader({ title, subtitle, children }) {
  return (
    <div className="flex items-end justify-between mb-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-100">{title}</h1>
        {subtitle && <p className="text-sm text-slate-500 mt-1">{subtitle}</p>}
      </div>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </div>
  );
}
