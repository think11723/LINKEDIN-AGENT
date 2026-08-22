import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
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
  CheckCircle2,
  Bookmark,
  Github,
  Globe,
  FileText,
  Sparkles,
  BarChart3,
  Clock,
} from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useDrafts } from '../context/DraftsContext.jsx';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Textarea, Field } from '../components/ui/Input.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { ConfirmDialog } from '../components/ConfirmDialog.jsx';
import { EmptyState, ErrorBanner, Skeleton } from '../components/ui/Feedback.jsx';
import { MotionPage } from '../components/ui/MotionPage.jsx';
import { QualityRing } from '../components/ui/QualityRing.jsx';
import { LinkedInPreview } from '../components/ui/LinkedInPreview.jsx';
import { SourcePreviewCard } from '../components/ui/SourcePreviewCard.jsx';
import { DRAFT_STATUS_TONE, DRAFT_STATUS_LABEL } from '../utils/design.js';
import { formatDateTime } from '../utils/date.js';
import { cn } from '../utils/cn.js';

function wordCountOf(s) {
  return (s || '').split(/\s+/).filter(Boolean).length;
}

function readingTimeMinutes(s) {
  const words = wordCountOf(s);
  // Average reading speed ≈ 200 wpm.
  return Math.max(1, Math.round(words / 200));
}

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
  const [err, setErr] = useState(null);

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
  const [publishErr, setPublishErr] = useState(null);
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
      setErr(null);
    } catch (e) {
      if (e?.status === 404) {
        setServerDraft(null);
        setErr(null);
      } else {
        setErr(e);
      }
    } finally {
      setLoading(false);
    }
  }, [api, id]);

  useEffect(() => {
    setEditing(false);
    setScheduleTime('');
    setPublishResult(null);
    setPublishErr(null);
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
    } catch (e) {
      toast.error('Save failed', e?.message);
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
    } catch (e) {
      toast.error('Delete failed', e?.message);
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
    } catch (e) {
      toast.error('Schedule failed', e?.message);
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
    } catch (e) {
      toast.error('Cancel failed', e?.message);
    } finally {
      setConfirmScheduleCancel(false);
    }
  }

  async function handlePublishNow() {
    if (!id) return;
    setPublishing(true);
    setPublishErr(null);
    try {
      const res = await api.publishDraft(id);
      setPublishResult(res);
      setPublishOpen(false);
      toast.success('Published to LinkedIn.');
      await loadDraft();
    } catch (e) {
      setPublishErr(e);
      const code = e?.code;
      if (code === 'INTERNAL_SERVER_ERROR') {
        toast.error('Publish failed', 'LinkedIn rejected the post.');
      } else if (e?.status === 400) {
        toast.error('Cannot publish', e?.message);
      } else {
        toast.error('Publish failed', e?.message);
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
      <MotionPage className="space-y-6 p-4 md:p-6 lg:p-8">
        <div className="space-y-3">
          <Skeleton className="h-7 w-64" />
          <Skeleton className="h-4 w-96" />
        </div>
        <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
          <Skeleton className="h-96" />
          <Skeleton className="h-96" />
        </div>
      </MotionPage>
    );
  }

  if (!draft) {
    return (
      <MotionPage className="space-y-6 p-4 md:p-6 lg:p-8">
        <ErrorBanner error={err} onRetry={loadDraft} />
        <EmptyState
          icon={<FileText className="h-5 w-5" />}
          title="Draft not found"
          description="It may have been deleted or never existed."
          action={
            <Button onClick={() => navigate('/drafts')}>Back to drafts</Button>
          }
        />
      </MotionPage>
    );
  }

  const status = draft.status || 'draft';
  const statusTone = DRAFT_STATUS_TONE[status] || DRAFT_STATUS_TONE.draft;
  const sourceMeta = draft.source_metadata || {};
  const sourceType = sourceMeta.source_type;
  const sourceUrl = draft.source_url;
  const words = wordCountOf(draft.content);
  const readMin = readingTimeMinutes(draft.content);
  const isPublished = Boolean(draft.published_at);

  return (
    <MotionPage className="space-y-6 p-4 md:p-6 lg:p-8">
      <div className="flex flex-wrap items-center gap-3">
        <Link
          to="/drafts"
          className="inline-flex items-center gap-1.5 text-sm text-text-muted transition hover:text-zinc-100"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to Drafts
        </Link>
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => handleCopy('content')}
            leftIcon={<Copy className="h-3.5 w-3.5" />}
          >
            Copy
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
              disabled={editing}
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

      <header className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={statusTone.label.toLowerCase()} size="md" withDot>
            {DRAFT_STATUS_LABEL[status] || status}
          </Badge>
          {sourceType && !sourceUrl ? null : null}
          <span className="inline-flex items-center gap-1.5 rounded-full border border-white/[0.08] bg-white/[0.03] px-2.5 py-0.5 text-[11px] uppercase tracking-[0.12em] text-text-muted">
            <Clock className="h-3 w-3" /> {readMin} min read
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-white/[0.08] bg-white/[0.03] px-2.5 py-0.5 text-[11px] uppercase tracking-[0.12em] text-text-muted">
            <BarChart3 className="h-3 w-3" /> {words} words
          </span>
        </div>
        <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">
          {draft.title || 'Untitled draft'}
        </h1>
        {draft.topic ? (
          <p className="text-sm text-text-secondary">Topic: {draft.topic}</p>
        ) : null}
      </header>

      <ErrorBanner error={err} onRetry={loadDraft} />

      {sourceUrl ? (
        <SourcePreviewCard
          compact
          sourceType={sourceType || 'generic_webpage'}
          title={sourceMeta.full_name || sourceMeta.title || sourceMeta.description || 'Source'}
          description={sourceMeta.description || ''}
          summary={sourceMeta.summary || ''}
          url={sourceUrl}
          finalUrl={sourceMeta.canonical_url || sourceUrl}
        />
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-4">
          {editing ? (
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
                    rows={12}
                    className="font-mono"
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                  />
                </Field>
                <Field
                  id="edit-hashtags"
                  label="Hashtags"
                  hint="Space-separated. # is added automatically."
                >
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
                <CardTitle>LinkedIn preview</CardTitle>
                <CardDescription>
                  How this post will look when published.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <LinkedInPreview
                  authorName="You"
                  authorHeadline="on LinkedIn"
                  content={draft.content}
                  hashtags={draft.hashtags || []}
                  sourceAttribution={
                    sourceUrl
                      ? {
                          label:
                            sourceType === 'github_repository'
                              ? 'GitHub Repository'
                              : sourceType === 'github_readme'
                              ? 'GitHub README'
                              : sourceType === 'blog_article'
                              ? 'Blog Article'
                              : sourceType === 'documentation'
                              ? 'Documentation'
                              : sourceType === 'product_page'
                              ? 'Product Announcement'
                              : 'Source',
                          title:
                            sourceMeta.full_name ||
                            sourceMeta.title ||
                            sourceMeta.description,
                          url: sourceMeta.canonical_url || sourceUrl,
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
                <CardTitle className="flex items-center gap-2">
                  <CalendarClock className="h-4 w-4 text-text-secondary" />
                  Schedule
                </CardTitle>
                <CardDescription>
                  Pick a date and time. We send a TZ-aware ISO string.
                </CardDescription>
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
                        variant="secondary"
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
              <CardTitle>Draft quality</CardTitle>
              <CardDescription>
                Reviewer evaluation (when scores are present).
              </CardDescription>
            </CardHeader>
            <CardContent>
              {draft.review_score !== undefined && draft.review_score !== null ? (
                <div className="flex items-center gap-4">
                  <QualityRing
                    score={Math.round(draft.review_score || 0)}
                    max={10}
                    size={88}
                    label={`Score ${draft.review_score} of 10`}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold text-white">
                      {draft.review_score >= 8
                        ? 'Strong'
                        : draft.review_score >= 6
                        ? 'Good'
                        : 'Needs work'}
                    </div>
                    <div className="text-xs text-text-muted">
                      Reviewer score
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-sm text-text-muted">
                  No reviewer score available for this draft yet.
                </div>
              )}
              {draft.review_feedback ? (
                <p className="mt-3 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 text-sm text-text-secondary">
                  {draft.review_feedback}
                </p>
              ) : null}
            </CardContent>
          </Card>

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
              <DetailRow label="Created">
                <span className="text-zinc-100">{formatDateTime(draft.createdAt || draft.created_at)}</span>
              </DetailRow>
              <DetailRow label="Updated">
                <span className="text-zinc-100">{formatDateTime(draft.updatedAt || draft.updated_at)}</span>
              </DetailRow>
              {draft.publishedAt || draft.published_at ? (
                <DetailRow label="Published">
                  <span className="text-zinc-100">{formatDateTime(draft.publishedAt || draft.published_at)}</span>
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
                <CardTitle className="flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-emerald-300" />
                  Published
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-zinc-300">
                <div>
                  LinkedIn post id:{' '}
                  <span className="font-mono text-zinc-100">
                    {publishResult.linkedin_post_id}
                  </span>
                </div>
                {publishResult.published_at ? (
                  <div>
                    Published at: {formatDateTime(publishResult.published_at)}
                  </div>
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
        {publishErr ? (
          <div className="mt-3 rounded-xl border border-rose-500/30 bg-rose-500/[0.08] p-3 text-sm text-rose-200">
            <div className="flex items-center gap-2 font-medium">
              <X className="h-4 w-4" /> LinkedIn rejected the post.
            </div>
            <div className="mt-1 text-rose-200/80">{publishErr.message}</div>
          </div>
        ) : null}
      </ConfirmDialog>
    </MotionPage>
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
