import { forwardRef } from 'react';
import { cn } from '../../utils/cn.js';

const variantClasses = {
  primary:
    'bg-zinc-50 text-zinc-950 hover:bg-white border border-white/10 shadow-sm',
  brand:
    'bg-gradient-to-b from-brand-500 to-brand-600 text-white border border-brand-400/40 hover:from-brand-400 hover:to-brand-500 shadow-glow-brand',
  secondary:
    'bg-white/[0.04] text-zinc-100 border border-white/10 hover:bg-white/[0.08] hover:border-white/20',
  outline:
    'bg-transparent text-zinc-100 border border-white/15 hover:border-white/30 hover:bg-white/[0.04]',
  ghost: 'bg-transparent text-zinc-300 hover:bg-white/[0.05] hover:text-white',
  danger:
    'bg-rose-600/90 text-white border border-rose-500/40 hover:bg-rose-500 shadow-sm',
  success:
    'bg-emerald-500/90 text-white border border-emerald-400/40 hover:bg-emerald-500 shadow-sm',
};

const sizeClasses = {
  xs: 'h-8 px-3 text-xs rounded-lg',
  sm: 'h-9 px-3.5 text-sm rounded-xl',
  md: 'h-10 px-4 text-sm rounded-xl',
  lg: 'h-11 px-5 text-sm rounded-xl',
  xl: 'h-12 px-6 text-base rounded-xl',
  icon: 'h-10 w-10 rounded-xl',
  'icon-sm': 'h-8 w-8 rounded-lg',
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
    leftIcon,
    rightIcon,
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
        'inline-flex items-center justify-center gap-2 font-medium transition-all duration-150 disabled:cursor-not-allowed disabled:opacity-60 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400/60 focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-[0.98]',
        variantClasses[variant] ?? variantClasses.primary,
        sizeClasses[size] ?? sizeClasses.md,
        className,
      )}
      {...rest}
    >
      {loading ? (
        <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-r-transparent" />
      ) : leftIcon ? (
        <span className="inline-flex shrink-0">{leftIcon}</span>
      ) : null}
      {children}
      {rightIcon && !loading ? (
        <span className="inline-flex shrink-0">{rightIcon}</span>
      ) : null}
    </Component>
  );
});
