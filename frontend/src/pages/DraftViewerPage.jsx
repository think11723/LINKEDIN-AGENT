import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { ArrowLeft, CalendarClock, Copy, Download, Trash2, Edit3, Send } from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useDrafts } from '../context/DraftsContext.jsx';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Textarea } from '../components/ui/Input.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { ConfirmDialog } from '../components/ConfirmDialog.jsx';
import { EmptyState, ErrorBanner, Spinner } from '../components/ui/Feedback.jsx';
import { formatDateTime } from '../utils/date.js';

/**
 * Phase 8B P1 — DraftViewer with state-aware actions, Edit, Publish-now,
 * Cancel-schedule, and provider / model metadata.
 */
export default function DraftViewerPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const api = useApi();
  const { drafts, deleteDraft } = useDrafts();
  const { toast } = useToast();

  const localDraft = useMemo(() => {
    if (!id) return null;
    return drafts.find((entry) => entry.id === id) || null;
  }, [id, drafts]);

  const [serverDraft, setServerDraft] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [editing, setEditing] = useState(false);
  const [editTitle, setEditTitle] = useState('');
  const [editContent, setEditContent] = useState('');
  const [editHashtags, setEditHashtags] = useState('');
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const [scheduleTime, setScheduleTime] = useState('');
  const [scheduling, setScheduling] = useState(false);
  const [confirmScheduleCancel, setConfirmScheduleCancel] = useState(false);
  const [existingJobId, setExistingJobId] = useState(null);

  const [publishOpen, setPublishOpen] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [publishError, setPublishError] = useState(null);
  const [publishResult, setPublishResult] = useState(null);

  const draft = useMemo(() => {
    if (!id) return localDraft;
    if (localDraft && serverDraft) return { ...localDraft, ...serverDraft };
    return serverDraft || localDraft;
  }, [id, localDraft, serverDraft]);

  const loadDraft = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const data = await api.getDraft(id);
      setServerDraft(data);
      setError(null);
    } catch (err) {
      if (err?.status === 404) {
        setServerDraft(null);
        setError(null);
      } else {
        setError(err);
      }
    } finally {
      setLoading(false);
    }
  }, [api, id]);

  useEffect(() => {
    // H6 - reset transient form state when the route id changes so
    // editing another draft does not show stale form fields.
    setEditing(false);
    setScheduleTime('');
    setPublishResult(null);
    setPublishError(null);
    loadDraft();
  }, [loadDraft]);

  // Find a pending scheduled job for this draft.
  useEffect(() => {
    let cancelled = false;
    async function findJob() {
      try {
        const jobs = await api.getScheduledJobs();
        if (cancelled) return;
        const job = (Array.isArray(jobs) ? jobs : []).find(
          (j) => j.status === 'pending' && j.title === (draft?.title || ''),
        );
        setExistingJobId(job?.job_id || null);
      } catch {
        if (!cancelled) setExistingJobId(null);
      }
    }
    if (draft?.id) findJob();
    return () => {
      cancelled = true;
    };
  }, [api, draft?.id, draft?.title]);

  const isPublished = Boolean(draft?.published_at);
  const isEditing = editing;

  function startEdit() {
    if (!draft) return;
    setEditTitle(draft.title || '');
    setEditContent(draft.content || '');
    setEditHashtags((draft.hashtags || []).join(' '));
    setEditing(true);
  }

  async function handleSave() {
    if (!id) return;
    setSaving(true);
    try {
      const hashtags = editHashtags
        .split(/[\s,]+/)
        .map((h) => h.trim())
        .filter((h) => h.length > 0)
        .map((h) => (h.startsWith('#') ? h : `#${h}`));
      await api.updateDraft(id, {
        title: editTitle,
        content: editContent,
        hashtags,
      });
      toast.success('Draft saved.');
      setEditing(false);
      await loadDraft();
    } catch (err) {
      toast.error('Save failed', err?.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!id) return;
    setDeleting(true);
    try {
      await api.deleteDraft(id);
      deleteDraft(id);
      toast.success('Draft deleted.');
      setConfirmDelete(false);
      navigate('/drafts');
    } catch (err) {
      toast.error('Delete failed', err?.message);
    } finally {
      // C2 — always reset state so the modal closes and loading clears,
      // even on success (the navigation unmounts but the finally still
      // runs synchronously).
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  async function handleSchedule() {
    if (!id || !scheduleTime) {
      toast.error('Pick a schedule time first.');
      return;
    }
    if (!draft?.title || !draft?.content) {
      toast.error('Draft must have a title and content.');
      return;
    }
    // H3 - reject past times client-side (the backend also rejects but
    // a clear UI error is better than waiting for a 400 round-trip).
    const scheduled = new Date(scheduleTime);
    if (Number.isNaN(scheduled.getTime()) || scheduled.getTime() <= Date.now()) {
      toast.error('Schedule time must be in the future.');
      return;
    }
    setScheduling(true);
    try {
      // Phase 8B P1-8 — use the user's local timezone (Intl default)
      // when sending the scheduled_time string.
      const offsetMinutes = -new Date().getTimezoneOffset();
      const sign = offsetMinutes >= 0 ? '+' : '-';
      const abs = Math.abs(offsetMinutes);
      const tz = `${sign}${String(Math.floor(abs / 60)).padStart(2, '0')}:${String(abs % 60).padStart(2, '0')}`;
      const local = new Date(scheduleTime);
      const iso = `${local.getFullYear()}-${String(local.getMonth() + 1).padStart(2, '0')}-${String(local.getDate()).padStart(2, '0')}T${String(local.getHours()).padStart(2, '0')}:${String(local.getMinutes()).padStart(2, '0')}:00${tz}`;
      await api.schedulePost({
        title: draft.title,
        content: draft.content,
        hashtags: draft.hashtags || [],
        scheduled_time: iso,
      });
      toast.success('Scheduled.');
      setScheduleTime('');
      await loadDraft();
    } catch (err) {
      toast.error('Schedule failed', err?.message);
    } finally {
      setScheduling(false);
    }
  }

  async function handleCancelSchedule() {
    if (!existingJobId) return;
    try {
      await api.cancelScheduledJob(existingJobId);
      toast.success('Schedule cancelled.');
      setExistingJobId(null);
      await loadDraft();
    } catch (err) {
      toast.error('Cancel failed', err?.message);
    } finally {
      setConfirmScheduleCancel(false);
    }
  }

  async function handlePublishNow() {
    if (!id) return;
    setPublishing(true);
    setPublishError(null);
    try {
      const res = await api.publishDraft(id);
      setPublishResult(res);
      setPublishOpen(false);
      toast.success('Published to LinkedIn.');
      await loadDraft();
    } catch (err) {
      setPublishError(err);
      const code = err?.code;
      if (code === 'INTERNAL_SERVER_ERROR') {
        toast.error('Publish failed', 'LinkedIn rejected the post. See the error above.');
      } else if (err?.status === 400) {
        toast.error('Cannot publish', err?.message);
      } else {
        toast.error('Publish failed', err?.message);
      }
    } finally {
      setPublishing(false);
    }
  }

  function handleCopy(type) {
    if (!draft) return;
    const text =
      type === 'content'
        ? draft.content
        : `${draft.title}\n\n${draft.content}\n\n${(draft.hashtags || []).join(' ')}`;
    navigator.clipboard
      .writeText(text)
      .then(() => toast.success(type === 'content' ? 'Content copied.' : 'LinkedIn version copied.'))
      .catch(() => toast.error('Copy failed', 'Clipboard unavailable.'));
  }

  function handleExport() {
    if (!draft) return;
    const blob = new Blob(
      [
        `# ${draft.title}\n\n${draft.content}\n\n${(draft.hashtags || []).join(' ')}`,
      ],
      { type: 'text/markdown;charset=utf-8' },
    );
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${(draft.title || 'draft').toLowerCase().replace(/\s+/g, '-')}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
    toast.success('Markdown downloaded.');
  }

  if (loading && !draft) {
    return (
      <div className="space-y-4">
        <Spinner /> Loading draft…
      </div>
    );
  }

  if (!draft) {
    return (
      <div className="space-y-4">
        <ErrorBanner error={error} onRetry={loadDraft} />
        <Link
          to="/drafts"
          className="inline-flex items-center gap-2 text-sm text-zinc-400 hover:text-zinc-100"
        >
          <ArrowLeft className="h-4 w-4" /> Back to drafts
        </Link>
        <EmptyState
          title="Draft not found"
          description="It may have been deleted or never existed."
          action={
            <Button onClick={() => navigate('/drafts')}>Back to drafts</Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Link
        to="/drafts"
        className="inline-flex items-center gap-2 text-sm text-zinc-400 hover:text-zinc-100"
      >
        <ArrowLeft className="h-4 w-4" /> Back to drafts
      </Link>

      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h1 className="text-3xl font-semibold">{draft.title || 'Untitled draft'}</h1>
          <p className="text-zinc-400">Topic: {draft.topic || '—'}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={() => handleCopy('content')}>
            <Copy className="h-4 w-4" /> Copy
          </Button>
          <Button size="sm" variant="outline" onClick={handleExport}>
            <Download className="h-4 w-4" /> Export
          </Button>
          {!isPublished ? (
            <Button size="sm" variant="outline" onClick={startEdit} disabled={isEditing}>
              <Edit3 className="h-4 w-4" /> Edit
            </Button>
          ) : null}
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setConfirmDelete(true)}
            loading={deleting}
          >
            <Trash2 className="h-4 w-4" /> Delete
          </Button>
        </div>
      </div>

      <ErrorBanner error={error} onRetry={loadDraft} />

      <Card>
        <CardHeader>
          <CardTitle>Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-2 text-sm text-zinc-300 sm:grid-cols-2 md:grid-cols-3">
            <div className="flex items-center gap-2">
              <span className="text-zinc-400">Status</span>
              <Badge>{draft.status || 'draft'}</Badge>
              {isPublished ? <Badge variant="success">Published</Badge> : null}
            </div>
            <div className="flex items-center gap-2">
              <span className="text-zinc-400">Review</span>
              <span className="text-zinc-200">{draft.reviewScore ?? '—'}/10</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-zinc-400">Created</span>
              <span className="text-zinc-200">{formatDateTime(draft.createdAt)}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-zinc-400">Updated</span>
              <span className="text-zinc-200">{formatDateTime(draft.updatedAt)}</span>
            </div>
            {draft.publishedAt || draft.published_at ? (
              <div className="flex items-center gap-2">
                <span className="text-zinc-400">Published</span>
                <span className="text-zinc-200">
                  {formatDateTime(draft.publishedAt || draft.published_at)}
                </span>
              </div>
            ) : null}
            {draft.linkedinPostId || draft.linkedin_post_id ? (
              <div className="flex items-center gap-2">
                <span className="text-zinc-400">LinkedIn</span>
                <span className="font-mono text-xs text-zinc-200">
                  {draft.linkedinPostId || draft.linkedin_post_id}
                </span>
              </div>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {isEditing ? (
        <Card>
          <CardHeader>
            <CardTitle>Edit draft</CardTitle>
            <CardDescription>Save to persist. Cancel reverts.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <label className="mb-1 block text-sm">Title</label>
              <Input value={editTitle} onChange={(event) => setEditTitle(event.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-sm">Content</label>
              <Textarea rows={10} value={editContent} onChange={(event) => setEditContent(event.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-sm">Hashtags (space-separated)</label>
              <Input
                value={editHashtags}
                onChange={(event) => setEditHashtags(event.target.value)}
                placeholder="#ai #linkedin"
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setEditing(false)} disabled={saving}>
                Cancel
              </Button>
              <Button size="sm" onClick={handleSave} loading={saving}>
                Save
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Content</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-zinc-100">
              <div className="text-lg font-semibold">{draft.title || 'Untitled'}</div>
              <div className="mt-3 whitespace-pre-line text-zinc-200">
                {draft.content || <span className="text-zinc-500">No content yet.</span>}
              </div>
              {(draft.hashtags || []).length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {draft.hashtags.map((tag) => (
                    <Badge key={tag}>{tag}</Badge>
                  ))}
                </div>
              ) : null}
            </div>
            {draft.metadata?.llm || draft.llm ? (
              <div className="mt-3 rounded-xl border border-white/10 bg-white/[0.03] p-3 text-xs text-zinc-500">
                Generated by{' '}
                <span className="text-zinc-300">
                  {(draft.metadata?.llm || draft.llm).writer_provider}/
                  {(draft.metadata?.llm || draft.llm).writer_model}
                </span>
                {draft.metadata?.llm?.reviewer_provider ? (
                  <>
                    {' '}
                    · reviewed by{' '}
                    <span className="text-zinc-300">
                      {draft.metadata.llm.reviewer_provider}/
                      {draft.metadata.llm.reviewer_model}
                    </span>
                  </>
                ) : null}
              </div>
            ) : null}
          </CardContent>
        </Card>
      )}

      {!isPublished ? (
        <Card>
          <CardHeader>
            <CardTitle>Schedule</CardTitle>
            <CardDescription>Pick a date + time. We send a TZ-aware ISO string.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input
              type="datetime-local"
              value={scheduleTime}
              onChange={(event) => setScheduleTime(event.target.value)}
            />
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-sm text-zinc-400">
                Timezone:{' '}
                <span className="text-zinc-300">
                  {Intl.DateTimeFormat().resolvedOptions().timeZone}
                </span>
              </div>
              <div className="flex gap-2">
                {existingJobId ? (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setConfirmScheduleCancel(true)}
                    loading={scheduling}
                  >
                    Cancel existing schedule
                  </Button>
                ) : null}
                <Button size="sm" onClick={handleSchedule} loading={scheduling}>
                  <CalendarClock className="h-4 w-4" /> Schedule
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {!isPublished ? (
        <Card>
          <CardHeader>
            <CardTitle>Publish now</CardTitle>
            <CardDescription>Posts to LinkedIn immediately (must be connected).</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => setPublishOpen(true)}>
              <Send className="h-4 w-4" /> Publish to LinkedIn
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {publishResult ? (
        <Card>
          <CardHeader>
            <CardTitle>Published</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-zinc-300">
            <div>
              LinkedIn post id:{' '}
              <span className="font-mono text-zinc-200">
                {publishResult.linkedin_post_id}
              </span>
            </div>
            {publishResult.published_at ? (
              <div>Published at: {formatDateTime(publishResult.published_at)}</div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <ConfirmDialog
        open={confirmDelete}
        title="Delete this draft?"
        description="The draft and its history will be removed. This cannot be undone."
        confirmLabel="Delete"
        danger
        confirming={deleting}
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(false)}
      />

      <ConfirmDialog
        open={confirmScheduleCancel}
        title="Cancel the scheduled job?"
        description="The draft itself is preserved; only the pending job is removed."
        confirmLabel="Cancel schedule"
        danger
        confirming={scheduling}
        onConfirm={handleCancelSchedule}
        onCancel={() => setConfirmScheduleCancel(false)}
      />

      <ConfirmDialog
        open={publishOpen}
        title="Publish this draft to LinkedIn?"
        description={
          draft
            ? `${draft.title}\n\n${(draft.content || '').slice(0, 200)}\n\n${(draft.hashtags || []).join(' ')}`.trim()
            : ''
        }
        confirmLabel={publishing ? 'Publishing…' : 'Publish'}
        confirming={publishing}
        onConfirm={handlePublishNow}
        onCancel={() => setPublishOpen(false)}
      >
        {publishError ? (
          <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-3 text-sm text-rose-200">
            <div className="font-medium">LinkedIn rejected the post.</div>
            <div className="mt-1 text-rose-300/80">{publishError.message}</div>
          </div>
        ) : null}
      </ConfirmDialog>
    </div>
  );
}
