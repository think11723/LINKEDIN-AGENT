import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Briefcase,
  Plus,
  ArrowRight,
  TrendingUp,
  Activity,
  BarChart3,
  Upload,
  Inbox,
  Clock,
} from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { EmptyState, ErrorBanner, Skeleton } from '../components/ui/Feedback.jsx';
import { MotionPage } from '../components/ui/MotionPage.jsx';
import { formatDateTime } from '../utils/date.js';
import { cn } from '../utils/cn.js';

const KANBAN_COLUMNS = [
  { key: 'saved', label: 'Saved' },
  { key: 'preparing', label: 'Preparing' },
  { key: 'applied', label: 'Applied' },
  { key: 'screening', label: 'Screening' },
  { key: 'interview', label: 'Interview' },
  { key: 'offer', label: 'Offer' },
  { key: 'rejected', label: 'Rejected' },
  { key: 'withdrawn', label: 'Withdrawn' },
];

const STATUS_TONE = {
  saved: 'neutral',
  preparing: 'warning',
  applied: 'brand',
  screening: 'accent',
  interview: 'success',
  offer: 'success',
  rejected: 'danger',
  withdrawn: 'muted',
};

const STATUS_LABEL = {
  saved: 'Saved',
  preparing: 'Preparing',
  applied: 'Applied',
  screening: 'Screening',
  interview: 'Interview',
  offer: 'Offer',
  rejected: 'Rejected',
  withdrawn: 'Withdrawn',
};

function StatCard({ label, value, icon: Icon, tone = 'brand' }) {
  const toneClass = {
    brand: 'text-brand-300 bg-brand-500/15 border-brand-400/20',
    accent: 'text-accent-400 bg-accent-500/15 border-accent-400/20',
    success: 'text-emerald-300 bg-emerald-500/15 border-emerald-400/20',
    info: 'text-sky-300 bg-sky-500/15 border-sky-400/20',
  }[tone];
  return (
    <motion.div
      whileHover={{ y: -2 }}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
      className="panel relative flex flex-col gap-3 p-5"
    >
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">
          {label}
        </div>
        <span
          className={cn(
            'inline-flex h-9 w-9 items-center justify-center rounded-xl border',
            toneClass
          )}
        >
          <Icon className="h-4 w-4" />
        </span>
      </div>
      <div className="text-3xl font-semibold tracking-tight text-white">
        {value}
      </div>
    </motion.div>
  );
}

function ApplicationCard({ app, onOpen, onStatusChange }) {
  const status = app.status || 'saved';
  const tone = STATUS_TONE[status] || 'neutral';
  const [pending, setPending] = useState(false);
  return (
    <motion.button
      type="button"
      whileHover={{ y: -2 }}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
      onClick={() => onOpen(app.id)}
      className="panel group flex w-full flex-col gap-2 p-3 text-left transition hover:border-white/[0.16] hover:bg-white/[0.04]"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold text-zinc-100">
            {app.job_title || 'Untitled role'}
          </div>
          <div className="truncate text-xs text-text-muted">
            {app.job_company || '—'}
          </div>
        </div>
        <Badge tone={tone} size="sm">
          {STATUS_LABEL[status] || status}
        </Badge>
      </div>
      {app.next_action ? (
        <div className="flex items-center gap-1 truncate text-[11px] text-text-muted">
          <Clock className="h-3 w-3 shrink-0" />
          <span className="truncate">
            {app.next_action}
            {app.next_action_date ? ` · ${app.next_action_date}` : ''}
          </span>
        </div>
      ) : null}
      <div className="flex items-center justify-between gap-2 pt-1">
        <div className="text-[11px] text-text-muted">
          {formatDateTime(app.updated_at)}
        </div>
        <select
          value={status}
          disabled={pending}
          onClick={(e) => e.stopPropagation()}
          onChange={async (e) => {
            e.stopPropagation();
            setPending(true);
            try {
              await onStatusChange(app.id, e.target.value);
            } finally {
              setPending(false);
            }
          }}
          className="rounded-md border border-white/[0.08] bg-white/[0.04] px-1.5 py-0.5 text-[10px] text-text-muted focus:border-brand-400/40 focus:outline-none"
        >
          {KANBAN_COLUMNS.map((col) => (
            <option key={col.key} value={col.key}>
              {col.label}
            </option>
          ))}
        </select>
      </div>
    </motion.button>
  );
}

function KanbanColumn({ column, applications, onOpen, onStatusChange }) {
  const items = applications.filter((a) => (a.status || 'saved') === column.key);
  return (
    <div className="flex h-full min-w-72 flex-col gap-2">
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2">
          <Badge tone={STATUS_TONE[column.key] || 'neutral'} size="sm">
            {column.label}
          </Badge>
          <span className="text-xs text-text-muted">{items.length}</span>
        </div>
      </div>
      <div className="flex flex-1 flex-col gap-2 overflow-y-auto pr-1 scrollbar-thin">
        {items.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-white/[0.06] p-3 text-center text-[11px] text-text-muted">
            No applications
          </div>
        ) : (
          items.map((a) => (
            <ApplicationCard
              key={a.id}
              app={a}
              onOpen={onOpen}
              onStatusChange={onStatusChange}
            />
          ))
        )}
      </div>
    </div>
  );
}

export default function JobTrackerPage() {
  const api = useApi();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [stats, setStats] = useState(null);
  const [applications, setApplications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [view, setView] = useState('kanban');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [d, apps] = await Promise.all([
        api.applicationDashboard().catch(() => null),
        api.listApplications().catch(() => []),
      ]);
      setStats(d);
      setApplications(Array.isArray(apps) ? apps : []);
      setError(null);
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleStatusChange(id, status) {
    try {
      await api.updateApplication(id, { status });
      toast.success(`Status set to ${STATUS_LABEL[status] || status}`);
      await load();
    } catch (e) {
      toast.error('Update failed', e?.message);
    }
  }

  const groups = useMemo(() => {
    const out = {};
    for (const col of KANBAN_COLUMNS) {
      out[col.key] = applications.filter(
        (a) => (a.status || 'saved') === col.key
      );
    }
    return out;
  }, [applications]);

  return (
    <MotionPage className="space-y-6 p-4 md:p-6 lg:p-8">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-text-secondary">
            <Briefcase className="h-3 w-3 text-accent-400" />
            Job Tracker
          </div>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            <span className="text-text-secondary">AI </span>
            <span className="gradient-text">Application Studio</span>
          </h1>
          <p className="mt-1 max-w-xl text-sm text-text-secondary">
            Job → JD analysis → Resume matching → Optimization →
            Application → LinkedIn. One workflow, not a stack of
            disconnected pages.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            size="md"
            onClick={() => navigate('/jobs/import')}
            leftIcon={<Upload className="h-4 w-4" />}
          >
            Import job
          </Button>
          <Button
            variant="brand"
            size="md"
            onClick={() => navigate('/jobs/new')}
            leftIcon={<Plus className="h-4 w-4" />}
          >
            Add job manually
          </Button>
        </div>
      </header>

      <ErrorBanner error={error} onRetry={load} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Applications"
          value={applications.length}
          icon={Briefcase}
          tone="brand"
        />
        <StatCard
          label="This week"
          value={stats?.applications_this_week ?? 0}
          icon={TrendingUp}
          tone="accent"
        />
        <StatCard
          label="Interviews"
          value={stats?.counts?.interview ?? 0}
          icon={Activity}
          tone="info"
        />
        <StatCard
          label="Offers"
          value={stats?.counts?.offer ?? 0}
          icon={BarChart3}
          tone="success"
        />
      </div>

      <div className="flex items-center justify-between">
        <div className="text-xs text-text-muted">
          {stats?.interview_rate !== null && stats?.interview_rate !== undefined ? (
            <>
              Interview rate{' '}
              <span className="text-zinc-200">{stats.interview_rate}%</span> ·
              Offer rate{' '}
              <span className="text-zinc-200">{stats.offer_rate ?? '—'}%</span> ·
              Avg ATS <span className="text-zinc-200">{stats.average_ats || '—'}</span>
            </>
          ) : (
            'Insufficient data for rates — apply to a few jobs first.'
          )}
        </div>
        <div className="glass-inset inline-flex items-center gap-1 rounded-2xl p-1">
          {[
            { value: 'kanban', label: 'Kanban' },
            { value: 'list', label: 'List' },
          ].map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => setView(opt.value)}
              className={cn(
                'rounded-xl px-3 py-1 text-xs font-medium transition',
                view === opt.value
                  ? 'bg-white/[0.08] text-zinc-100'
                  : 'text-text-muted hover:text-zinc-200'
              )}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex gap-3 overflow-x-auto pb-3">
          {KANBAN_COLUMNS.slice(0, 4).map((col) => (
            <Skeleton key={col.key} className="h-48 w-72 shrink-0" />
          ))}
        </div>
      ) : applications.length === 0 ? (
        <EmptyState
          icon={<Inbox className="h-5 w-5" />}
          title="No applications yet"
          description="Import a job, or add one manually. Applications show up here in real time as you progress through your pipeline."
          action={
            <Button
              variant="brand"
              onClick={() => navigate('/jobs/import')}
              leftIcon={<Upload className="h-4 w-4" />}
            >
              Import a job
            </Button>
          }
        />
      ) : view === 'kanban' ? (
        <div className="flex gap-3 overflow-x-auto pb-3">
          {KANBAN_COLUMNS.map((col) => (
            <KanbanColumn
              key={col.key}
              column={col}
              applications={groups[col.key] || []}
              onOpen={(id) => navigate(`/jobs/${id}`)}
              onStatusChange={handleStatusChange}
            />
          ))}
        </div>
      ) : (
        <Card>
          <CardContent>
            <ul className="space-y-2">
              {applications.map((a) => (
                <li
                  key={a.id}
                  className="flex items-center gap-3 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-3"
                >
                  <button
                    type="button"
                    onClick={() => navigate(`/jobs/${a.id}`)}
                    className="flex flex-1 items-center gap-3 text-left"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-semibold text-zinc-100">
                        {a.job_title || 'Untitled role'}
                      </div>
                      <div className="truncate text-xs text-text-muted">
                        {a.job_company || '—'}
                      </div>
                    </div>
                    <Badge tone={STATUS_TONE[a.status] || 'neutral'} size="sm">
                      {STATUS_LABEL[a.status] || a.status}
                    </Badge>
                    <ArrowRight className="h-3.5 w-3.5 text-text-muted" />
                  </button>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </MotionPage>
  );
}
