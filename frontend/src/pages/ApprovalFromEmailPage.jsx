import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { CheckCircle2, AlertCircle, X, FileText } from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { Button } from '../components/ui/Button.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from '../components/ui/Card.jsx';
import { PageHeader } from '../components/ui/PageHeader.jsx';
import { Spinner, ErrorBanner } from '../components/ui/Feedback.jsx';

/**
 * ApprovalFromEmailPage
 *
 * Handles the landing flow when the user clicks
 * "Approve & Publish" or "Review Draft" in the approval email.
 *
 * URL:  /approve?token=<approval_token>
 *
 * Behaviour:
 *   1. On mount, read ``?token=...``.
 *   2. If valid → POST /api/v1/approval/approve with the token.
 *   3. Show a polished result card:
 *        - Success:  ✓ Post approved and published successfully
 *                    (with link to the published draft)
 *        - Approved but publish failed: ⚠ Approved, but LinkedIn publish failed
 *                    (with a "Open Draft" CTA to retry)
 *        - Already processed: this approval has already been processed
 *        - Invalid / expired: friendly error with "Open Approval Queue" CTA
 *
 *   4. NO approval secret is ever echoed in the URL, audit, or
 *      browser console beyond the token the backend owns. The token
 *      is single-use and 24h-expiring.
 */
export default function ApprovalFromEmailPage() {
  const api = useApi();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const token = searchParams.get('token') || searchParams.get('approval_token');
  const [state, setState] = useState('pending'); // pending | success | failed | already | invalid
  const [message, setMessage] = useState('');
  const [draftId, setDraftId] = useState(null);
  const [error, setError] = useState(null);

  const run = useCallback(async () => {
    if (!token) {
      setState('invalid');
      setMessage('Missing approval token.');
      return;
    }
    setState('pending');
    setError(null);
    try {
      const result = await api.approveDraft({ token });
      // Look up the draft for navigation.
      try {
        const draft = await api.getApprovalDraft(token);
        if (draft && draft.draft_id) setDraftId(draft.draft_id);
      } catch {
        // non-fatal — the approve result still tells us what happened.
      }
      if (result && result.success) {
        setState('success');
        setMessage(result.message || 'Post approved and published successfully.');
      } else if (result && /already/i.test(result.message || '')) {
        setState('already');
        setMessage(result.message || 'This approval has already been processed.');
      } else {
        setState('failed');
        setMessage(
          result?.message ||
            'Post was approved, but LinkedIn publish failed. Use the Draft viewer to retry.'
        );
      }
    } catch (err) {
      setError(err);
      const detail = err?.message || 'Unknown error.';
      // 404 / cross-user / expired token — all surface as "invalid".
      if (err?.status === 404 || /not found|expired|invalid/i.test(detail)) {
        setState('invalid');
        setMessage(
          'This approval request has expired or has already been consumed. Please open the application to review the latest draft.'
        );
      } else {
        setState('failed');
        setMessage(detail);
      }
    }
  }, [api, token]);

  useEffect(() => {
    run();
  }, [run]);

  return (
    <div className="space-y-6 animate-fadeIn">
      <PageHeader
        eyebrow="Workspace"
        title="Email approval"
        subtitle="One-click approval from your email."
      />

      <div className="mx-auto max-w-2xl">
        {state === 'pending' ? (
          <Card>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-3">
                <Spinner />
                <div>
                  <div className="text-sm font-medium text-white">Validating your approval…</div>
                  <div className="text-xs text-text-muted">
                    Verifying the approval token, then publishing to LinkedIn.
                  </div>
                </div>
              </div>
              <ProgressSteps active="approving" />
            </CardContent>
          </Card>
        ) : null}

        {state === 'success' ? (
          <ResultCard
            tone="success"
            title="Post approved and published"
            message={message}
            icon={<CheckCircle2 className="h-5 w-5" />}
            primaryAction={
              draftId
                ? { label: 'Open published draft', onClick: () => navigate(`/drafts/${draftId}`) }
                : { label: 'View drafts', onClick: () => navigate('/drafts') }
            }
            secondaryAction={
              draftId
                ? { label: 'View approval queue', onClick: () => navigate('/approval') }
                : null
            }
          />
        ) : null}

        {state === 'already' ? (
          <ResultCard
            tone="info"
            title="Already processed"
            message={message}
            icon={<CheckCircle2 className="h-5 w-5" />}
            primaryAction={
              draftId
                ? { label: 'Open draft', onClick: () => navigate(`/drafts/${draftId}`) }
                : { label: 'View drafts', onClick: () => navigate('/drafts') }
            }
          />
        ) : null}

        {state === 'failed' ? (
          <ResultCard
            tone="warning"
            title="Approved, but publishing failed"
            message={message}
            icon={<AlertCircle className="h-5 w-5" />}
            primaryAction={
              draftId
                ? {
                    label: 'Open draft to retry',
                    onClick: () => navigate(`/drafts/${draftId}`),
                  }
                : { label: 'View drafts', onClick: () => navigate('/drafts') }
            }
            secondaryAction={
              { label: 'View approval queue', onClick: () => navigate('/approval') }
            }
          />
        ) : null}

        {state === 'invalid' ? (
          <ResultCard
            tone="danger"
            title="This approval is no longer valid"
            message={message}
            icon={<X className="h-5 w-5" />}
            primaryAction={
              { label: 'View approval queue', onClick: () => navigate('/approval') }
            }
            secondaryAction={
              { label: 'View drafts', onClick: () => navigate('/drafts') }
            }
          />
        ) : null}

        <ErrorBanner error={error} onRetry={run} />
      </div>
    </div>
  );
}

const TONES = {
  success: {
    wrap: 'border-emerald-500/30 bg-emerald-500/[0.06]',
    title: 'text-emerald-100',
    body: 'text-emerald-200/80',
    icon: 'text-emerald-300',
  },
  info: {
    wrap: 'border-sky-500/30 bg-sky-500/[0.06]',
    title: 'text-sky-100',
    body: 'text-sky-200/80',
    icon: 'text-sky-300',
  },
  warning: {
    wrap: 'border-amber-500/30 bg-amber-500/[0.06]',
    title: 'text-amber-100',
    body: 'text-amber-200/80',
    icon: 'text-amber-300',
  },
  danger: {
    wrap: 'border-rose-500/30 bg-rose-500/[0.06]',
    title: 'text-rose-100',
    body: 'text-rose-200/80',
    icon: 'text-rose-300',
  },
};

function ResultCard({ tone, title, message, icon, primaryAction, secondaryAction }) {
  const t = TONES[tone] || TONES.info;
  return (
    <Card className={t.wrap}>
      <CardHeader>
        <div className="flex items-center gap-3">
          <span className={`flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] ${t.icon}`}>
            {icon}
          </span>
          <div>
            <CardTitle className={t.title}>{title}</CardTitle>
            <CardDescription className={t.body}>{message}</CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardFooter>
        <Button variant="ghost" onClick={secondaryAction.onClick}>
          {secondaryAction.label}
        </Button>
        <Button
          variant={tone === 'danger' ? 'outline' : 'brand'}
          onClick={primaryAction.onClick}
        >
          {primaryAction.label}
        </Button>
      </CardFooter>
    </Card>
  );
}

function ProgressSteps({ active }) {
  const steps = [
    { id: 'validating', label: 'Validating approval' },
    { id: 'approving', label: 'Publishing to LinkedIn' },
    { id: 'finalizing', label: 'Finalizing' },
  ];
  const activeIdx = steps.findIndex((s) => s.id === active);
  return (
    <ol className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
      {steps.map((step, idx) => {
        const state = idx < activeIdx ? 'done' : idx === activeIdx ? 'active' : 'pending';
        return (
          <li key={step.id} className="flex items-center gap-2 text-xs">
            <span
              className={
                'flex h-6 w-6 items-center justify-center rounded-full border ' +
                (state === 'done'
                  ? 'border-emerald-400/30 bg-emerald-500/15 text-emerald-300'
                  : state === 'active'
                  ? 'border-brand-400/40 bg-brand-500/20 text-brand-200'
                  : 'border-white/10 bg-white/[0.03] text-text-muted')
              }
            >
              {state === 'done' ? (
                <CheckCircle2 className="h-3.5 w-3.5" />
              ) : state === 'active' ? (
                <Spinner size="xs" />
              ) : (
                <FileText className="h-3.5 w-3.5" />
              )}
            </span>
            <span
              className={
                state === 'pending' ? 'text-text-muted' : 'text-zinc-200'
              }
            >
              {step.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
