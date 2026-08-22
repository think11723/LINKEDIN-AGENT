import { useCallback, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  CalendarClock,
  CheckCircle2,
  AlertCircle,
  Clock,
  Send,
  Inbox,
  ArrowRight,
} from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { EmptyState, ErrorBanner, Skeleton } from '../components/ui/Feedback.jsx';
import { MotionPage } from '../components/ui/MotionPage.jsx';
import { formatDateTime } from '../utils/date.js';

const POLL_INTERVAL_MS = 20000;

const STATUS_META = {
  pending: { tone: 'warning', label: 'Pending' },
  running: { tone: 'info', label: 'Running' },
  completed: { tone: 'success', label: 'Completed' },
  failed: { tone: 'danger', label: 'Failed' },
  cancelled: { tone: 'neutral', label: 'Cancelled' },
};

export default function ScheduledPostsPage() {
  const api = useApi();
  const { toast } = useToast();
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [confirmId, setConfirmId] = useState(null);
  const [cancelling, setCancelling] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await api.getScheduledJobs();
      setJobs(Array.isArray(data) ? data : []);
      setErr(null);
    } catch (e) {
      setErr(e);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    load();
    const t = window.setInterval(load, POLL_INTERVAL_MS);
    return () => window.clearInterval(t);
  }, [load]);

  async function handleCancel() {
    if (!confirmId) return;
    setCancelling(true);
    try {
      await api.cancelScheduledJob(confirmId);
      toast.success('Schedule cancelled.');
      await load();
    } catch (e) {
      const code = e?.code;
      if (code === 'CONFLICT') toast.error('Only pending jobs can be cancelled.');
      else toast.error('Cancel failed', e?.message);
    } finally {
      setCancelling(false);
      setConfirmId(null);
    }
  }

  return (
    <MotionPage className="space-y-6 p-4 md:p-6 lg:p-8">
      <header>
        <div className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-text-secondary">
          <CalendarClock className="h-3 w-3 text-info-300" />
          Publishing
        </div>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
          <span className="text-text-secondary">Scheduled </span>
          <span className="gradient-text">posts</span>
        </h1>
        <p className="mt-1 text-sm text-text-secondary">
          {loading && jobs.length === 0
            ? 'Loading scheduled jobs…'
            : `${jobs.length} scheduled job${jobs.length === 1 ? '' : 's'}.`}
        </p>
      </header>

      <ErrorBanner error={err} onRetry={load} />

      {loading && jobs.length === 0 ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, idx) => (
            <Skeleton key={idx} className="h-20" />
          ))}
        </div>
      ) : jobs.length === 0 ? (
        <EmptyState
          icon={<Inbox className="h-5 w-5" />}
          title="Nothing scheduled"
          description="Schedule a draft from the viewer to populate this list."
        />
      ) : (
        <ul className="space-y-3">
          {jobs.map((job, idx) => {
            const meta = STATUS_META[job.status] || STATUS_META.pending;
            return (
              <motion.li
                key={job.job_id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.04, duration: 0.22 }}
              >
                <Card hoverable>
                  <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-center gap-3">
                      <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-white/[0.08] bg-white/[0.04] text-text-secondary">
                        <Clock className="h-4 w-4" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-semibold text-zinc-100">
                          {job.title || 'Untitled job'}
                        </div>
                        <div className="text-xs text-text-muted">
                          {job.scheduled_time
                            ? formatDateTime(job.scheduled_time)
                            : 'No time set'}
                        </div>
                        {job.last_error ? (
                          <div className="mt-0.5 flex items-center gap-1 text-xs text-rose-300">
                            <AlertCircle className="h-3 w-3" />
                            {job.last_error}
                          </div>
                        ) : null}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge tone={meta.tone} size="sm" withDot>
                        {meta.label}
                      </Badge>
                      {job.status === 'pending' ? (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setConfirmId(job.job_id)}
                          loading={cancelling}
                        >
                          Cancel
                        </Button>
                      ) : null}
                    </div>
                  </CardContent>
                </Card>
              </motion.li>
            );
          })}
        </ul>
      )}

      <ConfirmModal
        open={Boolean(confirmId)}
        title="Cancel this scheduled job?"
        description="The job will not run. The draft itself is preserved."
        confirmLabel="Cancel job"
        danger
        confirming={cancelling}
        onConfirm={handleCancel}
        onCancel={() => setConfirmId(null)}
      />
    </MotionPage>
  );
}

import { ConfirmDialog } from '../components/ConfirmDialog.jsx';
function Boolean(value) {
  return Boolean(value);
}
function ConfirmModal(props) {
  return <ConfirmDialog {...props} />;
}
