import { motion } from 'framer-motion';
import { cn } from '../../utils/cn.js';

export function Card({
  className,
  variant = 'default',
  hoverable = false,
  children,
  ...rest
}) {
  const variantClass = {
    default: 'glass-card',
    elevated: 'glass-card-elevated',
    inset: 'glass-inset',
    strong: 'glass-strong',
    flat: 'rounded-2xl border border-white/[0.08] bg-white/[0.02]',
  }[variant] ?? 'glass-card';

  if (hoverable) {
    return (
      <motion.div
        whileHover={{ y: -2 }}
        transition={{ type: 'spring', stiffness: 400, damping: 25 }}
        className={cn(variantClass, 'transition-shadow', className)}
        {...rest}
      >
        {children}
      </motion.div>
    );
  }

  return (
    <div className={cn(variantClass, className)} {...rest}>
      {children}
    </div>
  );
}

export function CardHeader({ className, ...rest }) {
  return (
    <div
      className={cn(
        'flex flex-col gap-1.5 border-b border-white/[0.06] p-6',
        className,
      )}
      {...rest}
    />
  );
}

export function CardTitle({ className, as: Component = 'h3', ...rest }) {
  return (
    <Component
      className={cn(
        'text-lg font-semibold tracking-tight text-white',
        className,
      )}
      {...rest}
    />
  );
}

export function CardDescription({ className, ...rest }) {
  return (
    <p
      className={cn('text-sm text-text-secondary', className)}
      {...rest}
    />
  );
}

export function CardContent({ className, ...rest }) {
  return <div className={cn('p-6', className)} {...rest} />;
}

export function CardFooter({ className, ...rest }) {
  return (
    <div
      className={cn(
        'flex flex-col gap-2 border-t border-white/[0.06] p-6 sm:flex-row sm:items-center sm:justify-between',
        className,
      )}
      {...rest}
    />
  );
}
