import { cn } from '../../utils/cn.js';

export function Spinner({ className }) {
  return (
    <span
      className={cn(
        'inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent',
        className,
      )}
      role="status"
      aria-label="Loading"
    />
  );
}

export function Skeleton({ className }) {
  return <div className={cn('animate-pulse rounded-lg bg-white/5', className)} />;
}

export function EmptyState({ title, description, action }) {
  return (
    <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.03] p-6 text-center">
      <div className="text-sm font-medium text-zinc-200">{title}</div>
      {description ? (
        <div className="mt-1 text-sm text-zinc-400">{description}</div>
      ) : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function ErrorBanner({ error, onRetry }) {
  if (!error) return null;
  const message = error?.message || 'Something went wrong.';
  return (
    <div className="flex items-start gap-3 rounded-xl border border-rose-500/30 bg-rose-500/5 p-3 text-sm text-rose-200">
      <div className="flex-1">
        <div className="font-medium">Error</div>
        <div className="text-rose-300/80">{message}</div>
      </div>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-lg border border-rose-500/40 px-3 py-1 text-xs hover:bg-rose-500/10"
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}