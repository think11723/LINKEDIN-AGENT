import { cn } from '../../utils/cn.js';

export function Card({ className, ...rest }) {
  return <div className={cn('panel', className)} {...rest} />;
}

export function CardHeader({ className, ...rest }) {
  return (
    <div
      className={cn('flex flex-col gap-1.5 border-b border-white/5 p-5', className)}
      {...rest}
    />
  );
}

export function CardTitle({ className, ...rest }) {
  return <div className={cn('text-base font-semibold text-zinc-50', className)} {...rest} />;
}

export function CardDescription({ className, ...rest }) {
  return <div className={cn('text-sm text-zinc-400', className)} {...rest} />;
}

export function CardContent({ className, ...rest }) {
  return <div className={cn('p-5', className)} {...rest} />;
}