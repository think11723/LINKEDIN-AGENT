import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  Sparkles,
  Activity,
  CalendarClock,
  CheckCircle2,
  FileCheck2,
  Inbox,
  Newspaper,
  NotebookPen,
  Send,
  TrendingUp,
  CirclePlus,
  Linkedin,
  XCircle,
  ExternalLink,
} from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useAuth } from '../context/AuthContext.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { ErrorBanner, Skeleton, EmptyState } from '../components/ui/Feedback.jsx';
import { MotionPage } from '../components/ui/MotionPage.jsx';
import { QualityRing } from '../components/ui/QualityRing.jsx';
import { DRAFT_STATUS_TONE, DRAFT_STATUS_LABEL } from '../utils/design.js';
import { formatDateTime } from '../utils/date.js';

const POLL_INTERVAL_MS = 20000;

const SUGGESTED_TOPICS = [
  'What I learned building a RAG application with LangChain',
  'Why async workflows matter for AI agents',
  'Three lessons from shipping a side project in 30 days',
  'How we cut our LLM inference costs by 60%',
];

function greetingForHour(hour) {
  if (hour < 5) return 'Working late';
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

function friendlyActivityType(t) {
  if (!t) return 'Activity';
  return t
    .toLowerCase()
    .split('_')
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(' ');
}

function StatCard({ label, value, icon, tone = 'brand', delta, className }) {
  const toneClass = {
    brand: 'text-brand-300 bg-brand-500/15 border-brand-400/20',
    accent: 'text-accent-400 bg-accent-500/15 border-accent-400/20',
    success: 'text-emerald-300 bg-emerald-500/15 border-emerald-400/20',
    warning: 'text-amber-300 bg-amber-500/15 border-amber-400/20',
    info: 'text-sky-300 bg-sky-500/15 border-sky-400/20',
  }[tone];
  return (
    <motion.div
      whileHover={{ y: -2 }}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
      className={
        'glass-card relative flex flex-col gap-3 overflow-hidden p-5 ' +
        (className || '')
      }
    >
      <div className="absolute -right-8 -top-8 h-24 w-24 rounded-full bg-gradient-brand-soft blur-2xl" />
      <div className="relative flex items-center justify-between">
        <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">
          {label}
        </div>
        {icon ? (
          <span
            className={
              'inline-flex h-9 w-9 items-center justify-center rounded-xl border ' +
              toneClass
            }
          >
            {icon}
          </span>
        ) : null}
      </div>
      <div className="relative flex items-baseline gap-2">
        {value === null ? (
          <Skeleton className="h-8 w-16" />
        ) : (
          <div className="text-3xl font-semibold tracking-tight text-white">
            {value}
          </div>
        )}
        {delta ? (
          <div className="text-xs text-emerald-300">{delta}</div>
        ) : null}
      </div>
    </motion.div>
  );
}

function LinkedInStatusPill({ connected, onClick }) {
  if (connected) {
    return (
      <div className="glass-inset flex items-center gap-3 rounded-2xl p-4">
        <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-emerald-400/20 bg-emerald-500/15 text-emerald-300">
          <CheckCircle2 className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold text-white">LinkedIn connected</div>
          <div className="text-xs text-text-muted">Ready to publish</div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={onClick}
          rightIcon={<ArrowRight className="h-3.5 w-3.5" />}
        >
          Manage
        </Button>
      </div>
    );
  }
  return (
    <div className="glass-inset flex items-center gap-3 rounded-2xl p-4">
      <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-rose-400/20 bg-rose-500/15 text-rose-300">
        <XCircle className="h-4 w-4" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-semibold text-white">LinkedIn disconnected</div>
        <div className="text-xs text-text-muted">Connect to publish drafts</div>
      </div>
      <Button
        variant="brand"
        size="sm"
        onClick={onClick}
        leftIcon={<Linkedin className="h-3.5 w-3.5" />}
      >
        Connect
      </Button>
    </div>
  );
}

function AiSparkles() {
  return (
    <div className="relative h-10 w-10 shrink-0">
      <div className="absolute inset-0 rounded-2xl gradient-brand opacity-90 blur-[2px]" />
      <div className="absolute inset-0 flex items-center justify-center rounded-2xl gradient-brand shadow-glow-brand">
        <Sparkles className="h-4 w-4 text-white" />
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const api = useApi();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [summary, setSummary] = useState(null);
  const [recentDrafts, setRecentDrafts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [linkedinConnected, setLinkedinConnected] = useState(false);

  const load = useCallback(async () => {
    try {
      const [s, d, status] = await Promise.all([
        api.getDashboardSummary(),
        api.listDrafts({ page: 1, page_size: 5 }),
        api.getLinkedInStatus().catch(() => ({ connected: false })),
      ]);
      setSummary(s);
      setRecentDrafts(Array.isArray(d?.items) ? d.items : []);
      setLinkedinConnected(Boolean(status?.connected));
      setError(null);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    load();
    const interval = window.setInterval(load, POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [load]);

  const greeting = greetingForHour(new Date().getHours());
  const firstName =
    (user?.displayName || user?.email || 'there').split(/[ @]/)[0] || 'there';

  return (
    <MotionPage className="space-y-6 p-4 md:p-6 lg:p-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-text-secondary">
            <Sparkles className="h-3 w-3 text-brand-300" />
            AI Workspace
          </div>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            <span className="text-text-secondary">{greeting},</span>{' '}
            <span className="gradient-text">{firstName}.</span>
          </h1>
          <p className="mt-1 max-w-xl text-sm text-text-secondary">
            Your AI-powered content studio. Create, refine, and publish
            LinkedIn posts with the polish of a hand-crafted draft and the
            velocity of automation.
          </p>
        </div>
        <Button
          variant="brand"
          size="lg"
          onClick={() => navigate('/create')}
          leftIcon={<CirclePlus className="h-4 w-4" />}
        >
          Create New Post
        </Button>
      </header>

      <ErrorBanner error={error} onRetry={load} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Posts generated"
          value={summary?.drafts_count ?? (loading ? null : 0)}
          icon={<NotebookPen className="h-4 w-4" />}
          tone="brand"
        />
        <StatCard
          label="Pending review"
          value={summary?.approval_queue_count ?? (loading ? null : 0)}
          icon={<FileCheck2 className="h-4 w-4" />}
          tone="warning"
        />
        <StatCard
          label="Scheduled"
          value={summary?.scheduled_count ?? (loading ? null : 0)}
          icon={<CalendarClock className="h-4 w-4" />}
          tone="info"
        />
        <StatCard
          label="Published"
          value={summary?.published_count ?? (loading ? null : 0)}
          icon={<Send className="h-4 w-4" />}
          tone="success"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Recent drafts</CardTitle>
              <CardDescription>
                Your five most recent LinkedIn drafts.
              </CardDescription>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/drafts')}
              rightIcon={<ArrowRight className="h-3.5 w-3.5" />}
            >
              View all
            </Button>
          </CardHeader>
          <CardContent>
            {loading && recentDrafts.length === 0 ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, idx) => (
                  <Skeleton key={idx} className="h-16" />
                ))}
              </div>
            ) : recentDrafts.length === 0 ? (
              <EmptyState
                icon={<NotebookPen className="h-5 w-5" />}
                title="No drafts yet"
                description="Generate your first LinkedIn post to see it here."
                action={
                  <Button
                    variant="brand"
                    size="sm"
                    onClick={() => navigate('/create')}
                    leftIcon={<Sparkles className="h-3.5 w-3.5" />}
                  >
                    Create your first post
                  </Button>
                }
              />
            ) : (
              <ul className="space-y-2">
                {recentDrafts.map((draft, idx) => {
                  const status = draft.status || 'draft';
                  const tone = DRAFT_STATUS_TONE[status] || DRAFT_STATUS_TONE.draft;
                  return (
                    <motion.li
                      key={draft.id}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: idx * 0.04, duration: 0.2 }}
                    >
                      <Link
                        to={`/drafts/${draft.id}`}
                        className="group flex items-center gap-3 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-3 transition hover:border-white/[0.14] hover:bg-white/[0.04]"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <div className="truncate text-sm font-semibold text-zinc-100 group-hover:text-white">
                              {draft.title || 'Untitled draft'}
                            </div>
                          </div>
                          <div className="mt-0.5 truncate text-xs text-text-muted">
                            Updated {formatDateTime(draft.updatedAt || draft.updated_at)}
                          </div>
                        </div>
                        <Badge tone={tone.label.toLowerCase()} size="sm" withDot>
                          {DRAFT_STATUS_LABEL[status] || status}
                        </Badge>
                        <ArrowRight className="h-3.5 w-3.5 shrink-0 text-text-muted opacity-0 transition group-hover:translate-x-0.5 group-hover:opacity-100" />
                      </Link>
                    </motion.li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <LinkedInStatusPill
            connected={linkedinConnected}
            onClick={() => navigate('/settings')}
          />
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-brand-300" />
                Recent activity
              </CardTitle>
              <CardDescription>Your latest LinkedIn AI Studio events.</CardDescription>
            </CardHeader>
            <CardContent>
              {loading && (!summary?.recent_activity || summary.recent_activity.length === 0) ? (
                <div className="space-y-2">
                  {Array.from({ length: 3 }).map((_, idx) => (
                    <Skeleton key={idx} className="h-12" />
                  ))}
                </div>
              ) : summary?.recent_activity?.length ? (
                <ul className="space-y-3">
                  {summary.recent_activity.slice(0, 6).map((a, idx) => (
                    <motion.li
                      key={`${a.event_type}-${a.timestamp}-${idx}`}
                      initial={{ opacity: 0, x: -4 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.04, duration: 0.2 }}
                      className="flex items-start gap-3"
                    >
                      <span
                        className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-gradient-brand shadow-glow-brand"
                        aria-hidden
                      />
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-medium text-zinc-100">
                          {friendlyActivityType(a.event_type)}
                        </div>
                        {a.description ? (
                          <div className="mt-0.5 line-clamp-2 text-xs text-text-muted">
                            {a.description}
                          </div>
                        ) : null}
                        <div className="mt-0.5 text-[11px] text-text-muted">
                          {formatDateTime(a.timestamp)}
                        </div>
                      </div>
                    </motion.li>
                  ))}
                </ul>
              ) : (
                <EmptyState
                  size="sm"
                  icon={<Inbox className="h-4 w-4" />}
                  title="No activity yet"
                  description="Activity will appear here as you use the studio."
                />
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-accent-400" />
            Need inspiration?
          </CardTitle>
          <CardDescription>
            Quick-start prompts to get the AI writing your next post.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2">
            {SUGGESTED_TOPICS.map((topic, idx) => (
              <motion.button
                key={topic}
                type="button"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.05, duration: 0.22 }}
                whileHover={{ y: -2 }}
                onClick={() => navigate(`/create?topic=${encodeURIComponent(topic)}`)}
                className="glass-card group flex items-start gap-3 rounded-2xl p-4 text-left transition hover:border-white/[0.18] hover:bg-white/[0.04]"
              >
                <AiSparkles />
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-medium text-zinc-100 group-hover:text-white">
                    {topic}
                  </div>
                  <div className="mt-0.5 text-[11px] uppercase tracking-wider text-text-muted">
                    Click to use as topic
                  </div>
                </div>
                <ArrowRight className="mt-1.5 h-3.5 w-3.5 shrink-0 text-text-muted transition group-hover:translate-x-0.5 group-hover:text-zinc-200" />
              </motion.button>
            ))}
          </div>
        </CardContent>
      </Card>
    </MotionPage>
  );
}
