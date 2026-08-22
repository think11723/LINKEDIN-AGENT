import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowRight,
  Search,
  Trash2,
  NotebookPen,
  LayoutGrid,
  List,
  Plus,
  Sparkles,
  CalendarClock,
  Inbox,
} from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useDrafts } from '../context/DraftsContext.jsx';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Select } from '../components/ui/Input.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { ConfirmDialog } from '../components/ConfirmDialog.jsx';
import { EmptyState, ErrorBanner, Skeleton, Spinner } from '../components/ui/Feedback.jsx';
import { MotionPage } from '../components/ui/MotionPage.jsx';
import { DRAFT_STATUS_TONE, DRAFT_STATUS_LABEL, SOURCE_TONE } from '../utils/design.js';
import { formatDateTime } from '../utils/date.js';
import { cn } from '../utils/cn.js';

const PAGE_SIZE = 12;

const STATUS_OPTIONS = [
  { value: 'all', label: 'All statuses' },
  { value: 'draft', label: 'Draft' },
  { value: 'approved', label: 'Approved' },
  { value: 'published', label: 'Published' },
];

const SORT_OPTIONS = [
  { value: 'updated', label: 'Last updated' },
  { value: 'created', label: 'Created' },
  { value: 'title', label: 'Title (A→Z)' },
];

export default function DraftsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const api = useApi();
  const { setDrafts, drafts, deleteDraft } = useDrafts();
  const { toast } = useToast();

  const [search, setSearch] = useState(() => searchParams.get('search') || '');
  const [statusFilter, setStatusFilter] = useState('all');
  const [sortBy, setSortBy] = useState('updated');
  const [view, setView] = useState('grid');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [nextPage, setNextPage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);
  const [confirmId, setConfirmId] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, page_size: PAGE_SIZE, sort_by: sortBy };
      if (statusFilter !== 'all') params.status = statusFilter;
      if (search.trim()) params.search = search.trim();
      const data = await api.listDrafts(params);
      setDrafts(Array.isArray(data?.items) ? data.items : []);
      setTotal(data?.total ?? 0);
      setNextPage(data?.next_page ?? null);
      setErr(null);
    } catch (e) {
      setErr(e);
    } finally {
      setLoading(false);
    }
  }, [api, search, statusFilter, page, sortBy, setDrafts]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setPage(1);
  }, [search, statusFilter, sortBy]);

  async function handleDelete() {
    if (!confirmId) return;
    setDeleting(true);
    try {
      await api.deleteDraft(confirmId);
      deleteDraft(confirmId);
      toast.success('Draft deleted.');
      setConfirmId(null);
      await load();
    } catch (e) {
      toast.error('Delete failed', e?.message);
    } finally {
      setDeleting(false);
      setConfirmId(null);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const pageItems = drafts;

  return (
    <MotionPage className="space-y-6 p-4 md:p-6 lg:p-8">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-text-secondary">
            <NotebookPen className="h-3 w-3 text-brand-300" />
            Draft Library
          </div>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            <span className="text-text-secondary">Your</span>{' '}
            <span className="gradient-text">drafts</span>
          </h1>
          <p className="mt-1 text-sm text-text-secondary">
            {loading && total === 0
              ? 'Loading your drafts…'
              : `${total} draft${total === 1 ? '' : 's'} in your library`}
          </p>
        </div>
        <Button
          variant="brand"
          size="md"
          onClick={() => navigate('/create')}
          leftIcon={<Plus className="h-4 w-4" />}
        >
          New Draft
        </Button>
      </header>

      <ErrorBanner error={err} onRetry={load} />

      <Card>
        <CardContent className="flex flex-col gap-3 lg:flex-row lg:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted" />
            <Input
              className="pl-9 h-10"
              placeholder="Search drafts by title, topic, or content…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search drafts"
            />
          </div>
          <Select
            className="lg:w-44"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            aria-label="Filter by status"
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
          <Select
            className="lg:w-44"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            aria-label="Sort drafts"
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </Select>
          <div className="glass-inset inline-flex items-center gap-1 rounded-2xl p-1">
            <ViewToggle
              active={view === 'grid'}
              onClick={() => setView('grid')}
              icon={<LayoutGrid className="h-4 w-4" />}
              label="Grid"
            />
            <ViewToggle
              active={view === 'list'}
              onClick={() => setView('list')}
              icon={<List className="h-4 w-4" />}
              label="List"
            />
          </div>
        </CardContent>
      </Card>

      {loading && pageItems.length === 0 ? (
        <div
          className={cn(
            'grid gap-4',
            view === 'grid'
              ? 'sm:grid-cols-2 lg:grid-cols-3'
              : 'grid-cols-1'
          )}
        >
          {Array.from({ length: 6 }).map((_, idx) => (
            <Skeleton key={idx} className="h-44" />
          ))}
        </div>
      ) : pageItems.length === 0 ? (
        <EmptyState
          icon={<Inbox className="h-5 w-5" />}
          title="No drafts match"
          description="Generate a new draft or clear your filters."
          action={
            <Button
              variant="brand"
              size="sm"
              onClick={() => navigate('/create')}
              leftIcon={<Sparkles className="h-4 w-4" />}
            >
              Create a draft
            </Button>
          }
        />
      ) : (
        <AnimatePresence mode="popLayout">
          <motion.div
            key={`${view}-${page}-${sortBy}-${statusFilter}-${search}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.24 }}
            className={cn(
              'grid gap-4',
              view === 'grid'
                ? 'sm:grid-cols-2 lg:grid-cols-3'
                : 'grid-cols-1'
            )}
          >
            {pageItems.map((draft, idx) => (
              <DraftCard
                key={draft.id}
                draft={draft}
                view={view}
                index={idx}
                onOpen={() => navigate(`/drafts/${draft.id}`)}
                onDelete={() => setConfirmId(draft.id)}
              />
            ))}
          </motion.div>
        </AnimatePresence>
      )}

      {totalPages > 1 ? (
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm text-text-muted">
            Page {page} of {totalPages}
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={page === 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              Previous
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={nextPage === null}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </Button>
          </div>
        </div>
      ) : null}

      <ConfirmDialog
        open={Boolean(confirmId)}
        title="Delete this draft?"
        description="The draft and its history will be removed. This cannot be undone."
        confirmLabel="Delete"
        danger
        confirming={deleting}
        onConfirm={handleDelete}
        onCancel={() => setConfirmId(null)}
      />
    </MotionPage>
  );
}

function Boolean(value) {
  return Boolean(value);
}

function ViewToggle({ active, onClick, icon, label }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      title={label}
      className={cn(
        'inline-flex h-8 w-8 items-center justify-center rounded-lg text-text-muted transition',
        active
          ? 'bg-white/[0.08] text-zinc-100 shadow-sm'
          : 'hover:bg-white/[0.04] hover:text-zinc-200'
      )}
    >
      {icon}
    </button>
  );
}

function DraftCard({ draft, view, index, onOpen, onDelete }) {
  const status = draft.status || 'draft';
  const statusTone = DRAFT_STATUS_TONE[status] || DRAFT_STATUS_TONE.draft;
  const sourceType = draft.source_metadata?.source_type;
  const sourceTone = sourceType ? SOURCE_TONE[sourceType] : null;
  const preview = (draft.content || '').slice(0, 200).replace(/\s+/g, ' ').trim();
  const wordCount = (draft.content || '').split(/\s+/).filter(Boolean).length;

  return (
    <motion.article
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.025, duration: 0.22 }}
      whileHover={{ y: -2 }}
      className={
        'glass-card group relative flex cursor-pointer flex-col gap-3 p-5 transition hover:border-white/[0.18] hover:bg-white/[0.04] ' +
        (view === 'list' ? 'sm:flex-row sm:items-center' : '')
      }
      onClick={onOpen}
    >
      <div className="absolute -right-10 -top-10 h-32 w-32 rounded-full bg-gradient-brand-soft opacity-60 blur-3xl transition group-hover:opacity-100" />
      <div className="relative flex flex-1 flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={statusTone.label.toLowerCase()} size="sm" withDot>
            {DRAFT_STATUS_LABEL[status] || status}
          </Badge>
          {sourceTone ? (
            <Badge tone={sourceTone.label.toLowerCase()} size="sm">
              {sourceTone.label}
            </Badge>
          ) : null}
        </div>
        <h3 className="line-clamp-2 text-base font-semibold tracking-tight text-white group-hover:text-white">
          {draft.title || 'Untitled draft'}
        </h3>
        {preview ? (
          <p className="line-clamp-3 text-sm leading-relaxed text-text-secondary">
            {preview}
            {(draft.content || '').length > 200 ? '…' : ''}
          </p>
        ) : (
          <p className="text-sm italic text-text-muted">No content yet.</p>
        )}
        <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-text-muted">
          <span className="inline-flex items-center gap-1">
            <CalendarClock className="h-3 w-3" />
            {formatDateTime(draft.updatedAt || draft.updated_at)}
          </span>
          {wordCount > 0 ? (
            <span className="inline-flex items-center gap-1">
              {wordCount} words
            </span>
          ) : null}
        </div>
      </div>
      <div
        className={
          'relative flex items-center gap-2 ' +
          (view === 'list' ? 'shrink-0' : 'justify-end')
        }
        onClick={(e) => e.stopPropagation()}
      >
        <Button
          variant="primary"
          size="sm"
          onClick={onOpen}
          rightIcon={<ArrowRight className="h-3.5 w-3.5" />}
        >
          Open
        </Button>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onDelete}
          aria-label="Delete draft"
          className="text-text-muted hover:text-rose-300"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </motion.article>
  );
}
