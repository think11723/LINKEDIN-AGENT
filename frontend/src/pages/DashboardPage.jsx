import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowRight, NotebookPen, FileCheck2, CalendarClock, Newspaper, AlertTriangle, CheckCircle2 } from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { ErrorBanner, Spinner, EmptyState } from '../components/ui/Feedback.jsx';
import { formatDateTime } from '../utils/date.js';

const POLL_INTERVAL_MS = 15000;

const TILES = [
  { key: 'drafts_count', label: 'Total drafts', icon: NotebookPen, href: '/drafts' },
  { key: 'approval_queue_count', label: 'Needs review', icon: FileCheck2, href: '/approval' },
  { key: 'approved_count', label: 'Approved', icon: CheckCircle2, href: '/drafts?status=approved' },
  { key: 'scheduled_count', label: 'Scheduled', icon: CalendarClock, href: '/scheduled-posts' },
  { key: 'published_count', label: 'Published', icon: Newspaper, href: '/published-posts' },
  { key: 'failed_count', label: 'Failed', icon: AlertTriangle, href: '/scheduled-posts' },
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

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-semibold">Dashboard</h1>
          <p className="text-zinc-400">Live view of your drafts, approvals, and publishing performance.</p>
        </div>
        <Button onClick={() => navigate('/create')}>
          New Post
          <ArrowRight className="h-4 w-4" />
        </Button>
      </div>

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
              className="rounded-2xl border border-white/10 bg-zinc-950/60 p-4 text-left transition hover:border-violet-500/50"
            >
              <div className="flex items-center justify-between">
                <div className="text-sm text-zinc-400">{tile.label}</div>
                <Icon className="h-4 w-4 text-zinc-500" />
              </div>
              <div className="mt-2 text-2xl font-semibold text-white">
                {value === undefined ? <Spinner /> : value}
              </div>
            </button>
          );
        })}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent drafts</CardTitle>
            <CardDescription>Your five most recent drafts.</CardDescription>
          </CardHeader>
          <CardContent>
            {recentDrafts.length ? (
              <ul className="space-y-2 text-sm">
                {recentDrafts.map((draft) => (
                  <li
                    key={draft.id}
                    className="rounded-xl border border-white/10 bg-white/[0.03] p-3"
                  >
                    <Link
                      to={`/drafts/${draft.id}`}
                      className="font-medium text-zinc-100 hover:text-violet-200"
                    >
                      {draft.title || 'Untitled'}
                    </Link>
                    <div className="mt-1 text-xs text-zinc-500">
                      Updated {formatDateTime(draft.updated_at || draft.updatedAt)}
                    </div>
                  </li>
                ))}
              </ul>
            ) : loading ? (
              <Spinner />
            ) : (
              <EmptyState
                title="No drafts yet"
                description="Generate your first draft to see it here."
                action={
                  <Button size="sm" onClick={() => navigate('/create')}>
                    Create your first draft
                  </Button>
                }
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent activity</CardTitle>
            <CardDescription>Up to the latest 8 events.</CardDescription>
          </CardHeader>
          <CardContent>
            {summary?.recent_activity?.length ? (
              <ul className="space-y-2 text-sm text-zinc-300">
                {summary.recent_activity.map((activity, index) => (
                  <li
                    key={`${activity.event_type}-${activity.timestamp}-${index}`}
                    className="rounded-xl border border-white/10 bg-white/[0.03] p-3"
                  >
                    <div className="font-medium text-zinc-100">{activity.event_type}</div>
                    <div className="mt-1 text-zinc-300">{activity.description}</div>
                    <div className="mt-2 text-xs text-zinc-500">{activity.timestamp}</div>
                  </li>
                ))}
              </ul>
            ) : loading ? (
              <Spinner />
            ) : (
              <EmptyState
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
        </CardHeader>
        <CardContent>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { label: 'Generate draft', href: '/create' },
              { label: 'Review approvals', href: '/approval' },
              { label: 'Scheduled jobs', href: '/scheduled-posts' },
              { label: 'Published', href: '/published-posts' },
            ].map((action) => (
              <Link
                key={action.href}
                to={action.href}
                className="rounded-xl border border-white/10 bg-white/[0.03] p-3 text-sm text-zinc-200 transition hover:border-violet-500/40 hover:text-violet-200"
              >
                {action.label}
              </Link>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
