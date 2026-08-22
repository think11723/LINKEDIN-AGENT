import { CheckCircle2, Circle, Loader2 } from 'lucide-react';
import { cn } from '../../utils/cn.js';

/**
 * Linear step progress for the generation flow. Each step has a
 * state: 'pending' (not yet started), 'active' (currently running),
 * 'done' (complete), 'error' (failed). Only steps that correspond to
 * real workflow stages should be passed in.
 */
export function StepProgress({ steps, className }) {
  return (
    <ol
      className={cn(
        'flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-0',
        className,
      )}
    >
      {steps.map((step, idx) => {
        const isLast = idx === steps.length - 1;
        return (
          <li
            key={step.id}
            className={cn(
              'flex flex-1 items-center gap-3 sm:flex-col sm:items-start sm:gap-2 sm:pr-4',
              isLast && 'sm:flex-[0_0_auto] sm:pr-0',
            )}
          >
            <div className="flex items-center gap-3 sm:w-full sm:items-center">
              <StepIcon state={step.state} />
              <div className="min-w-0 sm:flex-1">
                <div
                  className={cn(
                    'text-sm font-medium',
                    step.state === 'active'
                      ? 'text-white'
                      : step.state === 'done'
                      ? 'text-zinc-200'
                      : 'text-text-muted',
                  )}
                >
                  {step.label}
                </div>
                {step.hint ? (
                  <div className="text-xs text-text-muted">{step.hint}</div>
                ) : null}
              </div>
            </div>
            {!isLast ? (
              <div className="hidden h-px flex-1 bg-white/10 sm:block" />
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

function StepIcon({ state }) {
  if (state === 'done') {
    return (
      <span
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-emerald-400/30 bg-emerald-500/15 text-emerald-300"
        aria-hidden
      >
        <CheckCircle2 className="h-4 w-4" />
      </span>
    );
  }
  if (state === 'active') {
    return (
      <span
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-brand-400/40 bg-brand-500/20 text-brand-200"
        aria-hidden
      >
        <Loader2 className="h-4 w-4 animate-spin" />
      </span>
    );
  }
  if (state === 'error') {
    return (
      <span
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-rose-400/30 bg-rose-500/15 text-rose-300"
        aria-hidden
      >
        <span className="h-2 w-2 rounded-full bg-rose-400" />
      </span>
    );
  }
  return (
    <span
      className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/[0.03] text-text-muted"
      aria-hidden
    >
      <Circle className="h-4 w-4" />
    </span>
  );
}
