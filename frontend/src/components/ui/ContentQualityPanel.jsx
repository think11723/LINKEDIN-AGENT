import { CheckCircle2, AlertCircle, Sparkles } from 'lucide-react';
import { cn } from '../../utils/cn.js';

/**
 * ContentQualityPanel
 *
 * Renders a compact "Content Quality" card that surfaces the
 * reviewer scores returned by the backend
 * (``GenerateContentResponse.review_scores``) and the
 * dimensionality of the review. NEVER fabricates a score or
 * dimension: if the backend did not return a value, the panel
 * renders nothing for that dimension.
 *
 * The checklist view below the score grid is a deterministic
 * projection of the score thresholds and dimensional evaluation
 * (e.g. ``hashtag_relevance.score >= 7`` → "Hashtag quality ✓").
 * It only renders a row when the underlying dimension is present
 * in the response; missing dimensions are not invented.
 */
export function ContentQualityPanel({ reviewScores, className }) {
  if (!reviewScores || typeof reviewScores !== 'object') return null;

  const overall = pickScore(reviewScores.overall);
  const dimensions = [
    { key: 'hook_strength', label: 'Hook', desc: 'Strong opening line' },
    { key: 'logical_flow', label: 'Structure', desc: 'Logical flow' },
    { key: 'professional_tone', label: 'Tone', desc: 'Professional tone' },
    { key: 'educational_value', label: 'Value', desc: 'Educational value' },
    { key: 'credibility', label: 'Credibility', desc: 'Authentic voice' },
    { key: 'cta_quality', label: 'CTA', desc: 'Call to action' },
    { key: 'hashtag_relevance', label: 'Hashtags', desc: 'Relevant hashtags' },
    { key: 'grounding', label: 'Source grounding', desc: 'Supported by source' },
  ];

  const rows = dimensions
    .map((dim) => {
      const score = pickDimensionScore(reviewScores[dim.key]);
      if (score === null) return null;
      return { ...dim, score };
    })
    .filter(Boolean);

  // If no dimensions and no overall, nothing to show.
  if (rows.length === 0 && overall === null) return null;

  return (
    <div
      className={cn(
        'panel-inset space-y-4 p-4 sm:p-5',
        className,
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">
            Content Quality
          </div>
          <div className="mt-0.5 text-sm text-text-secondary">
            Reviewer evaluation
          </div>
        </div>
        {overall !== null ? <ScoreBadge score={overall} /> : null}
      </div>

      {rows.length > 0 ? (
        <ul className="grid gap-2 sm:grid-cols-2">
          {rows.map((row) => (
            <li
              key={row.key}
              className={cn(
                'flex items-center justify-between gap-3 rounded-lg border px-3 py-2',
                row.score >= 7
                  ? 'border-emerald-400/20 bg-emerald-500/[0.06]'
                  : row.score >= 5
                  ? 'border-amber-400/20 bg-amber-500/[0.06]'
                  : 'border-rose-400/20 bg-rose-500/[0.06]',
              )}
            >
              <div className="min-w-0">
                <div className="text-sm font-medium text-zinc-100">{row.label}</div>
                <div className="truncate text-xs text-text-muted">{row.desc}</div>
              </div>
              <div
                className={cn(
                  'shrink-0 text-sm font-semibold tabular-nums',
                  row.score >= 7
                    ? 'text-emerald-300'
                    : row.score >= 5
                    ? 'text-amber-300'
                    : 'text-rose-300',
                )}
              >
                {row.score}/10
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function ScoreBadge({ score }) {
  let tone = 'neutral';
  let label = 'Score';
  let chip = 'bg-white/[0.04] border-white/10 text-zinc-300';
  if (score >= 8) {
    tone = 'success';
    label = 'Strong';
    chip = 'border-emerald-400/30 bg-emerald-500/15 text-emerald-200';
  } else if (score >= 6) {
    tone = 'warning';
    label = 'Good';
    chip = 'border-amber-400/30 bg-amber-500/15 text-amber-200';
  } else if (score > 0) {
    tone = 'danger';
    label = 'Needs work';
    chip = 'border-rose-400/30 bg-rose-500/15 text-rose-200';
  }
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold',
        chip,
      )}
    >
      {tone === 'success' ? (
        <CheckCircle2 className="h-3.5 w-3.5" />
      ) : tone === 'warning' ? (
        <Sparkles className="h-3.5 w-3.5" />
      ) : tone === 'danger' ? (
        <AlertCircle className="h-3.5 w-3.5" />
      ) : null}
      <span className="tabular-nums">{score}/10</span>
      <span className="text-text-muted">·</span>
      <span>{label}</span>
    </span>
  );
}

function pickScore(value) {
  if (value === null || value === undefined) return null;
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return Math.max(0, Math.min(10, Math.round(n)));
}

function pickDimensionScore(value) {
  // The backend may return either a plain number or a
  // ``DimensionScore`` dict with ``score``/``explanation`` keys.
  if (value === null || value === undefined) return null;
  if (typeof value === 'object' && 'score' in value) {
    return pickScore(value.score);
  }
  return pickScore(value);
}
