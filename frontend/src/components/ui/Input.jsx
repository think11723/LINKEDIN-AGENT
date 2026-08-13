import { forwardRef } from 'react';
import { cn } from '../../utils/cn.js';

export const Input = forwardRef(function Input({ className, type = 'text', ...rest }, ref) {
  return <input ref={ref} type={type} className={cn('input-base', className)} {...rest} />;
});

export const Textarea = forwardRef(function Textarea({ className, rows = 4, ...rest }, ref) {
  return (
    <textarea
      ref={ref}
      rows={rows}
      className={cn('textarea-base min-h-[80px] resize-y', className)}
      {...rest}
    />
  );
});

export function Select({ className, children, ...rest }) {
  return (
    <select className={cn('select-base', className)} {...rest}>
      {children}
    </select>
  );
}