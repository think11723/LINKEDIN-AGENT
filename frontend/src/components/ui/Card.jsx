import { cn } from '../../utils/cn.js';

export function Card({ className, variant = 'default', ...rest }) {
  const variantClass = {
    default: 'panel',
    elevated: 'panel-elevated',
    muted: 'panel-muted',
    inset: 'panel-inset',
  }[variant] ?? 'panel';
  return <div className={cn(variantClass, className)} {...rest} />;
}

export function CardHeader({ className, ...rest }) {
  return (
    <div
      className={cn(
        'flex flex-col gap-1.5 border-b border-white/[0.06] p-5 sm:p-6',
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
        'text-base font-semibold tracking-tight text-zinc-50 sm:text-lg',
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
  return <div className={cn('p-5 sm:p-6', className)} {...rest} />;
}

export function CardFooter({ className, ...rest }) {
  return (
    <div
      className={cn(
        'flex flex-col gap-2 border-t border-white/[0.06] p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6',
        className,
      )}
      {...rest}
    />
  );
}
