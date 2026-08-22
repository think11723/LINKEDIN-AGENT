import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  NotebookPen,
  FileCheck2,
  CalendarClock,
  Newspaper,
  AlertTriangle,
  CheckCircle2,
  CirclePlus,
  Sparkles,
  Activity,
  Inbox,
} from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { PageHeader } from '../components/ui/PageHeader.jsx';
import { StatCard } from '../components/ui/StatCard.jsx';
import { ErrorBanner, Spinner, Skeleton, EmptyState } from '../components/ui/Feedback.jsx';
import { formatDateTime } from '../utils/date.js';
import { DRAFT_STATUS_TONE, DRAFT_STATUS_LABEL, SOURCE_TONE } from '../utils/design.js';

const POLL_INTERVAL_MS = 15000;

const TILES = [
  { key: 'drafts_count', label: 'Total drafts', icon: NotebookPen, href: '/drafts', tone: 'neutral' },
  { key: 'approval_queue_count', label: 'Needs review', icon: FileCheck2, href: '/approval', tone: 'warning' },
  { key: 'approved_count', label: 'Approved', icon: CheckCircle2, href: '/drafts?status=approved', tone: 'success' },
  { key: 'scheduled_count', label: 'Scheduled', icon: CalendarClock, href: '/scheduled-posts', tone: 'info' },
  { key: 'published_count', label: 'Published', icon: Newspaper, href: '/published-posts', tone: 'brand' },
  { key: 'failed_count', label: 'Failed', icon: AlertTriangle, href: '/scheduled-posts', tone: 'danger' },
];

const QUICK_ACTIONS = [
  { label: 'Generate draft', description: 'Topic or URL', href: '/create', icon: Sparkles },
  { label: 'Review approvals', description: 'Pending queue', href: '/approval', icon: FileCheck2 },
  { label: 'View drafts', description: 'Library', href: '/drafts', icon: NotebookPen },
  { label: 'See published', description: 'LinkedIn history', href: '/published-posts', icon: Newspaper },
];

export default function DashboardPage() {
  const api = useApi();
  const navigate = useNavigate();
  const [summary, setSummary] = useState(null);
  const [recentDrafts, setRecentDrafts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      const [s, d] = await Promise.all([
        api.getDashboardSummary(),
        api.listDrafts({ page: 1, page_size: 5 }),
      ]);
      setSummary(s);
      setRecentDrafts(Array.isArray(d?.items) ? d.items : []);
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

  const greeting = greetingForHour();

  return (
    <div className="space-y-6 animate-fadeIn">
      <PageHeader
        eyebrow="Workspace"
        title={greeting}
        subtitle="A real-time look at your content pipeline. Drafts, approvals, and published posts at a glance."
        actions={
          <>
            <Button
              variant="secondary"
              size="md"
              onClick={() => navigate('/drafts')}
              leftIcon={<NotebookPen className="h-4 w-4" />}
            >
              View Drafts
            </Button>
            <Button
              variant="brand"
              size="md"
              onClick={() => navigate('/create')}
              rightIcon={<ArrowRight className="h-4 w-4" />}
            >
              Create LinkedIn Post
            </Button>
          </>
        }
      />

      <ErrorBanner error={error} onRetry={load} />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {TILES.map((tile) => {
          const value = summary?.[tile.key];
          const Icon = tile.icon;
          return (
            <button
              key={tile.key}
              type="button"
              onClick={() => navigate(tile.href)}
              className="group panel relative flex flex-col gap-3 p-4 text-left transition hover:border-white/20 hover:bg-white/[0.04]"
            >
              <div className="flex items-center justify-between">
                <div className="text-sm text-text-secondary">{tile.label}</div>
                <span
                  className={
                    'flex h-8 w-8 items-center justify-center rounded-lg border ' +
                    {
                      neutral: 'border-white/10 bg-white/[0.03] text-text-secondary',
                      brand: 'border-brand-400/30 bg-brand-500/15 text-brand-300',
                      success: 'border-emerald-400/30 bg-emerald-500/15 text-emerald-300',
                      warning: 'border-amber-400/30 bg-amber-500/15 text-amber-300',
                      danger: 'border-rose-400/30 bg-rose-500/15 text-rose-300',
                      info: 'border-sky-400/30 bg-sky-500/15 text-sky-300',
                    }[tile.tone]
                  }
                  aria-hidden
                >
                  <Icon className="h-4 w-4" />
                </span>
              </div>
              <div className="text-3xl font-semibold tracking-tight text-white">
                {value === undefined ? (
                  <span className="inline-block h-7 w-12 rounded-md skeleton" />
                ) : (
                  value
                )}
              </div>
              <div className="absolute right-3 top-3 text-text-muted opacity-0 transition group-hover:opacity-100">
                <ArrowRight className="h-3.5 w-3.5" />
              </div>
            </button>
          );
        })}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Recent drafts</CardTitle>
                <CardDescription>Your five most recent drafts.</CardDescription>
              </div>
              <Button variant="ghost" size="sm" onClick={() => navigate('/drafts')}>
                All drafts <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {recentDrafts.length ? (
              <ul className="space-y-2">
                {recentDrafts.map((draft) => {
                  const status = draft.status || 'draft';
                  const tone = DRAFT_STATUS_TONE[status] || DRAFT_STATUS_TONE.draft;
                  const sourceType = draft.source_metadata?.source_type;
                  const sourceTone = sourceType ? SOURCE_TONE[sourceType] : null;
                  return (
                    <li key={draft.id}>
                      <Link
                        to={`/drafts/${draft.id}`}
                        className="group flex items-center gap-3 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 transition hover:border-white/15 hover:bg-white/[0.04]"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="truncate text-sm font-semibold text-zinc-100 group-hover:text-white">
                              {draft.title || 'Untitled draft'}
                            </span>
                            {sourceTone ? (
                              <Badge tone={sourceTone.label.toLowerCase()} size="xs">
                                {sourceTone.label}
                              </Badge>
                            ) : null}
                          </div>
                          <div className="mt-0.5 text-xs text-text-muted">
                            Updated {formatDateTime(draft.updated_at || draft.updatedAt)}
                          </div>
                        </div>
                        <Badge tone={tone.label.toLowerCase()} size="sm" withDot>
                          {DRAFT_STATUS_LABEL[status] || status}
                        </Badge>
                        <ArrowRight className="h-3.5 w-3.5 shrink-0 text-text-muted opacity-0 transition group-hover:opacity-100" />
                      </Link>
                    </li>
                  );
                })}
              </ul>
            ) : loading ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-14" />
                ))}
              </div>
            ) : (
              <EmptyState
                icon={<NotebookPen className="h-5 w-5" />}
                title="No drafts yet"
                description="Generate your first draft to see it here."
                action={
                  <Button
                    variant="brand"
                    size="sm"
                    onClick={() => navigate('/create')}
                    leftIcon={<CirclePlus className="h-4 w-4" />}
                  >
                    Create your first draft
                  </Button>
                }
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Recent activity</CardTitle>
                <CardDescription>Up to the latest 8 events.</CardDescription>
              </div>
              <Activity className="h-4 w-4 text-text-muted" />
            </div>
          </CardHeader>
          <CardContent>
            {summary?.recent_activity?.length ? (
              <ul className="space-y-3">
                {summary.recent_activity.slice(0, 8).map((activity, index) => (
                  <li key={`${activity.event_type}-${activity.timestamp}-${index}`} className="relative pl-4">
                    <span className="absolute left-0 top-2 h-1.5 w-1.5 rounded-full bg-brand-400" />
                    <div className="text-sm font-medium text-zinc-100">
                      {prettyEvent(activity.event_type)}
                    </div>
                    {activity.description ? (
                      <div className="mt-0.5 truncate text-xs text-text-secondary">
                        {activity.description}
                      </div>
                    ) : null}
                    <div className="mt-0.5 text-[11px] text-text-muted">
                      {formatDateTime(activity.timestamp)}
                    </div>
                  </li>
                ))}
              </ul>
            ) : loading ? (
              <div className="space-y-3">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-12" />
                ))}
              </div>
            ) : (
              <EmptyState
                size="sm"
                icon={<Inbox className="h-4 w-4" />}
                title="No recent activity"
                description="Activity will appear here once you start using the system."
              />
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Quick actions</CardTitle>
          <CardDescription>Jump to the next thing you probably need to do.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {QUICK_ACTIONS.map((action) => {
              const Icon = action.icon;
              return (
                <Link
                  key={action.href}
                  to={action.href}
                  className="group flex items-center gap-3 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 transition hover:border-white/15 hover:bg-white/[0.04]"
                >
                  <span
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] text-text-secondary group-hover:border-brand-400/30 group-hover:bg-brand-500/15 group-hover:text-brand-300"
                    aria-hidden
                  >
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-zinc-100">{action.label}</span>
                    <span className="block text-xs text-text-muted">{action.description}</span>
                  </span>
                  <ArrowRight className="ml-auto h-3.5 w-3.5 text-text-muted opacity-0 transition group-hover:opacity-100" />
                </Link>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function greetingForHour() {
  const hour = new Date().getHours();
  if (hour < 5) return 'Good evening';
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

function prettyEvent(eventType) {
  if (!eventType) return 'Activity';
  return eventType
    .toLowerCase()
    .split('_')
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ');
}
