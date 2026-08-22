import { useCallback, useEffect, useState } from 'react';
import { Trash2, CalendarClock, Inbox, AlertTriangle, RotateCw, CheckCircle2 } from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { PageHeader } from '../components/ui/PageHeader.jsx';
import { EmptyState, ErrorBanner, Skeleton } from '../components/ui/Feedback.jsx';
import { ConfirmDialog } from '../components/ConfirmDialog.jsx';
import { formatDateTime } from '../utils/date.js';
import { DRAFT_STATUS_TONE, DRAFT_STATUS_LABEL } from '../utils/design.js';

const POLL_INTERVAL_MS = 30000;

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
    <div className="space-y-6 animate-fadeIn">
      <PageHeader
        eyebrow="Publishing"
        title="Scheduled Posts"
        subtitle="Review queued publishing jobs and cancel any that should not run."
      />

      <ErrorBanner error={error} onRetry={load} />

      {loading && !jobs.length ? (
        <div className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </div>
      ) : jobs.length ? (
        <div className="space-y-2">
          {jobs.map((job) => {
            const status = job.status || 'pending';
            const tone = DRAFT_STATUS_TONE[status] || DRAFT_STATUS_TONE.pending;
            return (
              <div
                key={job.job_id}
                className="panel flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <CalendarClock className="h-4 w-4 shrink-0 text-text-muted" />
                    <div className="truncate text-sm font-semibold text-white">
                      {job.title || 'Untitled job'}
                    </div>
                  </div>
                  <div className="mt-1 text-xs text-text-muted">
                    {job.scheduled_time
                      ? formatDateTime(job.scheduled_time)
                      : 'No time set'}
                  </div>
                  {job.last_error ? (
                    <div className="mt-1 flex items-center gap-1 text-xs text-rose-300">
                      <AlertTriangle className="h-3 w-3" />
                      {job.last_error}
                    </div>
                  ) : null}
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={tone.label.toLowerCase()} size="sm" withDot>
                    {DRAFT_STATUS_LABEL[status] || status}
                  </Badge>
                  {status === 'pending' ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setConfirmId(job.job_id)}
                      leftIcon={<Trash2 className="h-3.5 w-3.5" />}
                    >
                      Cancel
                    </Button>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <Card>
          <CardContent>
            <EmptyState
              icon={<CalendarClock className="h-5 w-5" />}
              title="No scheduled jobs"
              description="Schedule a draft from the viewer to populate this list."
            />
          </CardContent>
        </Card>
      )}

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
