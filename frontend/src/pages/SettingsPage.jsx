import { useCallback, useEffect, useRef, useState } from 'react';

import { useApi } from '../services/api/backend.js';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Select } from '../components/ui/Input.jsx';
import { ErrorBanner, Spinner } from '../components/ui/Feedback.jsx';
import { LinkedInCard } from '../components/LinkedInCard.jsx';

const PUBLISHING_MODES = [
  { value: 'manual', label: 'Manual — publish only on explicit action' },
  { value: 'scheduled', label: 'Scheduled — honour scheduled times' },
];

const APPROVAL_MODES = [
  { value: 'email', label: 'Email — send approval link' },
  { value: 'auto', label: 'Auto — approve on review-pass' },
  { value: 'manual', label: 'Manual — require explicit approval' },
];

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

    // Phase 8B: keep the existing /health probe — useful diagnostic.
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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Settings</h1>
        <p className="text-zinc-400">Tune the workspace for your publishing workflow.</p>
      </div>

      <ErrorBanner error={error} onRetry={load} />

      <LinkedInCard />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Publishing</CardTitle>
            <CardDescription>How drafts reach LinkedIn.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <label className="mb-1 block text-sm">Publishing mode</label>
              <Select
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
            </div>
            <div>
              <label className="mb-1 block text-sm">Approval mode</label>
              <Select
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
            </div>
            <div>
              <label className="mb-1 block text-sm">Notification email</label>
              <Input
                type="email"
                value={form.notification_email}
                onChange={(event) => update('notification_email', event.target.value)}
                placeholder="you@example.com"
                disabled={loading}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Locale</CardTitle>
            <CardDescription>Timezone for scheduled publishing.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <label className="mb-1 block text-sm">Timezone (IANA)</label>
              <Input
                value={form.timezone}
                onChange={(event) => update('timezone', event.target.value)}
                placeholder="Asia/Kolkata"
                disabled={loading}
              />
              <p className="mt-1 text-xs text-zinc-500">
                Detected: {Intl.DateTimeFormat().resolvedOptions().timeZone}
              </p>
            </div>
            <div className="flex justify-end">
              <Button onClick={handleSave} disabled={!dirty || loading} loading={saving}>
                {dirty ? 'Save changes' : 'Saved'}
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Backend health</CardTitle>
            <CardDescription>Live probe against /health.</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <Spinner />
            ) : (
              <div className="space-y-2 text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-zinc-400">Status</span>
                  <span
                    className={
                      health?.status === 'healthy'
                        ? 'text-emerald-300'
                        : 'text-rose-300'
                    }
                  >
                    {health?.status || 'unknown'}
                  </span>
                </div>
                <pre className="overflow-auto rounded-xl border border-white/10 bg-black/30 p-3 font-mono text-xs text-zinc-300">
                  {JSON.stringify(health, null, 2)}
                </pre>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
