import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import {
  ArrowLeft,
  CalendarClock,
  Copy,
  Download,
  Trash2,
  Edit3,
  Send,
  Save,
  X,
  ExternalLink,
  Link2,
  Check,
  AlertCircle,
  BadgeCheck,
  Inbox,
  Sparkles,
  FileText,
} from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useDrafts } from '../context/DraftsContext.jsx';
import { useToast } from '../context/ToastContext.jsx';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
  CardFooter,
} from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Textarea, Field } from '../components/ui/Input.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { PageHeader } from '../components/ui/PageHeader.jsx';
import { ConfirmDialog } from '../components/ConfirmDialog.jsx';
import { ErrorBanner, Spinner, EmptyState, Skeleton } from '../components/ui/Feedback.jsx';
import { formatDateTime } from '../utils/date.js';
import { LinkedInPreview } from '../components/ui/LinkedInPreview.jsx';
import { SourcePreviewCard, SourceTypeChip } from '../components/ui/SourcePreviewCard.jsx';
import { DRAFT_STATUS_TONE, DRAFT_STATUS_LABEL, SOURCE_TONE, SOURCE_TYPE_LABEL } from '../utils/design.js';

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
    setEditing(false);
    setScheduleTime('');
    setPublishResult(null);
    setPublishError(null);
    loadDraft();
  }, [loadDraft]);

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
  const sourceMeta = draft?.source_metadata || null;
  const sourceType = sourceMeta?.source_type || sourceMeta?.adapter || null;
  const status = draft?.status || 'draft';
  const statusTone = DRAFT_STATUS_TONE[status] || DRAFT_STATUS_TONE.draft;

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
    const scheduled = new Date(scheduleTime);
    if (Number.isNaN(scheduled.getTime()) || scheduled.getTime() <= Date.now()) {
      toast.error('Schedule time must be in the future.');
      return;
    }
    setScheduling(true);
    try {
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
      [`# ${draft.title}\n\n${draft.content}\n\n${(draft.hashtags || []).join(' ')}`],
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
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-72" />
      </div>
    );
  }

  if (!draft) {
    return (
      <div className="space-y-4 animate-fadeIn">
        <ErrorBanner error={error} onRetry={loadDraft} />
        <EmptyState
          icon={<Inbox className="h-5 w-5" />}
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
    <div className="space-y-6 animate-fadeIn">
      <div className="flex items-center justify-between">
        <Link
          to="/drafts"
          className="inline-flex items-center gap-1.5 text-sm text-text-muted transition hover:text-zinc-100"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to Drafts
        </Link>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => handleCopy('content')}
            leftIcon={<Copy className="h-3.5 w-3.5" />}
          >
            Copy content
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={handleExport}
            leftIcon={<Download className="h-3.5 w-3.5" />}
          >
            Export
          </Button>
          {!isPublished ? (
            <Button
              size="sm"
              variant="secondary"
              onClick={startEdit}
              disabled={isEditing}
              leftIcon={<Edit3 className="h-3.5 w-3.5" />}
            >
              Edit
            </Button>
          ) : null}
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setConfirmDelete(true)}
            className="text-text-muted hover:text-rose-300"
            leftIcon={<Trash2 className="h-3.5 w-3.5" />}
          >
            Delete
          </Button>
        </div>
      </div>

      <PageHeader
        eyebrow="Workspace"
        title={draft.title || 'Untitled draft'}
        subtitle={draft.topic ? `Topic: ${draft.topic}` : undefined}
        actions={
          <Badge tone={statusTone.label.toLowerCase()} size="lg" withDot>
            {DRAFT_STATUS_LABEL[status] || status}
            {isPublished ? ' · LinkedIn' : null}
          </Badge>
        }
      />

      {sourceType || draft.source_url ? (
        <SourcePreviewCard
          compact
          sourceType={sourceType || 'generic_webpage'}
          title={sourceMeta?.full_name || sourceMeta?.description || SOURCE_TYPE_LABEL[sourceType] || 'Source'}
          description={sourceMeta?.description || sourceMeta?.readme_summary || ''}
          summary={sourceMeta?.summary || ''}
          url={draft.source_url}
          finalUrl={sourceMeta?.canonical_url || draft.source_url}
        />
      ) : null}

      <ErrorBanner error={error} onRetry={loadDraft} />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          {isEditing ? (
            <Card>
              <CardHeader>
                <CardTitle>Edit draft</CardTitle>
                <CardDescription>Save to persist. Cancel reverts.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Field id="edit-title" label="Title" required>
                  <Input
                    id="edit-title"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                  />
                </Field>
                <Field id="edit-content" label="Content" required>
                  <Textarea
                    id="edit-content"
                    rows={10}
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                  />
                </Field>
                <Field id="edit-hashtags" label="Hashtags" hint="Space-separated. # is added automatically.">
                  <Input
                    id="edit-hashtags"
                    value={editHashtags}
                    onChange={(e) => setEditHashtags(e.target.value)}
                    placeholder="#ai #linkedin"
                  />
                </Field>
              </CardContent>
              <CardFooter>
                <Button
                  variant="ghost"
                  onClick={() => setEditing(false)}
                  disabled={saving}
                >
                  Cancel
                </Button>
                <Button
                  variant="brand"
                  onClick={handleSave}
                  loading={saving}
                  leftIcon={<Save className="h-4 w-4" />}
                >
                  Save changes
                </Button>
              </CardFooter>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>LinkedIn preview</CardTitle>
                    <CardDescription>
                      How this post will look when published.
                    </CardDescription>
                  </div>
                  <BadgeCheck className="h-4 w-4 text-sky-400" />
                </div>
              </CardHeader>
              <CardContent>
                <LinkedInPreview
                  authorName="You"
                  authorHeadline="on LinkedIn"
                  content={draft.content}
                  hashtags={draft.hashtags || []}
                  sourceAttribution={
                    draft.source_url
                      ? {
                          label: SOURCE_TYPE_LABEL[sourceType] || 'Source',
                          title: sourceMeta?.full_name || sourceMeta?.description,
                          url: sourceMeta?.canonical_url || draft.source_url,
                        }
                      : null
                  }
                />
              </CardContent>
            </Card>
          )}

          {!isPublished ? (
            <Card>
              <CardHeader>
                <CardTitle>Schedule</CardTitle>
                <CardDescription>Pick a date and time. We send a TZ-aware ISO string.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Input
                  type="datetime-local"
                  value={scheduleTime}
                  onChange={(event) => setScheduleTime(event.target.value)}
                />
                <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                  <div className="text-text-muted">
                    Timezone:{' '}
                    <span className="text-zinc-100">
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
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={handleSchedule}
                      loading={scheduling}
                      leftIcon={<CalendarClock className="h-3.5 w-3.5" />}
                    >
                      Schedule
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : null}
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <DetailRow label="Status">
                <Badge tone={statusTone.label.toLowerCase()} size="sm" withDot>
                  {DRAFT_STATUS_LABEL[status] || status}
                </Badge>
                {isPublished ? <Badge tone="success" size="sm">Published</Badge> : null}
              </DetailRow>
              <DetailRow label="Review">
                <span className="text-zinc-100">
                  {typeof draft.reviewScore === 'number' ? `${draft.reviewScore}/10` : '—'}
                </span>
              </DetailRow>
              <DetailRow label="Created">
                <span className="text-zinc-100">{formatDateTime(draft.createdAt || draft.created_at)}</span>
              </DetailRow>
              <DetailRow label="Updated">
                <span className="text-zinc-100">{formatDateTime(draft.updatedAt || draft.updated_at)}</span>
              </DetailRow>
              {draft.publishedAt || draft.published_at ? (
                <DetailRow label="Published">
                  <span className="text-zinc-100">
                    {formatDateTime(draft.publishedAt || draft.published_at)}
                  </span>
                </DetailRow>
              ) : null}
              {draft.linkedinPostId || draft.linkedin_post_id ? (
                <DetailRow label="LinkedIn">
                  <span className="font-mono text-xs text-zinc-100">
                    {draft.linkedinPostId || draft.linkedin_post_id}
                  </span>
                </DetailRow>
              ) : null}
            </CardContent>
          </Card>

          {draft.review_feedback ? (
            <Card>
              <CardHeader>
                <CardTitle>Reviewer feedback</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-text-secondary">{draft.review_feedback}</p>
              </CardContent>
            </Card>
          ) : null}

          {draft.metadata?.llm || draft.llm ? (
            <Card variant="muted">
              <CardContent className="space-y-2 text-xs text-text-muted">
                <div className="font-semibold text-text-secondary">Generated by</div>
                <div>
                  Writer:{' '}
                  <span className="text-zinc-200">
                    {(draft.metadata?.llm || draft.llm).writer_provider}/
                    {(draft.metadata?.llm || draft.llm).writer_model}
                  </span>
                </div>
                {draft.metadata?.llm?.reviewer_provider ? (
                  <div>
                    Reviewer:{' '}
                    <span className="text-zinc-200">
                      {draft.metadata.llm.reviewer_provider}/
                      {draft.metadata.llm.reviewer_model}
                    </span>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          ) : null}

          {!isPublished ? (
            <Card>
              <CardContent>
                <Button
                  variant="brand"
                  size="lg"
                  className="w-full"
                  onClick={() => setPublishOpen(true)}
                  leftIcon={<Send className="h-4 w-4" />}
                >
                  Publish to LinkedIn
                </Button>
                <p className="mt-2 text-xs text-text-muted">
                  Posts immediately. LinkedIn must be connected.
                </p>
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
        </div>
      </div>

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
          <div className="mt-3 rounded-xl border border-rose-500/30 bg-rose-500/[0.06] p-3 text-sm text-rose-200">
            <div className="flex items-center gap-2 font-medium">
              <AlertCircle className="h-4 w-4" /> LinkedIn rejected the post.
            </div>
            <div className="mt-1 text-rose-200/80">{publishError.message}</div>
          </div>
        ) : null}
      </ConfirmDialog>
    </div>
  );
}

function DetailRow({ label, children }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-text-muted">{label}</span>
      <div className="flex items-center gap-1.5">{children}</div>
    </div>
  );
}
