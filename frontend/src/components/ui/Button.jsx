import { forwardRef } from 'react';
import { cn } from '../../utils/cn.js';

const variantClasses = {
  primary:
    'bg-zinc-50 text-zinc-950 hover:bg-white border border-white/10 shadow-sm',
  secondary:
    'bg-white/5 text-zinc-100 border border-white/10 hover:bg-white/10',
  outline:
    'bg-transparent text-zinc-100 border border-white/15 hover:border-white/30 hover:bg-white/5',
  ghost: 'bg-transparent text-zinc-200 hover:bg-white/5',
  danger:
    'bg-rose-600/90 text-white border border-rose-500/40 hover:bg-rose-500',
};

const sizeClasses = {
  sm: 'h-9 px-3 text-sm rounded-xl',
  md: 'h-10 px-4 text-sm rounded-xl',
  lg: 'h-11 px-6 text-sm rounded-xl',
  icon: 'h-10 w-10 rounded-xl',
};

export const Button = forwardRef(function Button(
  {
    as: Component = 'button',
    variant = 'primary',
    size = 'md',
    className,
    loading,
    disabled,
    children,
    ...rest
  },
  ref,
) {
  const isDisabled = disabled || loading;
  return (
    <Component
      ref={ref}
      disabled={isDisabled}
      className={cn(
        'inline-flex items-center justify-center gap-2 font-medium transition disabled:cursor-not-allowed disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/60',
        variantClasses[variant] ?? variantClasses.primary,
        sizeClasses[size] ?? sizeClasses.md,
        className,
      )}
      {...rest}
    >
      {loading ? (
        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-r-transparent" />
      ) : null}
      {children}
    </Component>
  );
});