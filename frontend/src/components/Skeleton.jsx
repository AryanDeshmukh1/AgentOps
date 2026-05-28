import clsx from 'clsx';

export function Skeleton({ className }) {
  return <div className={clsx('animate-pulse rounded bg-slate-800/60', className)} />;
}

export function SkeletonTable({ rows = 5, cols = 6 }) {
  return (
    <div className="p-4 space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-3">
          {Array.from({ length: cols }).map((_, j) => (
            <Skeleton key={j} className={clsx('h-4', j === 0 ? 'flex-[2]' : 'flex-1')} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function SkeletonCard() {
  return (
    <div className="p-4 space-y-3">
      <div className="flex items-center justify-between">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-5 w-16 rounded-full" />
      </div>
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-3 w-1/2" />
    </div>
  );
}

export function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <div className="text-6xl font-mono text-slate-700 mb-2">404</div>
      <div className="text-sm text-slate-400">Route not found</div>
      <a href="/" className="mt-4 text-xs text-emerald-400 hover:text-emerald-300">← back to dashboard</a>
    </div>
  );
}