import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowRight, Search, Trash2, NotebookPen, ChevronLeft, ChevronRight, Sparkles } from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useAuth } from '../context/AuthContext.jsx';
import { useDrafts } from '../context/DraftsContext.jsx';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Select, Field } from '../components/ui/Input.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { PageHeader } from '../components/ui/PageHeader.jsx';
import { ConfirmDialog } from '../components/ConfirmDialog.jsx';
import { EmptyState, ErrorBanner, Skeleton } from '../components/ui/Feedback.jsx';
import { formatDateTime } from '../utils/date.js';
import { DRAFT_STATUS_TONE, DRAFT_STATUS_LABEL, SOURCE_TONE, SOURCE_TYPE_LABEL } from '../utils/design.js';
import { SourceTypeChip } from '../components/ui/SourcePreviewCard.jsx';

const PAGE_SIZE = 10;

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
  const { status: authStatus } = useAuth();
  const { setDrafts, drafts, setCurrentDraft, deleteDraft } = useDrafts();
  const { toast } = useToast();

  const [search, setSearch] = useState(() => searchParams.get('search') || '');
  const [statusFilter, setStatusFilter] = useState('all');
  const [sortBy, setSortBy] = useState('updated');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [nextPage, setNextPage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [confirmId, setConfirmId] = useState(null);

  const load = useCallback(async () => {
    if (authStatus !== 'authenticated') return;
    setLoading(true);
    try {
      const params = { page, page_size: PAGE_SIZE, sort_by: sortBy };
      if (statusFilter !== 'all') params.status = statusFilter;
      if (search.trim()) params.search = search.trim();
      const data = await api.listDrafts(params);
      const items = Array.isArray(data?.items) ? data.items : [];
      setDrafts(items);
      setTotal(data?.total ?? 0);
      setNextPage(data?.next_page ?? null);
      setError(null);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [api, authStatus, search, statusFilter, page, sortBy, setDrafts]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setPage(1);
  }, [search, statusFilter, sortBy]);

  const pageItems = drafts;

  async function handleDelete() {
    if (!confirmId) return;
    setDeletingId(confirmId);
    try {
      await api.deleteDraft(confirmId);
      deleteDraft(confirmId);
      toast.success('Draft deleted.');
      setConfirmId(null);
      await load();
    } catch (err) {
      toast.error('Delete failed', err?.message);
    } finally {
      setDeletingId(null);
    }
  }

  function handleOpen(id) {
    setCurrentDraft(id);
    navigate(`/drafts/${id}`);
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6 animate-fadeIn">
      <PageHeader
        eyebrow="Workspace"
        title="Draft Library"
        subtitle="Search, filter, edit, and publish your drafts."
        actions={
          <Button
            variant="brand"
            size="md"
            onClick={() => navigate('/create')}
            rightIcon={<ArrowRight className="h-4 w-4" />}
          >
            Generate new draft
          </Button>
        }
      />

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle>Filters</CardTitle>
              <CardDescription>
                {loading ? 'Loading drafts…' : `Showing ${total} draft${total === 1 ? '' : 's'}.`}
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-[1fr_180px_180px]">
            <Field id="drafts-search" label="Search">
              <Input
                id="drafts-search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search drafts"
                leftIcon={<Search className="h-3.5 w-3.5" />}
              />
            </Field>
            <Field id="drafts-status" label="Status">
              <Select
                id="drafts-status"
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
              >
                {STATUS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </Field>
            <Field id="drafts-sort" label="Sort">
              <Select
                id="drafts-sort"
                value={sortBy}
                onChange={(event) => setSortBy(event.target.value)}
              >
                {SORT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
        </CardContent>
      </Card>

      <ErrorBanner error={error} onRetry={load} />

      {loading && !pageItems.length ? (
        <div className="grid gap-3 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, idx) => (
            <Skeleton key={idx} className="h-44" />
          ))}
        </div>
      ) : pageItems.length ? (
        <div className="grid gap-3 md:grid-cols-2">
          {pageItems.map((draft) => (
            <DraftCard
              key={draft.id}
              draft={draft}
              onOpen={() => handleOpen(draft.id)}
              onDelete={() => setConfirmId(draft.id)}
            />
          ))}
        </div>
      ) : (
        <Card>
          <CardContent>
            <EmptyState
              icon={<NotebookPen className="h-5 w-5" />}
              title="No drafts yet"
              description="Create your first LinkedIn post from a topic or a public URL."
              action={
                <Button
                  variant="brand"
                  size="md"
                  onClick={() => navigate('/create')}
                  leftIcon={<Sparkles className="h-4 w-4" />}
                >
                  Create Post
                </Button>
              }
            />
          </CardContent>
        </Card>
      )}

      {totalPages > 1 ? (
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm text-text-muted">
            Page {page} of {totalPages}
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={page === 1}
              onClick={() => setPage((current) => Math.max(1, current - 1))}
              leftIcon={<ChevronLeft className="h-3.5 w-3.5" />}
            >
              Previous
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={nextPage === null}
              onClick={() => setPage((current) => current + 1)}
              rightIcon={<ChevronRight className="h-3.5 w-3.5" />}
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
        confirming={Boolean(deletingId)}
        onConfirm={handleDelete}
        onCancel={() => setConfirmId(null)}
      />
    </div>
  );
}

function DraftCard({ draft, onOpen, onDelete }) {
  const status = draft.status || 'draft';
  const statusTone = DRAFT_STATUS_TONE[status] || DRAFT_STATUS_TONE.draft;
  const sourceType = draft.source_metadata?.source_type;
  const sourceMeta = draft.source_metadata || {};
  const sourceLabel = sourceType ? SOURCE_TYPE_LABEL[sourceType] : null;
  const sourceSummary =
    sourceMeta.description ||
    sourceMeta.readme_summary ||
    sourceMeta.summary ||
    '';
  const preview = (draft.content || '').slice(0, 200).replace(/\s+/g, ' ').trim();

  return (
    <div className="panel group flex h-full flex-col gap-3 p-4 transition hover:border-white/20">
      <div className="flex items-start gap-3">
        <button
          type="button"
          onClick={onOpen}
          className="min-w-0 flex-1 text-left"
        >
          <div className="flex items-start gap-2">
            <h3 className="line-clamp-2 text-base font-semibold tracking-tight text-white group-hover:text-brand-200">
              {draft.title || 'Untitled draft'}
            </h3>
          </div>
          {draft.topic ? (
            <div className="mt-0.5 line-clamp-1 text-xs text-text-muted">
              {draft.topic}
            </div>
          ) : null}
        </button>
        <Badge tone={statusTone.label.toLowerCase()} size="sm" withDot>
          {DRAFT_STATUS_LABEL[status] || status}
        </Badge>
      </div>

      {preview ? (
        <p className="line-clamp-3 text-sm text-text-secondary">
          {preview}
          {draft.content && draft.content.length > 200 ? '…' : ''}
        </p>
      ) : (
        <p className="text-sm italic text-text-muted">No content yet.</p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {sourceLabel ? (
          <Badge tone={(SOURCE_TONE[sourceType] || {}).label?.toLowerCase() || 'brand'} size="sm">
            <SourceTypeChip sourceType={sourceType} />
          </Badge>
        ) : null}
        {typeof draft.reviewScore === 'number' ? (
          <Badge tone={draft.reviewScore >= 7 ? 'success' : 'warning'} size="sm">
            Score {draft.reviewScore}/10
          </Badge>
        ) : null}
      </div>

      {sourceSummary && sourceType ? (
        <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-2 text-xs text-text-secondary">
          {sourceSummary.slice(0, 140)}
          {sourceSummary.length > 140 ? '…' : ''}
        </div>
      ) : null}

      <div className="mt-auto flex items-center justify-between gap-2 border-t border-white/[0.06] pt-3 text-xs text-text-muted">
        <span>
          Updated {formatDateTime(draft.updatedAt || draft.updated_at)}
        </span>
        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant="ghost"
            onClick={onDelete}
            aria-label="Delete draft"
            className="h-8 w-8 p-0 text-text-muted hover:text-rose-300"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={onOpen}
            rightIcon={<ArrowRight className="h-3.5 w-3.5" />}
          >
            Open
          </Button>
        </div>
      </div>
    </div>
  );
}
