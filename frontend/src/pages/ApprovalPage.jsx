import { useCallback, useEffect, useState } from 'react';
import { Check, X } from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input } from '../components/ui/Input.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { EmptyState, ErrorBanner, Skeleton } from '../components/ui/Feedback.jsx';
import { formatDateTime } from '../utils/date.js';

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
  const [message, setMessage] = useState(null);

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
    api
      .getApprovalDraft(token)
      .then((data) => {
        if (cancelled) return;
        setDraft(data);
        setMessage(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setDraft(null);
        setMessage(err?.message ?? 'Unable to load draft');
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
    try {
      const result = await api.approveDraft({ token });
      setMessage(result?.message ?? 'Approved');
      toast.success('Approved');
      await loadQueue();
    } catch (err) {
      toast.error('Approve failed', err?.message);
      setMessage(err?.message);
    } finally {
      setActionLoading(null);
    }
  }

  async function handleReject() {
    if (!token) return;
    setActionLoading('reject');
    try {
      const result = await api.rejectDraft({ token });
      setMessage(result?.message ?? 'Rejected');
      toast.success('Rejected');
      await loadQueue();
    } catch (err) {
      toast.error('Reject failed', err?.message);
      setMessage(err?.message);
    } finally {
      setActionLoading(null);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Approval Queue</h1>
        <p className="text-zinc-400">Review approval tokens and finalize publishing decisions.</p>
      </div>

      <ErrorBanner error={queueError} onRetry={loadQueue} />

      <div className="grid gap-4 lg:grid-cols-[1fr_0.85fr]">
        <Card>
          <CardHeader>
            <CardTitle>Token review</CardTitle>
            <CardDescription>Paste a token to inspect and act on a draft.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="label-muted mb-2 block">Approval token</label>
              <Input value={token} onChange={(event) => setToken(event.target.value)} placeholder="Paste a token" />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={handleApprove} disabled={!token} loading={actionLoading === 'approve'}>
                <Check className="h-4 w-4" /> Approve
              </Button>
              <Button
                variant="outline"
                onClick={handleReject}
                disabled={!token}
                loading={actionLoading === 'reject'}
              >
                <X className="h-4 w-4" /> Reject
              </Button>
            </div>
            {message ? (
              <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3 text-sm text-zinc-200">
                {message}
              </div>
            ) : null}

            {draftLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-32 w-full" />
              </div>
            ) : draft ? (
              <div className="space-y-3 rounded-2xl border border-white/10 bg-white/[0.03] p-4">
                <div className="text-lg font-semibold">{draft.title}</div>
                <div className="whitespace-pre-line text-zinc-200">{draft.content}</div>
                {draft.hashtags?.length ? (
                  <div className="flex flex-wrap gap-2">
                    {draft.hashtags.map((tag) => (
                      <Badge key={tag}>{tag}</Badge>
                    ))}
                  </div>
                ) : null}
                <div className="grid gap-2 sm:grid-cols-2 text-sm text-zinc-300">
                  <div className="panel-muted p-3">
                    <div className="text-zinc-400">Review score</div>
                    <div className="font-medium text-white">{draft.review_score}/10</div>
                  </div>
                  <div className="panel-muted p-3">
                    <div className="text-zinc-400">Status</div>
                    <div className="font-medium text-white">{draft.status}</div>
                  </div>
                  <div className="panel-muted p-3 sm:col-span-2">
                    <div className="text-zinc-400">Review feedback</div>
                    <div className="text-zinc-200">{draft.review_feedback || 'No feedback recorded.'}</div>
                  </div>
                </div>
              </div>
            ) : (
              <EmptyState
                title="No draft loaded"
                description="Provide a token above or pick one from the pending queue."
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Pending queue</CardTitle>
            <CardDescription>{queue.length} item(s) waiting for review.</CardDescription>
          </CardHeader>
          <CardContent>
            {queueLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            ) : queue.length ? (
              <div className="space-y-2">
                {queue.map((item) => (
                  <button
                    key={item.draft_id}
                    type="button"
                    onClick={() => setToken(item.token)}
                    className="w-full rounded-xl border border-white/10 bg-white/[0.03] p-3 text-left transition hover:border-violet-500/40 hover:bg-white/[0.06]"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="font-medium text-zinc-100">{item.title}</div>
                        <div className="text-sm text-zinc-400">{item.topic}</div>
                      </div>
                      <Badge variant="outline">Score {item.review_score ?? '—'}</Badge>
                    </div>
                    <div className="mt-2 text-xs text-zinc-500">
                      Token {item.token} · Created {formatDateTime(item.created_at)}
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No pending approvals"
                description="Once drafts move through the reviewer and require approval, they will appear here."
              />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}