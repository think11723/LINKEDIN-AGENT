import { useCallback, useEffect, useState } from 'react';
import { Check, X, FileCheck2, Inbox, AlertCircle, KeyRound, Sparkles, Eye } from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useToast } from '../context/ToastContext.jsx';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Field } from '../components/ui/Input.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { PageHeader } from '../components/ui/PageHeader.jsx';
import { EmptyState, ErrorBanner, Skeleton } from '../components/ui/Feedback.jsx';
import { formatDateTime } from '../utils/date.js';
import { LinkedInPreview } from '../components/ui/LinkedInPreview.jsx';

export default function ApprovalPage() {
  const api = useApi();
  const { toast } = useToast();

  const [queue, setQueue] = useState([]);
  const [queueLoading, setQueueLoading] = useState(true);
  const [queueError, setQueueError] = useState(null);

  const [token, setToken] = useState('');
  const [draft, setDraft] = useState(null);
  const [draftLoading, setDraftLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(null);
  const [actionMessage, setActionMessage] = useState(null);
  const [actionError, setActionError] = useState(null);

  const loadQueue = useCallback(async () => {
    setQueueLoading(true);
    setQueueError(null);
    try {
      const items = await api.getApprovalQueue();
      setQueue(items);
      if (!token && items[0]?.token) {
        setToken(items[0].token);
      }
    } catch (err) {
      setQueueError(err);
    } finally {
      setQueueLoading(false);
    }
  }, [api, token]);

  useEffect(() => {
    loadQueue();
  }, [loadQueue]);

  useEffect(() => {
    if (!token) {
      setDraft(null);
      return undefined;
    }
    let cancelled = false;
    setDraftLoading(true);
    setActionMessage(null);
    setActionError(null);
    api
      .getApprovalDraft(token)
      .then((data) => {
        if (cancelled) return;
        setDraft(data);
      })
      .catch((err) => {
        if (cancelled) return;
        setDraft(null);
        setActionError(err);
      })
      .finally(() => {
        if (!cancelled) setDraftLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [api, token]);

  async function handleApprove() {
    if (!token) return;
    setActionLoading('approve');
    setActionError(null);
    setActionMessage(null);
    try {
      const result = await api.approveDraft({ token });
      const msg = result?.message ?? 'Approved';
      setActionMessage({ tone: result?.success === false ? 'warning' : 'success', text: msg });
      if (result?.success === false) {
        toast.error('Approved, but publishing failed', msg);
      } else {
        toast.success('Approved and published');
      }
      await loadQueue();
      setToken('');
    } catch (err) {
      setActionError(err);
      toast.error('Approve failed', err?.message);
    } finally {
      setActionLoading(null);
    }
  }

  async function handleReject() {
    if (!token) return;
    setActionLoading('reject');
    setActionError(null);
    setActionMessage(null);
    try {
      const result = await api.rejectDraft({ token });
      const msg = result?.message ?? 'Rejected';
      setActionMessage({ tone: 'danger', text: msg });
      toast.success('Rejected');
      await loadQueue();
      setToken('');
    } catch (err) {
      setActionError(err);
      toast.error('Reject failed', err?.message);
    } finally {
      setActionLoading(null);
    }
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      <PageHeader
        eyebrow="Workspace"
        title="Approval Queue"
        subtitle="Review approval tokens and finalize publishing decisions."
      />

      <ErrorBanner error={queueError} onRetry={loadQueue} />

      <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Token review</CardTitle>
                <CardDescription>
                  Paste a token to inspect a draft and act on it.
                </CardDescription>
              </div>
              <FileCheck2 className="h-4 w-4 text-text-muted" />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field id="approval-token" label="Approval token">
              <Input
                id="approval-token"
                value={token}
                onChange={(event) => setToken(event.target.value)}
                placeholder="Paste a token"
                leftIcon={<KeyRound className="h-3.5 w-3.5" />}
              />
            </Field>

            <div className="flex flex-wrap gap-2">
              <Button
                variant="success"
                onClick={handleApprove}
                disabled={!token || draftLoading}
                loading={actionLoading === 'approve'}
                leftIcon={<Check className="h-4 w-4" />}
              >
                Approve &amp; Publish
              </Button>
              <Button
                variant="outline"
                onClick={handleReject}
                disabled={!token || draftLoading}
                loading={actionLoading === 'reject'}
                leftIcon={<X className="h-4 w-4" />}
              >
                Reject
              </Button>
            </div>

            {actionMessage ? (
              <ActionBanner tone={actionMessage.tone}>{actionMessage.text}</ActionBanner>
            ) : null}
            {actionError && !draftLoading ? (
              <ErrorBanner error={actionError} />
            ) : null}

            {draftLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-32 w-full" />
              </div>
            ) : draft ? (
              <DraftReview draft={draft} />
            ) : (
              <EmptyState
                icon={<Inbox className="h-5 w-5" />}
                title="No draft loaded"
                description="Provide a token above or pick one from the pending queue."
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Pending queue</CardTitle>
                <CardDescription>
                  {queueLoading ? 'Loading…' : `${queue.length} item${queue.length === 1 ? '' : 's'} waiting for review.`}
                </CardDescription>
              </div>
              <Badge tone="warning" size="sm" withDot>
                Pending
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            {queueLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-20" />
                ))}
              </div>
            ) : queue.length ? (
              <ul className="space-y-2">
                {queue.map((item) => (
                  <li key={item.draft_id}>
                    <button
                      type="button"
                      onClick={() => setToken(item.token)}
                      className={
                        'group w-full rounded-xl border p-3 text-left transition ' +
                        (item.token === token
                          ? 'border-brand-400/40 bg-brand-500/[0.08]'
                          : 'border-white/[0.06] bg-white/[0.02] hover:border-white/15 hover:bg-white/[0.04]')
                      }
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="truncate text-sm font-semibold text-zinc-100 group-hover:text-white">
                            {item.title}
                          </div>
                          {item.topic ? (
                            <div className="mt-0.5 truncate text-xs text-text-muted">
                              {item.topic}
                            </div>
                          ) : null}
                        </div>
                        {typeof item.review_score === 'number' ? (
                          <Badge tone={item.review_score >= 7 ? 'success' : 'warning'} size="sm">
                            {item.review_score}/10
                          </Badge>
                        ) : null}
                      </div>
                      <div className="mt-2 flex items-center justify-between text-[11px] text-text-muted">
                        <span className="font-mono">Token {item.token.slice(0, 8)}…</span>
                        <span>{formatDateTime(item.created_at)}</span>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                icon={<Check className="h-5 w-5" />}
                title="Inbox zero"
                description="No drafts waiting for review. Nice work."
              />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function ActionBanner({ tone, children }) {
  const toneClass = {
    success: 'border-emerald-500/30 bg-emerald-500/[0.06] text-emerald-200',
    warning: 'border-amber-500/30 bg-amber-500/[0.06] text-amber-200',
    danger: 'border-rose-500/30 bg-rose-500/[0.06] text-rose-200',
  }[tone] ?? 'border-white/10 bg-white/[0.04] text-text-secondary';
  return (
    <div className={`flex items-start gap-2 rounded-xl border p-3 text-sm ${toneClass}`}>
      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="flex-1">{children}</div>
    </div>
  );
}

function DraftReview({ draft }) {
  return (
    <div className="space-y-4 animate-fadeIn">
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="Status" value={draft.status} />
        <Stat label="Review score" value={`${draft.review_score ?? '—'}/10`} />
        <Stat label="Topic" value={draft.topic || '—'} />
      </div>
      <LinkedInPreview
        authorName="You"
        authorHeadline="on LinkedIn"
        content={draft.content}
        hashtags={draft.hashtags || []}
      />
      {draft.review_feedback ? (
        <div className="panel-inset p-3 text-sm text-text-secondary">
          <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">
            Reviewer feedback
          </div>
          <div className="mt-1">{draft.review_feedback}</div>
        </div>
      ) : null}
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="panel-inset p-3">
      <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">
        {label}
      </div>
      <div className="mt-1 truncate text-sm font-medium text-zinc-100">{value}</div>
    </div>
  );
}
