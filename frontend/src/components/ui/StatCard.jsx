import { cn } from '../../utils/cn.js';

/**
 * Stat / KPI card used on the Dashboard. Polished dark glass with a
 * large number, label, optional trend indicator, and an icon chip.
 */
export function StatCard({
  label,
  value,
  hint,
  icon,
  trend, // { direction: 'up' | 'down' | 'flat', value: '+12%' }
  tone = 'neutral',
  className,
  ...rest
}) {
  const toneClass = {
    neutral: 'text-text-secondary',
    brand: 'text-brand-300',
    success: 'text-emerald-300',
    warning: 'text-amber-300',
    danger: 'text-rose-300',
    info: 'text-sky-300',
  }[tone] ?? 'text-text-secondary';

  const trendClass = {
    up: 'text-emerald-300',
    down: 'text-rose-300',
    flat: 'text-text-muted',
  }[trend?.direction] ?? 'text-text-muted';

  return (
    <div
      className={cn(
        'panel relative flex flex-col gap-3 p-5 transition hover:border-white/20',
        className,
      )}
      {...rest}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm text-text-secondary">{label}</div>
        {icon ? (
          <div
            className={cn(
              'flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04]',
              toneClass,
            )}
            aria-hidden
          >
            {icon}
          </div>
        ) : null}
      </div>
      <div className="flex items-baseline gap-2">
        <div className="text-3xl font-semibold tracking-tight text-white">
          {value}
        </div>
        {trend ? (
          <div className={cn('text-xs font-medium', trendClass)}>
            {trend.value}
          </div>
        ) : null}
      </div>
      {hint ? (
        <div className="text-xs text-text-muted">{hint}</div>
      ) : null}
    </div>
  );
}
