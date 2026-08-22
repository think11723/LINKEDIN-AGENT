import { Github, Globe, BookOpen, Rocket, ExternalLink, FileText, CheckCircle2, Tag } from 'lucide-react';
import { cn } from '../../utils/cn.js';
import { Badge } from './Badge.jsx';
import { SOURCE_TYPE_LABEL } from '../../utils/design.js';

const ICON_BY_TYPE = {
  github_repository: Github,
  github_readme: Github,
  blog_article: FileText,
  documentation: BookOpen,
  product_page: Rocket,
  generic_webpage: Globe,
};

function hostOf(url) {
  if (!url) return '';
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return '';
  }
}

/**
 * Compact, polished "Source found" card. Used by the Create Post
 * source-mode flow and the Draft Viewer source attribution section.
 * Renders only safe metadata (title, summary, key facts, URL) — no
 * raw HTML / README bodies / credentials.
 */
export function SourcePreviewCard({
  sourceType,
  title,
  description,
  summary,
  keyFacts = [],
  url,
  finalUrl,
  compact = false,
  className,
}) {
  const Icon = ICON_BY_TYPE[sourceType] ?? Globe;
  const label = SOURCE_TYPE_LABEL[sourceType] || 'Source';
  const safeUrl = finalUrl || url || '';
  const host = hostOf(safeUrl);
  const displaySummary = description || summary || '';

  return (
    <div
      className={cn(
        'panel-elevated relative overflow-hidden',
        compact ? 'p-4' : 'p-5 sm:p-6',
        className,
      )}
    >
      <div
        className="pointer-events-none absolute inset-0 opacity-60"
        aria-hidden
        style={{
          background:
            'radial-gradient(ellipse 60% 40% at 0% 0%, rgba(139, 92, 246, 0.10), transparent 60%)',
        }}
      />
      <div className="relative">
        <div className="flex items-center justify-between gap-3">
          <div className="inline-flex items-center gap-2 text-emerald-300">
            <CheckCircle2 className="h-4 w-4" />
            <span className="text-xs font-semibold uppercase tracking-wider">
              Source found
            </span>
          </div>
          <Badge tone="brand" size="sm">
            <Icon className="h-3 w-3" /> {label}
          </Badge>
        </div>

        {title ? (
          <div
            className={cn(
              'mt-3 font-semibold tracking-tight text-white',
              compact ? 'text-base' : 'text-lg sm:text-xl',
            )}
          >
            {title}
          </div>
        ) : null}

        {displaySummary ? (
          <p
            className={cn(
              'mt-1 text-text-secondary',
              compact ? 'text-sm' : 'text-sm sm:text-base',
            )}
          >
            {displaySummary}
          </p>
        ) : null}

        {keyFacts && keyFacts.length > 0 ? (
          <ul className="mt-3 space-y-1.5 text-sm text-zinc-200">
            {keyFacts.slice(0, compact ? 3 : 5).map((fact, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-brand-400" />
                <span className="text-text-secondary">{fact}</span>
              </li>
            ))}
          </ul>
        ) : null}

        {safeUrl ? (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-text-muted">
            {host ? (
              <span className="inline-flex items-center gap-1 rounded-md border border-white/10 bg-white/[0.03] px-2 py-1">
                <Globe className="h-3 w-3" /> {host}
              </span>
            ) : null}
            <a
              href={safeUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-text-secondary transition hover:border-white/20 hover:text-zinc-100"
            >
              <ExternalLink className="h-3 w-3" />
              <span className="max-w-[20rem] truncate">{safeUrl}</span>
            </a>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function sourceIconForType(sourceType) {
  const Icon = ICON_BY_TYPE[sourceType] ?? Globe;
  return <Icon className="h-3.5 w-3.5" />;
}

export function SourceTypeChip({ sourceType, className }) {
  const label = SOURCE_TYPE_LABEL[sourceType] || 'Source';
  return (
    <span className={cn('inline-flex items-center gap-1', className)}>
      {sourceIconForType(sourceType)}
      {label}
    </span>
  );
}
