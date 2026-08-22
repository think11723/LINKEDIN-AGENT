import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Check,
  X,
  Sparkles,
  ArrowRight,
  Inbox,
  FileText,
  PencilLine,
  AlertCircle,
  BadgeCheck,
  ExternalLink,
  Star,
} from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { EmptyState, ErrorBanner, Skeleton } from '../components/ui/Feedback.jsx';
import { MotionPage } from '../components/ui/MotionPage.jsx';
import { QualityRing } from '../components/ui/QualityRing.jsx';
import { LinkedInPreview } from '../components/ui/LinkedInPreview.jsx';
import { formatDateTime } from '../utils/date.js';

const POLL_INTERVAL_MS = 20000;

export default function ApprovalPage() {
  const api = useApi();
  const navigate = useNavigate();
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
    try {
      const items = await api.getApprovalQueue();
      setQueue(items);
      if (!token && items[0]?.token) setToken(items[0].token);
      setQueueError(null);
    } catch (e) {
      setQueueError(e);
    } finally {
      setQueueLoading(false);
    }
  }, [api, token]);

  useEffect(() => {
    loadQueue();
    const t = window.setInterval(loadQueue, POLL_INTERVAL_MS);
    return () => window.clearInterval(t);
  }, [loadQueue]);

  useEffect(() => {
    if (!token) {
      setDraft(null);
      return;
    }
    let cancelled = false;
    setDraftLoading(true);
    api
      .getApprovalDraft(token)
      .then((data) => {
        if (!cancelled) {
          setDraft(data);
          setActionMessage(null);
        }
      })
      .catch((e) => {
        if (cancelled) return;
        setDraft(null);
        setActionMessage(e?.message ?? 'Unable to load draft');
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
      const message = result?.message ?? 'Approved and published';
      setActionMessage({ tone: result?.success === False ? 'warning' : 'success', text: message });
      if (result?.success === false) {
        toast.error('Approved, but publishing failed', message);
      } else {
        toast.success('Approved and published');
      }
      await loadQueue();
      setToken('');
    } catch (e) {
      setActionError(e);
      toast.error('Approve failed', e?.message);
      setActionMessage(e?.message);
    } finally {
      setActionLoading(null);
    }
  }

  async function handleReject() {
    if (!token) return;
    setActionLoading('reject');
    setActionError(null);
    try {
      const result = await api.rejectDraft({ token });
      setActionMessage({ tone: 'danger', text: result?.message ?? 'Rejected' });
      toast.success('Rejected');
      await loadQueue();
      setToken('');
    } catch (e) {
      setActionError(e);
      toast.error('Reject failed', e?.message);
    } finally {
      setActionLoading(null);
    }
  }

  return (
    <MotionPage className="space-y-6 p-4 md:p-6 lg:p-8">
      <header>
        <div className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-text-secondary">
          <BadgeCheck className="h-3 w-3 text-brand-300" />
          Reviewer · Approval
        </div>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
          <span className="text-text-secondary">AI </span>
          <span className="gradient-text">approval queue</span>
        </h1>
        <p className="mt-1 max-w-xl text-sm text-text-secondary">
          Review drafts the AI has prepared. Approve to publish to LinkedIn,
          edit to refine, or reject to discard.
        </p>
      </header>

      <ErrorBanner error={queueError} onRetry={loadQueue} />

      <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Inbox className="h-4 w-4 text-text-secondary" />
                  Pending drafts
                </CardTitle>
                <CardDescription>
                  {queueLoading
                    ? 'Loading…'
                    : `${queue.length} item${queue.length === 1 ? '' : 's'} waiting for review`}
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {queueLoading && queue.length === 0 ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, idx) => (
                  <Skeleton key={idx} className="h-16" />
                ))}
              </div>
            ) : queue.length === 0 ? (
              <EmptyState
                icon={<BadgeCheck className="h-5 w-5" />}
                title="Inbox zero"
                description="No drafts waiting for review. Nice work."
              />
            ) : (
              <ul className="space-y-2">
                {queue.map((item, idx) => (
                  <motion.li
                    key={item.draft_id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.04, duration: 0.2 }}
                  >
                    <button
                      type="button"
                      onClick={() => setToken(item.token)}
                      className={
                        'group w-full rounded-2xl border p-3 text-left transition ' +
                        (item.token === token
                          ? 'border-brand-400/40 bg-brand-500/[0.08]'
                          : 'border-white/[0.06] bg-white/[0.02] hover:border-white/[0.16] hover:bg-white/[0.04]')
                      }
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-semibold text-zinc-100">
                            {item.title}
                          </div>
                          <div className="mt-0.5 truncate text-xs text-text-muted">
                            {item.topic}
                          </div>
                          <div className="mt-1 text-[11px] text-text-muted">
                            {formatDateTime(item.created_at)}
                          </div>
                        </div>
                        {typeof item.review_score === 'number' ? (
                          <QualityRing
                            score={item.review_score}
                            max={10}
                            size={44}
                            stroke={4}
                            label={`Score ${item.review_score} of 10`}
                          />
                        ) : null}
                      </div>
                    </button>
                  </motion.li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-text-secondary" />
                  Review
                </CardTitle>
                <CardDescription>
                  {draftLoading
                    ? 'Loading…'
                    : draft
                    ? 'Inspect, edit, or approve.'
                    : 'Pick a draft from the queue.'}
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            {actionMessage ? (
              <ActionBanner tone={actionMessage.tone}>{actionMessage.text}</ActionBanner>
            ) : null}
            {actionError ? <ErrorBanner error={actionError} /> : null}

            {draftLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-4 w-1/3" />
                <Skeleton className="h-32 w-full" />
              </div>
            ) : draft ? (
              <>
                <div className="flex flex-wrap items-center gap-2 text-xs text-text-muted">
                  <Badge tone="brand" size="sm" withDot>
                    <Sparkles className="h-3 w-3" /> AI generated
                  </Badge>
                  <span>· {formatDateTime(draft.created_at || undefined)}</span>
                </div>
                <LinkedInPreview
                  authorName="You"
                  authorHeadline="on LinkedIn"
                  content={draft.content}
                  hashtags={draft.hashtags || []}
                />
                {draft.review_feedback ? (
                  <div className="glass-inset rounded-2xl p-3 text-sm text-text-secondary">
                    <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
                      Reviewer note
                    </div>
                    {draft.review_feedback}
                  </div>
                ) : null}
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="brand"
                    onClick={handleApprove}
                    disabled={actionLoading !== null}
                    loading={actionLoading === 'approve'}
                    leftIcon={<Check className="h-4 w-4" />}
                  >
                    Approve & Publish
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => navigate(`/drafts/${draft.draft_id}`)}
                    leftIcon={<PencilLine className="h-4 w-4" />}
                  >
                    Edit draft
                  </Button>
                  <Button
                    variant="outline"
                    onClick={handleReject}
                    disabled={actionLoading !== null}
                    loading={actionLoading === 'reject'}
                    leftIcon={<X className="h-4 w-4" />}
                  >
                    Reject
                  </Button>
                </div>
              </>
            ) : (
              <EmptyState
                size="sm"
                icon={<ArrowRight className="h-4 w-4" />}
                title="Nothing selected"
                description="Pick a pending draft to review."
              />
            )}
          </CardContent>
        </Card>
      </div>
    </MotionPage>
  );
}

const TONES = {
  success: {
    wrap: 'border-emerald-500/30 bg-emerald-500/[0.08]',
    title: 'text-emerald-100',
    body: 'text-emerald-200/80',
    icon: 'text-emerald-300',
    Icon: Check,
  },
  warning: {
    wrap: 'border-amber-500/30 bg-amber-500/[0.08]',
    title: 'text-amber-100',
    body: 'text-amber-200/80',
    icon: 'text-amber-300',
    Icon: AlertCircle,
  },
  danger: {
    wrap: 'border-rose-500/30 bg-rose-500/[0.08]',
    title: 'text-rose-100',
    body: 'text-rose-200/80',
    icon: 'text-rose-300',
    Icon: AlertCircle,
  },
  info: {
    wrap: 'border-sky-500/30 bg-sky-500/[0.08]',
    title: 'text-sky-100',
    body: 'text-sky-200/80',
    icon: 'text-sky-300',
    Icon: Star,
  },
};

function ActionBanner({ tone, children }) {
  const t = TONES[tone] || TONES.info;
  const Icon = t.Icon;
  return (
    <div className={`flex items-start gap-3 rounded-2xl border p-3 text-sm ${t.wrap}`}>
      <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${t.icon}`} />
      <div className={`flex-1 ${t.body}`}>{children}</div>
    </div>
  );
}
