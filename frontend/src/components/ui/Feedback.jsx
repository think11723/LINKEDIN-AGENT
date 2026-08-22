import { AlertCircle, CheckCircle2, Info, AlertTriangle } from 'lucide-react';
import { motion } from 'framer-motion';
import { cn } from '../../utils/cn.js';

export function Spinner({ className, size = 'md' }) {
  const sizeMap = {
    xs: 'h-3 w-3 border',
    sm: 'h-3.5 w-3.5 border-2',
    md: 'h-4 w-4 border-2',
    lg: 'h-5 w-5 border-2',
    xl: 'h-6 w-6 border-[3px]',
  };
  return (
    <span
      className={cn(
        'inline-block animate-spin rounded-full border-current border-r-transparent',
        sizeMap[size] ?? sizeMap.md,
        className,
      )}
      role="status"
      aria-label="Loading"
    />
  );
}

export function Skeleton({ className, ...rest }) {
  return <div className={cn('skeleton', className)} {...rest} />;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
  size = 'md',
}) {
  const sizeMap = {
    sm: { padding: 'p-6', iconBox: 'h-10 w-10', iconSize: 'h-5 w-5' },
    md: { padding: 'p-8', iconBox: 'h-14 w-14', iconSize: 'h-7 w-7' },
    lg: { padding: 'p-10', iconBox: 'h-16 w-16', iconSize: 'h-8 w-8' },
  };
  const s = sizeMap[size] ?? sizeMap.md;
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={cn(
        'glass-card flex flex-col items-center justify-center rounded-2xl text-center',
        s.padding,
        className,
      )}
    >
      {icon ? (
        <div
          className={cn(
            'mb-3 inline-flex items-center justify-center rounded-2xl border border-white/[0.08] bg-gradient-brand-soft text-brand-300',
            s.iconBox,
          )}
          aria-hidden
        >
          <span className={s.iconSize}>{icon}</span>
        </div>
      ) : null}
      {title ? (
        <div className="text-base font-semibold text-white">{title}</div>
      ) : null}
      {description ? (
        <div className="mt-1 max-w-md text-sm text-text-secondary">
          {description}
        </div>
      ) : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </motion.div>
  );
}

const bannerTones = {
  danger: {
    wrap: 'border-rose-500/30 bg-rose-500/[0.08]',
    title: 'text-rose-100',
    body: 'text-rose-200/80',
    icon: 'text-rose-300',
    Icon: AlertCircle,
  },
  warning: {
    wrap: 'border-amber-500/30 bg-amber-500/[0.08]',
    title: 'text-amber-100',
    body: 'text-amber-200/80',
    icon: 'text-amber-300',
    Icon: AlertTriangle,
  },
  success: {
    wrap: 'border-emerald-500/30 bg-emerald-500/[0.08]',
    title: 'text-emerald-100',
    body: 'text-emerald-200/80',
    icon: 'text-emerald-300',
    Icon: CheckCircle2,
  },
  info: {
    wrap: 'border-sky-500/30 bg-sky-500/[0.08]',
    title: 'text-sky-100',
    body: 'text-sky-200/80',
    icon: 'text-sky-300',
    Icon: Info,
  },
};

export function ErrorBanner({
  error,
  onRetry,
  tone = 'danger',
  title,
  className,
}) {
  if (!error) return null;
  const t = bannerTones[tone] ?? bannerTones.danger;
  const Icon = t.Icon;
  const message =
    typeof error === 'string' ? error : error?.message || 'Something went wrong.';
  return (
    <motion.div
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={cn(
        'flex items-start gap-3 rounded-2xl border p-4 text-sm',
        t.wrap,
        className,
      )}
      role={tone === 'danger' || tone === 'warning' ? 'alert' : 'status'}
    >
      <Icon className={cn('mt-0.5 h-4 w-4 shrink-0', t.icon)} aria-hidden />
      <div className="flex-1">
        {title ? <div className={cn('font-semibold', t.title)}>{title}</div> : null}
        <div className={t.body}>{message}</div>
      </div>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className={cn(
            'shrink-0 rounded-xl border px-3 py-1 text-xs font-medium transition hover:opacity-80',
            t.wrap,
            t.title,
          )}
        >
          Retry
        </button>
      ) : null}
    </motion.div>
  );
}
