import { useCallback, useEffect, useState } from 'react';
import { Trash2 } from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { EmptyState, ErrorBanner, Spinner } from '../components/ui/Feedback.jsx';
import { ConfirmDialog } from '../components/ConfirmDialog.jsx';
import { formatDateTime } from '../utils/date.js';

const POLL_INTERVAL_MS = 30000;

// Phase 8B P1 — STATUS_VARIANT now distinguishes ``failed`` from ``running``.
const STATUS_VARIANT = {
  pending: 'info',
  running: 'info',
  completed: 'success',
  failed: 'danger',
  cancelled: 'muted',
};

const STATUS_LABEL = {
  pending: 'Pending',
  running: 'Running',
  completed: 'Published',
  failed: 'Failed',
  cancelled: 'Cancelled',
};

export default function ScheduledPostsPage() {
  const api = useApi();
  const { toast } = useToast();
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [confirmId, setConfirmId] = useState(null);
  const [cancelling, setCancelling] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await api.getScheduledJobs();
      setJobs(Array.isArray(data) ? data : []);
      setError(null);
    } catch (err) {
      setError(err);
      setJobs([]);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    load();
    const interval = window.setInterval(load, POLL_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [load]);

  async function handleCancel() {
    if (!confirmId) return;
    setCancelling(true);
    try {
      await api.cancelScheduledJob(confirmId);
      toast.success('Schedule cancelled.');
      await load();
    } catch (err) {
      // Phase 8A envelope: err.message is the safe message.
      const code = err?.code;
      if (code === 'CONFLICT') {
        toast.error('Only pending jobs can be cancelled.');
      } else {
        toast.error('Cancel failed', err?.message);
      }
    } finally {
      setCancelling(false);
      setConfirmId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Scheduled Posts</h1>
        <p className="text-zinc-400">Review queued publishing jobs and cancel any that should not run.</p>
      </div>

      <ErrorBanner error={error} onRetry={load} />

      <Card>
        <CardHeader>
          <CardTitle>Upcoming & recent jobs</CardTitle>
          <CardDescription>{jobs.length} job{jobs.length === 1 ? '' : 's'}.</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <Spinner />
          ) : jobs.length ? (
            <div className="space-y-3">
              {jobs.map((job) => (
                <div
                  key={job.job_id}
                  className="rounded-2xl border border-white/10 bg-white/[0.03] p-4"
                >
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                      <div className="text-lg font-semibold text-zinc-100">
                        {job.title || 'Untitled'}
                      </div>
                      <div className="mt-1 text-sm text-zinc-400">
                        {job.scheduled_time
                          ? formatDateTime(job.scheduled_time)
                          : 'No time set'}
                      </div>
                      {job.last_error ? (
                        <div className="mt-1 text-xs text-rose-300">
                          Last error: {job.last_error}
                        </div>
                      ) : null}
                    </div>
                    <Badge variant={STATUS_VARIANT[job.status] || 'muted'}>
                      {STATUS_LABEL[job.status] || job.status}
                    </Badge>
                  </div>
                  {job.status === 'pending' ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setConfirmId(job.job_id)}
                      >
                        <Trash2 className="h-4 w-4" /> Cancel
                      </Button>
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No scheduled jobs"
              description="Schedule a draft from the viewer to populate this list."
            />
          )}
        </CardContent>
      </Card>

      <ConfirmDialog
        open={Boolean(confirmId)}
        title="Cancel this scheduled job?"
        description="The job will not run. The draft itself is preserved."
        confirmLabel="Cancel job"
        danger
        confirming={cancelling}
        onConfirm={handleCancel}
        onCancel={() => setConfirmId(null)}
      />
    </div>
  );
}
