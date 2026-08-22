import { useCallback, useEffect, useRef, useState } from 'react';
import { Check, Save, Globe, Mail, Clock, Server, Send } from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useToast } from '../context/ToastContext.jsx';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
  CardFooter,
} from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Select, Field } from '../components/ui/Input.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { PageHeader } from '../components/ui/PageHeader.jsx';
import { ErrorBanner, Spinner } from '../components/ui/Feedback.jsx';
import { LinkedInCard } from '../components/LinkedInCard.jsx';

const PUBLISHING_MODES = [
  { value: 'manual', label: 'Manual — publish only on explicit action' },
  { value: 'scheduled', label: 'Scheduled — honour scheduled times' },
];

const APPROVAL_MODES = [
  { value: 'email', label: 'Email — send an approval link' },
  { value: 'auto', label: 'Auto — approve on review-pass' },
  { value: 'manual', label: 'Manual — require explicit approval' },
];

const APPROVAL_TONE = {
  email: 'brand',
  auto: 'success',
  manual: 'warning',
};

export default function SettingsPage() {
  const api = useApi();
  const { toast } = useToast();
  const cancelledRef = useRef(false);

  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [health, setHealth] = useState(null);

  const [form, setForm] = useState({
    publishing_mode: 'manual',
    approval_mode: 'email',
    notification_email: '',
    timezone: '',
  });

  const load = useCallback(async () => {
    cancelledRef.current = false;
    setLoading(true);
    try {
      const data = await api.getSettings();
      if (cancelledRef.current) return;
      setSettings(data);
      setForm({
        publishing_mode: data.publishing_mode || 'manual',
        approval_mode: data.approval_mode || 'email',
        notification_email: data.notification_email || '',
        timezone: data.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone,
      });
      setDirty(false);
      setError(null);
    } catch (err) {
      if (!cancelledRef.current) setError(err);
    } finally {
      if (!cancelledRef.current) setLoading(false);
    }

    try {
      const h = await api.healthCheck();
      if (!cancelledRef.current) setHealth(h);
    } catch {
      if (!cancelledRef.current) setHealth({ status: 'unreachable' });
    }
  }, [api]);

  useEffect(() => {
    load();
    return () => {
      cancelledRef.current = true;
    };
  }, [load]);

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
    setDirty(true);
  }

  async function handleSave() {
    if (
      form.approval_mode === 'email'
      && (!form.notification_email || !form.notification_email.trim())
    ) {
      toast.error(
        'Notification email required',
        'Please enter a notification email for Email approval mode.',
      );
      return;
    }
    setSaving(true);
    try {
      const payload = {
        publishing_mode: form.publishing_mode,
        approval_mode: form.approval_mode,
        notification_email: form.notification_email || null,
        timezone: form.timezone || null,
      };
      const updated = await api.updateSettings(payload);
      setSettings(updated);
      setForm({
        publishing_mode: updated.publishing_mode || 'manual',
        approval_mode: updated.approval_mode || 'email',
        notification_email: updated.notification_email || '',
        timezone: updated.timezone || '',
      });
      setDirty(false);
      toast.success('Settings saved.');
    } catch (err) {
      toast.error('Save failed', err?.message);
    } finally {
      setSaving(false);
    }
  }

  const approvalNeedsEmail = form.approval_mode === 'email';
  const approvalTone = APPROVAL_TONE[form.approval_mode] || 'neutral';

  return (
    <div className="space-y-6 animate-fadeIn">
      <PageHeader
        eyebrow="Account"
        title="Settings"
        subtitle="Tune the workspace for your publishing workflow."
        actions={
          <Button
            variant="brand"
            size="md"
            onClick={handleSave}
            disabled={!dirty || loading}
            loading={saving}
            leftIcon={<Save className="h-4 w-4" />}
          >
            {dirty ? 'Save changes' : 'Saved'}
          </Button>
        }
      />

      <ErrorBanner error={error} onRetry={load} />

      <Card>
        <CardHeader>
          <CardTitle>LinkedIn</CardTitle>
          <CardDescription>Connection status for the publishing pipeline.</CardDescription>
        </CardHeader>
        <CardContent>
          <LinkedInCard />
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Publishing</CardTitle>
                <CardDescription>How drafts reach LinkedIn.</CardDescription>
              </div>
              <Send className="h-4 w-4 text-text-muted" aria-hidden />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field id="publishing-mode" label="Publishing mode">
              <Select
                id="publishing-mode"
                value={form.publishing_mode}
                onChange={(event) => update('publishing_mode', event.target.value)}
                disabled={loading}
              >
                {PUBLISHING_MODES.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </Select>
            </Field>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Approval</CardTitle>
                <CardDescription>How drafts get cleared for publishing.</CardDescription>
              </div>
              <Badge tone={approvalTone} size="sm" withDot>
                {form.approval_mode}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field id="approval-mode" label="Approval mode">
              <Select
                id="approval-mode"
                value={form.approval_mode}
                onChange={(event) => update('approval_mode', event.target.value)}
                disabled={loading}
              >
                {APPROVAL_MODES.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </Select>
              <div className="text-xs text-text-muted">
                {form.approval_mode === 'email' &&
                  'Newly generated posts will require approval via the notification email below.'}
                {form.approval_mode === 'auto' &&
                  'Posts that pass the reviewer are approved automatically. No email is sent.'}
                {form.approval_mode === 'manual' &&
                  'Posts always need explicit approval in the Approval queue.'}
              </div>
            </Field>

            <Field
              id="notification-email"
              label={
                <span className="flex items-center gap-1.5">
                  <Mail className="h-3.5 w-3.5 text-text-muted" />
                  Notification email
                  {approvalNeedsEmail ? (
                    <span className="text-rose-400">*</span>
                  ) : null}
                </span>
              }
              hint={
                approvalNeedsEmail
                  ? 'Required when Email approval mode is selected.'
                  : 'Only used when Email approval mode is selected.'
              }
            >
              <Input
                id="notification-email"
                type="email"
                value={form.notification_email}
                onChange={(event) => update('notification_email', event.target.value)}
                placeholder="you@example.com"
                disabled={loading}
                required={approvalNeedsEmail}
              />
            </Field>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Locale</CardTitle>
                <CardDescription>Timezone for scheduled publishing.</CardDescription>
              </div>
              <Clock className="h-4 w-4 text-text-muted" aria-hidden />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field
              id="timezone"
              label="Timezone (IANA)"
              hint={`Detected: ${Intl.DateTimeFormat().resolvedOptions().timeZone}`}
            >
              <Input
                id="timezone"
                value={form.timezone}
                onChange={(event) => update('timezone', event.target.value)}
                placeholder="Asia/Kolkata"
                disabled={loading}
                leftIcon={<Globe className="h-3.5 w-3.5" />}
              />
            </Field>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Backend health</CardTitle>
                <CardDescription>Live probe against /health.</CardDescription>
              </div>
              <Badge tone={health?.status === 'healthy' ? 'success' : 'danger'} size="sm" withDot>
                {health?.status || 'unknown'}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <Spinner />
            ) : (
              <pre className="max-h-48 overflow-auto rounded-xl border border-white/10 bg-black/30 p-3 font-mono text-xs text-zinc-300">
                {JSON.stringify(health, null, 2)}
              </pre>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
