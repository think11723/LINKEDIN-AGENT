import { useState } from 'react';
import {
  ArrowRight,
  RotateCcw,
  Eye,
  PencilLine,
  CheckCircle2,
} from 'lucide-react';
import { cn } from '../../utils/cn.js';
import { Button } from './Button.jsx';
import { ContentQualityPanel } from './ContentQualityPanel.jsx';
import { LinkedInPreview } from './LinkedInPreview.jsx';
import { SourcePreviewCard } from './SourcePreviewCard.jsx';
import { formatDateTime } from '../../utils/date.js';

/**
 * GenerationResultCard
 *
 * The polished "your post is ready" surface. Composes:
 *
 *   1. A short "Your LinkedIn post is ready" header with metadata
 *      (iterations, last-edited timestamp).
 *   2. The LinkedInPreview (the actual post that will be published).
 *   3. The SourcePreviewCard (only when a source was used).
 *   4. The ContentQualityPanel (only when the backend returned
 *      reviewer scores).
 *   5. Three actions: Open Draft (primary), Generate Again
 *      (secondary), Edit (secondary).
 *
 * The component does NOT auto-publish — the existing approval
 * workflow remains the authority for publishing.
 */
export function GenerationResultCard({
  result,
  onOpen,
  onRegenerate,
  onEdit,
  regenerating = false,
  className,
}) {
  const [showEditHint, setShowEditHint] = useState(false);
  if (!result) return null;

  const post = result.final_post || {};
  const sourceUrl = result.source_url;
  const sourceMeta = result.source_metadata || {};
  const reviewScores = result.review_scores || null;
  const iterations = result.iterations;

  return (
    <div className={cn('space-y-4 animate-fadeIn', className)}>
      {/* Header */}
      <div className="flex items-center gap-3">
        <span
          className="flex h-10 w-10 items-center justify-center rounded-xl border border-emerald-400/30 bg-emerald-500/15 text-emerald-300"
          aria-hidden
        >
          <CheckCircle2 className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold text-white">
            Your LinkedIn post is ready
          </div>
          <div className="text-xs text-text-muted">
            Review the preview, then approve & publish from the draft viewer.
            {iterations
              ? ` · ${iterations} iteration${iterations === 1 ? '' : 's'}`
              : null}
          </div>
        </div>
      </div>

      {/* LinkedIn preview (canonical, normalized content) */}
      <LinkedInPreview
        authorName="You"
        authorHeadline="on LinkedIn"
        content={post.content}
        hashtags={post.hashtags || []}
        sourceAttribution={
          sourceUrl
            ? {
                label: sourceMeta.source_type
                  ? prettySourceType(sourceMeta.source_type)
                  : 'Source',
                title:
                  sourceMeta.full_name ||
                  sourceMeta.title ||
                  sourceMeta.description ||
                  '',
                url: sourceMeta.canonical_url || sourceUrl,
              }
            : null
        }
      />

      {/* Source attribution (URL mode only) */}
      {sourceUrl ? (
        <SourcePreviewCard
          compact
          sourceType={sourceMeta.source_type || 'generic_webpage'}
          title={
            sourceMeta.full_name ||
            sourceMeta.title ||
            sourceMeta.description ||
            'Source'
          }
          description={sourceMeta.description || ''}
          summary={sourceMeta.summary || ''}
          url={sourceUrl}
          finalUrl={sourceMeta.canonical_url || sourceUrl}
        />
      ) : null}

      {/* Reviewer feedback (when present, short) */}
      {result.review_feedback ? (
        <div className="panel-inset p-3 text-sm text-text-secondary">
          <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">
            Reviewer note
          </div>
          <div className="mt-1 text-text-secondary">
            {result.review_feedback}
          </div>
        </div>
      ) : null}

      {/* Quality panel (only when backend returned reviewer scores) */}
      <ContentQualityPanel reviewScores={reviewScores} />

      {/* Actions */}
      <div className="flex flex-wrap items-center gap-2 pt-1">
        <Button
          variant="brand"
          size="md"
          onClick={onOpen}
          rightIcon={<ArrowRight className="h-4 w-4" />}
        >
          Review Draft
        </Button>
        {onRegenerate ? (
          <Button
            variant="secondary"
            size="md"
            onClick={onRegenerate}
            loading={regenerating}
            leftIcon={!regenerating ? <RotateCcw className="h-3.5 w-3.5" /> : null}
          >
            {regenerating ? 'Regenerating…' : 'Generate Again'}
          </Button>
        ) : null}
        {onEdit ? (
          <Button
            variant="ghost"
            size="md"
            onClick={() => {
              setShowEditHint(true);
              onEdit();
            }}
            leftIcon={<PencilLine className="h-3.5 w-3.5" />}
          >
            Edit
          </Button>
        ) : null}
      </div>
      {showEditHint ? (
        <p className="text-xs text-text-muted">
          Opening the draft viewer where you can edit before approval…
        </p>
      ) : null}
    </div>
  );
}

function prettySourceType(sourceType) {
  const labels = {
    github_repository: 'GitHub Repository',
    github_readme: 'GitHub README',
    blog_article: 'Blog Article',
    documentation: 'Documentation',
    product_page: 'Product Announcement',
    generic_webpage: 'Web Article',
  };
  return labels[sourceType] || 'Source';
}
