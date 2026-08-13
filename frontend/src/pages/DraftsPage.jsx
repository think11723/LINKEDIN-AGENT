import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowRight, Search, Trash2 } from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useAuth } from '../context/AuthContext.jsx';
import { useDrafts } from '../context/DraftsContext.jsx';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Select } from '../components/ui/Input.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { ConfirmDialog } from '../components/ConfirmDialog.jsx';
import { EmptyState, ErrorBanner, Spinner } from '../components/ui/Feedback.jsx';
import { formatDateTime } from '../utils/date.js';

const PAGE_SIZE = 10;

const STATUS_OPTIONS = [
  { value: 'all', label: 'All statuses' },
  { value: 'draft', label: 'Draft' },
  { value: 'approved', label: 'Approved' },
  { value: 'published', label: 'Published' },
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

  // Reset to page 1 whenever the user changes the search / status filter / sort.
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
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-semibold">Drafts</h1>
          <p className="text-zinc-400">Search, filter, edit, and publish your drafts.</p>
        </div>
        <Button onClick={() => navigate('/create')}>
          Generate new draft
          <ArrowRight className="h-4 w-4" />
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
          <CardDescription>Showing {total} draft{total === 1 ? '' : 's'}.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-[1fr_180px_180px]">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
              <Input
                className="pl-9"
                placeholder="Search drafts"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </div>
            <Select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
            <Select value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
              <option value="updated">Sort by updated</option>
              <option value="created">Sort by created</option>
              <option value="title">Sort by title</option>
            </Select>
          </div>
        </CardContent>
      </Card>

      <ErrorBanner error={error} onRetry={load} />

      <Card>
        <CardHeader>
          <CardTitle>Draft library</CardTitle>
          {loading ? <Spinner /> : null}
        </CardHeader>
        <CardContent>
          {pageItems.length ? (
            <div className="space-y-3">
              {pageItems.map((draft) => (
                <div key={draft.id} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div className="space-y-1">
                      <div className="text-lg font-semibold text-white">{draft.title || 'Untitled'}</div>
                      <div className="text-sm text-zinc-400">Topic: {draft.topic || '—'}</div>
                      <div className="text-xs text-zinc-500">
                        Created {formatDateTime(draft.createdAt)} · Updated {formatDateTime(draft.updatedAt)}
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Badge>{draft.status}</Badge>
                      <Badge variant="outline">Score {draft.reviewScore ?? '—'}</Badge>
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" onClick={() => handleOpen(draft.id)}>
                      Open
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setConfirmId(draft.id)}
                      loading={deletingId === draft.id}
                    >
                      <Trash2 className="h-4 w-4" /> Delete
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : loading ? null : (
            <EmptyState
              title="No drafts match"
              description="Generate a new draft or clear your filters."
              action={
                <Button size="sm" onClick={() => navigate('/create')}>
                  Generate new draft
                </Button>
              }
            />
          )}

          {totalPages > 1 ? (
            <div className="mt-4 flex items-center justify-between gap-3">
              <div className="text-sm text-zinc-400">
                Page {page} of {totalPages}
              </div>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={page === 1}
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                >
                  Previous
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={nextPage === null}
                  onClick={() => setPage((current) => current + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

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
