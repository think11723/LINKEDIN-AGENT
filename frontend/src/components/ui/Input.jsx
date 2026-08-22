import { forwardRef } from 'react';
import { cn } from '../../utils/cn.js';

const baseField =
  'input-base w-full rounded-xl border px-3.5 py-2.5 text-sm transition';

export const Input = forwardRef(function Input(
  {
    className,
    type = 'text',
    size = 'md',
    leftIcon,
    rightIcon,
    invalid,
    ...rest
  },
  ref,
) {
  const heightClass =
    size === 'sm' ? 'h-9' : size === 'lg' ? 'h-12' : 'h-10';
  return (
    <div className={cn('relative w-full', invalid && 'has-error')}>
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
          invalid &&
            'border-rose-500/60 focus:border-rose-500/80 focus:ring-rose-500/20',
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
  { className, rows = 4, invalid, ...rest },
  ref,
) {
  return (
    <textarea
      ref={ref}
      rows={rows}
      className={cn(
        baseField,
        'min-h-[80px] py-2.5 resize-y',
        invalid &&
          'border-rose-500/60 focus:border-rose-500/80 focus:ring-rose-500/20',
        className,
      )}
      {...rest}
    />
  );
});

export function Select({ className, children, ...rest }) {
  return (
    <div className="relative w-full">
      <select
        className={cn(
          baseField,
          'h-10 appearance-none pr-9',
          className,
        )}
        {...rest}
      >
        {children}
      </select>
      <svg
        aria-hidden
        className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted"
        viewBox="0 0 16 16"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      >
        <path d="M4 6l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
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
  optional,
}) {
  return (
    <div className={cn('space-y-1.5', className)}>
      {label ? (
        <label
          htmlFor={id}
          className="flex items-center gap-1.5 text-sm font-medium text-zinc-200"
        >
          {label}
          {required ? (
            <span className="text-rose-400">*</span>
          ) : null}
          {optional ? (
            <span className="text-[11px] uppercase tracking-wider text-text-muted">Optional</span>
          ) : null}
        </label>
      ) : null}
      {children}
      {hint && !error ? (
        <div className="text-xs text-text-muted">{hint}</div>
      ) : null}
      {error ? (
        <div className="flex items-center gap-1.5 text-xs text-rose-300">
          <span className="inline-block h-1 w-1 rounded-full bg-rose-400" />
          {error}
        </div>
      ) : null}
    </div>
  );
}
