import { cn } from '../../utils/cn.js';

/**
 * Polished segmented control used for the topic/URL mode selector on
 * the Create Post page. Renders as a row of equal-width pill cards
 * with an icon, label, and optional short description; the active
 * tab is highlighted with a subtle gradient and ring.
 */
export function SegmentedTabs({ value, onChange, options, className }) {
  return (
    <div
      role="tablist"
      aria-orientation="horizontal"
      className={cn(
        'grid gap-3 sm:grid-cols-2',
        className,
      )}
    >
      {options.map((opt) => {
        const active = opt.value === value;
        const Icon = opt.icon;
        return (
          <button
            key={opt.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(opt.value)}
            className={cn(
              'group relative flex items-start gap-3 rounded-2xl border p-4 text-left transition-all duration-150',
              'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60',
              active
                ? 'border-brand-400/40 bg-gradient-to-br from-brand-500/[0.18] via-brand-500/[0.06] to-transparent shadow-glow-brand'
                : 'border-white/10 bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.04]',
            )}
          >
            <span
              className={cn(
                'flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border transition',
                active
                  ? 'border-brand-400/40 bg-brand-500/20 text-brand-200'
                  : 'border-white/10 bg-white/[0.04] text-text-secondary group-hover:text-zinc-200',
              )}
              aria-hidden
            >
              {Icon}
            </span>
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-2">
                <span
                  className={cn(
                    'text-sm font-semibold',
                    active ? 'text-white' : 'text-zinc-100',
                  )}
                >
                  {opt.label}
                </span>
                {opt.badge ? (
                  <span className="rounded-md border border-white/10 bg-white/[0.04] px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-text-muted">
                    {opt.badge}
                  </span>
                ) : null}
              </span>
              {opt.description ? (
                <span className="mt-0.5 block text-xs text-text-secondary">
                  {opt.description}
                </span>
              ) : null}
            </span>
            <span
              className={cn(
                'mt-1 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full border transition',
                active
                  ? 'border-brand-400/50 bg-brand-500/30 text-brand-100'
                  : 'border-white/15 text-transparent',
              )}
              aria-hidden
            >
              <svg viewBox="0 0 16 16" className="h-3 w-3" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 8.5 6.5 12 13 4.5" />
              </svg>
            </span>
          </button>
        );
      })}
    </div>
  );
}
