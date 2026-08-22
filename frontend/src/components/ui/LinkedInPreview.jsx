import { cn } from '../../utils/cn.js';
import { Globe, MoreHorizontal, ThumbsUp, MessageCircle, Repeat2, Send, Bookmark, BadgeCheck } from 'lucide-react';

/**
 * Tasteful approximation of a LinkedIn feed post. NOT a clone of
 * LinkedIn's proprietary UI — just a clean card with author,
 * content, hashtags, and engagement icons. Renders the canonical
 * normalized post (plain text with paragraph breaks + emoji +
 * Unicode bullets). NEVER renders markdown.
 */
export function LinkedInPreview({
  authorName = 'You',
  authorHeadline = 'on LinkedIn',
  authorAvatar,
  content = '',
  hashtags = [],
  sourceAttribution = null,
  className,
}) {
  const contentParagraphs = (content || '').split(/\n{2,}/).filter(Boolean);
  return (
    <div
      className={cn(
        'overflow-hidden rounded-2xl border border-white/10 bg-[#0f1115] shadow-panel-lg',
        className,
      )}
    >
      <div className="p-5 sm:p-6">
        <header className="flex items-start gap-3">
          {authorAvatar ? (
            <img
              src={authorAvatar}
              alt=""
              className="h-12 w-12 shrink-0 rounded-full object-cover"
            />
          ) : (
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-base font-semibold text-white">
              {(authorName || 'Y').charAt(0).toUpperCase()}
            </div>
          )}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <span className="truncate text-sm font-semibold text-white">
                {authorName}
              </span>
              <BadgeCheck className="h-4 w-4 shrink-0 text-sky-400" />
            </div>
            <div className="truncate text-xs text-text-secondary">
              {authorHeadline}
            </div>
            <div className="mt-0.5 flex items-center gap-1 text-xs text-text-muted">
              <span>now</span>
              <span aria-hidden>•</span>
              <Globe className="h-3 w-3" />
            </div>
          </div>
          <button
            type="button"
            className="rounded-full p-1.5 text-text-muted transition hover:bg-white/5 hover:text-zinc-200"
            aria-label="More options"
          >
            <MoreHorizontal className="h-4 w-4" />
          </button>
        </header>

        <div className="mt-4 space-y-3 text-[15px] leading-relaxed text-zinc-100">
          {contentParagraphs.length > 0 ? (
            contentParagraphs.map((para, idx) => (
              <p key={idx} className="whitespace-pre-line break-words">
                {para}
              </p>
            ))
          ) : (
            <p className="text-text-muted">No content yet.</p>
          )}
        </div>

        {hashtags && hashtags.length > 0 ? (
          <div className="mt-3 flex flex-wrap gap-x-2 gap-y-1 text-sm">
            {hashtags.map((tag) => (
              <span key={tag} className="font-medium text-brand-300">
                {tag.startsWith('#') ? tag : `#${tag}`}
              </span>
            ))}
          </div>
        ) : null}

        {sourceAttribution ? (
          <div className="mt-4 rounded-xl border border-white/10 bg-white/[0.03] p-3 text-xs text-text-secondary">
            <div className="font-medium text-zinc-200">
              Inspired by · {sourceAttribution.label || 'Source'}
            </div>
            {sourceAttribution.title ? (
              <div className="mt-0.5 truncate text-text-secondary">
                {sourceAttribution.title}
              </div>
            ) : null}
            {sourceAttribution.url ? (
              <a
                href={sourceAttribution.url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-0.5 inline-block max-w-full truncate text-brand-300 hover:underline"
              >
                {sourceAttribution.url}
              </a>
            ) : null}
          </div>
        ) : null}

        <div className="mt-3 flex items-center justify-between text-xs text-text-muted">
          <span>0 reactions · 0 comments</span>
          <span>0 reposts</span>
        </div>
      </div>
      <div className="grid grid-cols-4 border-t border-white/[0.06] px-2 py-1 text-xs text-text-secondary">
        <PreviewAction Icon={ThumbsUp} label="Like" />
        <PreviewAction Icon={MessageCircle} label="Comment" />
        <PreviewAction Icon={Repeat2} label="Repost" />
        <PreviewAction Icon={Send} label="Send" />
      </div>
      <div className="flex items-center justify-between border-t border-white/[0.06] px-5 py-2 text-xs text-text-muted">
        <div className="inline-flex items-center gap-1">
          <Bookmark className="h-3.5 w-3.5" /> Save
        </div>
        <span>Visible to your network</span>
      </div>
    </div>
  );
}

function PreviewAction({ Icon, label }) {
  return (
    <button
      type="button"
      className="inline-flex items-center justify-center gap-1.5 rounded-md py-2 text-text-secondary transition hover:bg-white/[0.04] hover:text-zinc-100"
    >
      <Icon className="h-4 w-4" />
      <span className="hidden sm:inline">{label}</span>
    </button>
  );
}
