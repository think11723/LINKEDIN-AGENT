import { cn } from '../../utils/cn.js';

const variants = {
  default: 'border-white/10 bg-white/5 text-zinc-100',
  outline: 'border-white/15 bg-transparent text-zinc-200',
  success: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200',
  warning: 'border-amber-500/40 bg-amber-500/10 text-amber-200',
  info: 'border-sky-500/40 bg-sky-500/10 text-sky-200',
  muted: 'border-white/10 bg-white/[0.03] text-zinc-400',
};

export function Badge({ variant = 'default', className, ...rest }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium',
        variants[variant] ?? variants.default,
        className,
      )}
      {...rest}
    />
  );
}