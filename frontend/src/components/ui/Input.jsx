import { forwardRef } from 'react';
import { cn } from '../../utils/cn.js';

const baseField =
  'w-full rounded-xl border border-white/10 bg-black/30 px-3 text-sm text-zinc-100 placeholder-zinc-500 outline-none transition focus:border-brand-400/60 focus:ring-2 focus:ring-brand-500/20 disabled:opacity-50 disabled:cursor-not-allowed';

export const Input = forwardRef(function Input(
  { className, type = 'text', size = 'md', leftIcon, rightIcon, ...rest },
  ref,
) {
  const heightClass = size === 'sm' ? 'h-9' : size === 'lg' ? 'h-12' : 'h-10';
  return (
    <div className="relative w-full">
      {leftIcon ? (
        <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-text-muted">
          {leftIcon}
        </span>
      ) : null}
      <input
        ref={ref}
        type={type}
        className={cn(
          baseField,
          heightClass,
          leftIcon ? 'pl-9' : null,
          rightIcon ? 'pr-9' : null,
          className,
        )}
        {...rest}
      />
      {rightIcon ? (
        <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-text-muted">
          {rightIcon}
        </span>
      ) : null}
    </div>
  );
});

export const Textarea = forwardRef(function Textarea(
  { className, rows = 4, ...rest },
  ref,
) {
  return (
    <textarea
      ref={ref}
      rows={rows}
      className={cn(
        baseField,
        'min-h-[80px] py-2.5 resize-y',
        className,
      )}
      {...rest}
    />
  );
});

export function Select({ className, children, ...rest }) {
  return (
    <select className={cn(baseField, 'h-10 appearance-none pr-8', className)} {...rest}>
      {children}
    </select>
  );
}

export function Field({
  label,
  hint,
  error,
  required,
  children,
  className,
  id,
}) {
  return (
    <div className={cn('space-y-1.5', className)}>
      {label ? (
        <label
          htmlFor={id}
          className="flex items-center gap-1 text-sm font-medium text-zinc-200"
        >
          {label}
          {required ? <span className="text-rose-400">*</span> : null}
        </label>
      ) : null}
      {children}
      {hint && !error ? (
        <div className="text-xs text-text-muted">{hint}</div>
      ) : null}
      {error ? (
        <div className="text-xs text-rose-300">{error}</div>
      ) : null}
    </div>
  );
}
