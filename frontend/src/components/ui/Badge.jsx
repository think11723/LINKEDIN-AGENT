import { cn } from '../../utils/cn.js';
import { TONE } from '../../utils/design.js';

const sizeClasses = {
  xs: 'h-5 px-1.5 text-[10px] gap-1',
  sm: 'h-6 px-2 text-[11px] gap-1',
  md: 'h-7 px-2.5 text-xs gap-1.5',
  lg: 'h-8 px-3 text-sm gap-1.5',
};

export function Badge({
  className,
  tone = 'neutral',
  size = 'sm',
  withDot = false,
  children,
  ...rest
}) {
  const toneClass = TONE[tone] ?? TONE.neutral;
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border font-medium leading-none whitespace-nowrap transition-colors',
        toneClass.bg,
        toneClass.border,
        toneClass.text,
        sizeClasses[size] ?? sizeClasses.sm,
        className,
      )}
      {...rest}
    >
      {withDot ? (
        <span
          className={cn('h-1.5 w-1.5 shrink-0 rounded-full', toneClass.dot)}
          aria-hidden
        />
      ) : null}
      {children}
    </span>
  );
}
