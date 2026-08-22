/**
 * Centralized design tokens — Phase 4.
 *
 * Single source of truth for the LinkedIn Agent design system.
 * Components consume these values via Tailwind utility classes that
 * resolve to the same CSS variables; this module is the JS-level
 * reference for things that must be computed at runtime (e.g. icons
 * that map to a status label).
 *
 * The visual language is a polished dark-mode SaaS aesthetic
 * (Linear / Vercel / Stripe-developer inspired):
 *   - background: #070709 with a soft top-center radial gradient
 *   - surface:    rgba(20, 20, 24, 0.72) glassy panels
 *   - border:     rgba(255, 255, 255, 0.08) — subtle, never harsh
 *   - text:       zinc-50 (primary), zinc-300 (secondary), zinc-500 (muted)
 *   - accent:     violet (brand-500 #8b5cf6)
 *   - status:     green (success), amber (warning), rose (danger), sky (info)
 *   - radius:     0.75rem (default), 1rem (lg), 1.5rem (2xl)
 *   - shadow:     soft panel shadow + 1px highlight
 */

export const ACCENT = {
  // Source types (used by the Draft Viewer / Draft Library cards).
  GITHUB: 'github_repository',
  GITHUB_README: 'github_readme',
  BLOG: 'blog_article',
  DOCS: 'documentation',
  PRODUCT: 'product_page',
  WEBPAGE: 'generic_webpage',
};

export const SOURCE_TYPE_LABEL = {
  [ACCENT.GITHUB]: 'GitHub Repository',
  [ACCENT.GITHUB_README]: 'GitHub README',
  [ACCENT.BLOG]: 'Blog Article',
  [ACCENT.DOCS]: 'Documentation',
  [ACCENT.PRODUCT]: 'Product Announcement',
  [ACCENT.WEBPAGE]: 'Web Article',
};

// Tone tokens for status badges / status pills.
export const TONE = {
  neutral: {
    label: 'neutral',
    bg: 'bg-white/[0.04]',
    border: 'border-white/10',
    text: 'text-zinc-300',
    dot: 'bg-zinc-400',
  },
  brand: {
    label: 'brand',
    bg: 'bg-brand-500/15',
    border: 'border-brand-400/30',
    text: 'text-brand-200',
    dot: 'bg-brand-400',
  },
  success: {
    label: 'success',
    bg: 'bg-emerald-500/15',
    border: 'border-emerald-400/30',
    text: 'text-emerald-300',
    dot: 'bg-emerald-400',
  },
  warning: {
    label: 'warning',
    bg: 'bg-amber-500/15',
    border: 'border-amber-400/30',
    text: 'text-amber-300',
    dot: 'bg-amber-400',
  },
  danger: {
    label: 'danger',
    bg: 'bg-rose-500/15',
    border: 'border-rose-400/30',
    text: 'text-rose-300',
    dot: 'bg-rose-400',
  },
  info: {
    label: 'info',
    bg: 'bg-sky-500/15',
    border: 'border-sky-400/30',
    text: 'text-sky-300',
    dot: 'bg-sky-400',
  },
};

export const DRAFT_STATUS_TONE = {
  draft: TONE.neutral,
  approved: TONE.brand,
  published: TONE.success,
  failed: TONE.danger,
  pending: TONE.warning,
  scheduled: TONE.info,
  expired: TONE.danger,
  queued: TONE.neutral,
  running: TONE.info,
  succeeded: TONE.success,
  cancelled: TONE.danger,
};

export const DRAFT_STATUS_LABEL = {
  draft: 'Draft',
  approved: 'Approved',
  published: 'Published',
  failed: 'Failed',
  pending: 'Pending approval',
  scheduled: 'Scheduled',
  expired: 'Expired',
  queued: 'Queued',
  running: 'Running',
  succeeded: 'Ready',
  cancelled: 'Cancelled',
};

export const SOURCE_TONE = {
  [ACCENT.GITHUB]: { ...TONE.brand, label: 'GitHub' },
  [ACCENT.GITHUB_README]: { ...TONE.brand, label: 'README' },
  [ACCENT.BLOG]: { ...TONE.info, label: 'Article' },
  [ACCENT.DOCS]: { ...TONE.success, label: 'Docs' },
  [ACCENT.PRODUCT]: { ...TONE.warning, label: 'Product' },
  [ACCENT.WEBPAGE]: { ...TONE.neutral, label: 'Web' },
};
