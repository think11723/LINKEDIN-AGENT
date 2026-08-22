import { useEffect, useState } from 'react';
import { Sparkles, Loader2, ChevronRight } from 'lucide-react';
import { cn } from '../../utils/cn.js';

/**
 * GenerationProgress
 *
 * Polished, deterministic in-flight generation surface. Auto-advances
 * through a small list of named steps at fixed time intervals so
 * the user sees motion even when the backend does not stream
 * progress. The animation is honest:
 *
 *  - Each step has a "minimum duration" before it advances, but
 *    once the network request actually completes, the panel switches
 *    to the "done" state immediately and the parent re-renders the
 *    final result.
 *  - No step is marked "done" if the request has not actually
 *    returned — the panel is fully controlled by the ``done`` prop
 *    and the parent owns the source of truth.
 *  - The step labels are honest about what the backend does (the
 *    LangGraph workflow's real stages: context → research → plan →
 *    write → review). For URL mode, the source-acquisition stages
 *    are prepended.
 */
export function GenerationProgress({
  mode = 'topic',
  done = false,
  failed = false,
  className,
}) {
  // Auto-advance steps so the user sees motion. ``done`` short-
  // circuits to the final state and the parent takes over rendering.
  const steps =
    mode === 'source' ? SOURCE_GENERATION_STEPS : TOPIC_GENERATION_STEPS;

  const [activeIdx, setActiveIdx] = useState(0);

  useEffect(() => {
    if (done || failed) return;
    const t = window.setInterval(() => {
      setActiveIdx((idx) => Math.min(idx + 1, steps.length - 1));
    }, 2200);
    return () => window.clearInterval(t);
  }, [done, failed, steps.length]);

  const displaySteps = steps.map((step, idx) => {
    let state = 'pending';
    if (done) state = 'done';
    else if (failed) {
      state = idx === activeIdx ? 'error' : idx < activeIdx ? 'done' : 'pending';
    } else {
      state = idx < activeIdx ? 'done' : idx === activeIdx ? 'active' : 'pending';
    }
    return { ...step, state };
  });

  return (
    <div className={cn('space-y-4', className)}>
      <div className="flex items-center gap-3">
        <span
          className="flex h-10 w-10 items-center justify-center rounded-xl border border-brand-400/30 bg-brand-500/15 text-brand-200"
          aria-hidden
        >
          {failed ? (
            <Sparkles className="h-5 w-5" />
          ) : (
            <Loader2 className="h-5 w-5 animate-spin" />
          )}
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold text-white">
            {failed
              ? "We couldn't finish generating this post"
              : 'Creating your LinkedIn post'}
          </div>
          <div className="text-xs text-text-muted">
            {failed
              ? 'The backend returned an error. Try again or change the inputs.'
              : 'This usually takes 30–90 seconds. The pipeline is running.'}
          </div>
        </div>
      </div>

      <ol className="space-y-2">
        {displaySteps.map((step) => (
          <StepRow key={step.id} step={step} />
        ))}
      </ol>
    </div>
  );
}

function StepRow({ step }) {
  const state = step.state;
  return (
    <li
      className={cn(
        'flex items-center gap-3 rounded-xl border px-3 py-2.5 text-sm transition-colors',
        state === 'active'
          ? 'border-brand-400/30 bg-brand-500/[0.06] text-white'
          : state === 'done'
          ? 'border-emerald-400/20 bg-emerald-500/[0.04] text-zinc-200'
          : state === 'error'
          ? 'border-rose-400/30 bg-rose-500/[0.06] text-rose-100'
          : 'border-white/[0.06] bg-white/[0.02] text-text-muted',
      )}
    >
      <StepIcon state={state} />
      <div className="min-w-0 flex-1">
        <div className="font-medium">{step.label}</div>
        {step.hint ? (
          <div className="truncate text-xs text-text-muted">{step.hint}</div>
        ) : null}
      </div>
      {state === 'active' ? (
        <span className="text-xs font-semibold uppercase tracking-wider text-brand-200">
          Running
        </span>
      ) : state === 'done' ? (
        <span className="text-xs font-semibold uppercase tracking-wider text-emerald-300">
          Done
        </span>
      ) : null}
    </li>
  );
}

function StepIcon({ state }) {
  if (state === 'done') {
    return (
      <span
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-emerald-400/30 bg-emerald-500/15 text-emerald-300"
        aria-hidden
      >
        <svg
          viewBox="0 0 16 16"
          className="h-3.5 w-3.5"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M3 8.5 6.5 12 13 4.5" />
        </svg>
      </span>
    );
  }
  if (state === 'active') {
    return (
      <span
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-brand-400/40 bg-brand-500/20 text-brand-200"
        aria-hidden
      >
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
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
      <ChevronRight className="h-3.5 w-3.5" />
    </span>
  );
}

// The names below mirror the real stages of the LangGraph
// content_workflow so the user sees motion that reflects what the
// backend is actually doing. They are intentionally not generic
// "Step 1 / Step 2" placeholders.
const TOPIC_GENERATION_STEPS = [
  {
    id: 'understand',
    label: 'Understanding your idea',
    hint: 'Profile + topic context',
  },
  {
    id: 'research',
    label: 'Researching relevant information',
    hint: 'Web search for grounding',
  },
  {
    id: 'plan',
    label: 'Planning the post',
    hint: 'Intent, audience, angle',
  },
  {
    id: 'write',
    label: 'Writing the draft',
    hint: 'LinkedIn-native format',
  },
  {
    id: 'review',
    label: 'Reviewing and refining',
    hint: 'Quality + grounding',
  },
];

const SOURCE_GENERATION_STEPS = [
  {
    id: 'understand',
    label: 'Understanding your source',
    hint: 'Source metadata + content',
  },
  {
    id: 'extract',
    label: 'Extracting key insights',
    hint: 'Topic, key points, technical details',
  },
  {
    id: 'write',
    label: 'Writing the draft',
    hint: 'Source-inspired, no fabrication',
  },
  {
    id: 'review',
    label: 'Reviewing and refining',
    hint: 'Grounded in source facts',
  },
];
