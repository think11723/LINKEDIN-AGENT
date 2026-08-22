import { forwardRef } from 'react';
import { motion } from 'framer-motion';
import { cn } from '../../utils/cn.js';

const variantClasses = {
  primary:
    'bg-white/95 text-zinc-950 hover:bg-white border border-white/20 shadow-sm',
  brand:
    'gradient-brand text-white border border-white/10 shadow-glow-brand hover:shadow-[0_0_40px_rgba(79,140,255,0.55)]',
  secondary:
    'glass-card text-zinc-100 hover:bg-white/[0.06] border-white/[0.08]',
  outline:
    'bg-transparent text-zinc-100 border border-white/[0.14] hover:border-white/[0.22] hover:bg-white/[0.04]',
  ghost:
    'bg-transparent text-zinc-300 hover:bg-white/[0.05] hover:text-white',
  danger:
    'bg-rose-500/90 text-white border border-rose-400/40 hover:bg-rose-500',
  subtle:
    'bg-white/[0.05] text-zinc-200 border border-white/[0.06] hover:bg-white/[0.08]',
};

const sizeClasses = {
  xs: 'h-7 px-2.5 text-xs rounded-lg gap-1.5',
  sm: 'h-8 px-3 text-xs rounded-lg gap-1.5',
  md: 'h-10 px-4 text-sm rounded-xl gap-2',
  lg: 'h-11 px-5 text-sm rounded-xl gap-2',
  xl: 'h-12 px-6 text-base rounded-2xl gap-2.5',
  icon: 'h-10 w-10 rounded-xl',
  'icon-sm': 'h-8 w-8 rounded-lg',
  'icon-lg': 'h-11 w-11 rounded-xl',
};

export const Button = forwardRef(function Button(
  {
    as: Component = 'button',
    variant = 'secondary',
    size = 'md',
    className,
    loading,
    disabled,
    children,
    leftIcon,
    rightIcon,
    fullWidth = false,
    ...rest
  },
  ref,
) {
  const isDisabled = disabled || loading;
  const MotionComponent = motion(Component);
  return (
    <MotionComponent
      ref={ref}
      disabled={isDisabled}
      whileHover={isDisabled ? undefined : { scale: 1.02 }}
      whileTap={isDisabled ? undefined : { scale: 0.98 }}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
      className={cn(
        'btn-base',
        variantClasses[variant] ?? variantClasses.secondary,
        sizeClasses[size] ?? sizeClasses.md,
        fullWidth && 'w-full',
        className,
      )}
      {...rest}
    >
      {loading ? (
        <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-r-transparent" />
      ) : leftIcon ? (
        <span className="inline-flex shrink-0">{leftIcon}</span>
      ) : null}
      {children}
      {rightIcon && !loading ? (
        <span className="inline-flex shrink-0">{rightIcon}</span>
      ) : null}
    </MotionComponent>
  );
});
