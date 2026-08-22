import { useCallback, useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Check,
  Save,
  Globe,
  Mail,
  Clock,
  Server,
  Send,
  Linkedin,
  Sparkles,
  User,
  Bell,
  Shield,
  ImageIcon,
  Heart,
  Settings as SettingsIcon,
} from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Select, Field } from '../components/ui/Input.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { ErrorBanner, Skeleton } from '../components/ui/Feedback.jsx';
import { MotionPage } from '../components/ui/MotionPage.jsx';
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

const SECTIONS = [
  { id: 'profile', label: 'Profile', icon: User },
  { id: 'linkedin', label: 'LinkedIn', icon: Linkedin },
  { id: 'ai', label: 'AI Preferences', icon: Sparkles },
  { id: 'approval', label: 'Approval', icon: Mail },
  { id: 'publishing', label: 'Publishing', icon: Send },
  { id: 'notifications', label: 'Notifications', icon: Bell },
  { id: 'security', label: 'Security', icon: Shield },
  { id: 'general', label: 'General', icon: SettingsIcon },
];

export default function SettingsPage() {
  const api = useApi();
  const { toast } = useToast();
  const cancelledRef = useRef(false);

  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [health, setHealth] = useState(null);
  const [active, setActive] = useState('profile');

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
        timezone:
          data.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone,
      });
      setDirty(false);
      setErr(null);
    } catch (e) {
      if (!cancelledRef.current) setErr(e);
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
    if (form.approval_mode === 'email' && !form.notification_email?.trim()) {
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
      setForm((current) => ({
        ...current,
        publishing_mode: updated.publishing_mode || 'manual',
        approval_mode: updated.approval_mode || 'email',
        notification_email: updated.notification_email || '',
        timezone: updated.timezone || '',
      }));
      setDirty(false);
      toast.success('Settings saved.');
    } catch (e) {
      toast.error('Save failed', e?.message);
    } finally {
      setSaving(false);
    }
  }

  const approvalTone = APPROVAL_TONE[form.approval_mode] || 'neutral';
  const approvalNeedsEmail = form.approval_mode === 'email';

  return (
    <MotionPage className="space-y-6 p-4 md:p-6 lg:p-8">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-text-secondary">
            <SettingsIcon className="h-3 w-3 text-brand-300" />
            Workspace
          </div>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            <span className="text-text-secondary">Workspace</span>{' '}
            <span className="gradient-text">settings</span>
          </h1>
          <p className="mt-1 max-w-xl text-sm text-text-secondary">
            Configure how the AI studio publishes, who reviews drafts, and
            how the rest of the system behaves.
          </p>
        </div>
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
      </header>

      <ErrorBanner error={err} onRetry={load} />

      <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
        <aside className="lg:sticky lg:top-20 lg:self-start">
          <nav className="glass-card space-y-1 p-2">
            {SECTIONS.map((section) => {
              const Icon = section.icon;
              const isActive = active === section.id;
              return (
                <button
                  key={section.id}
                  type="button"
                  onClick={() => setActive(section.id)}
                  className={
                    'nav-item w-full ' +
                    (isActive ? 'nav-item-active' : '')
                  }
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  <span className="truncate">{section.label}</span>
                </button>
              );
            })}
          </nav>
        </aside>

        <div className="space-y-6">
          {loading ? (
            <div className="space-y-4">
              {Array.from({ length: 3 }).map((_, idx) => (
                <Skeleton key={idx} className="h-40" />
              ))}
            </div>
          ) : (
            <AnimatePresence mode="wait">
              <motion.div
                key={active}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.22 }}
                className="space-y-6"
              >
                {active === 'profile' ? (
                  <ProfileSection />
                ) : null}
                {active === 'linkedin' ? (
                  <LinkedInSection />
                ) : null}
                {active === 'ai' ? <AiSection /> : null}
                {active === 'approval' ? (
                  <ApprovalSection
                    form={form}
                    update={update}
                    approvalTone={approvalTone}
                    approvalNeedsEmail={approvalNeedsEmail}
                  />
                ) : null}
                {active === 'publishing' ? (
                  <PublishingSection form={form} update={update} />
                ) : null}
                {active === 'notifications' ? (
                  <NotificationsSection form={form} update={update} />
                ) : null}
                {active === 'security' ? (
                  <SecuritySection health={health} />
                ) : null}
                {active === 'general' ? <GeneralSection /> : null}
              </motion.div>
            </AnimatePresence>
          )}
        </div>
      </div>
    </MotionPage>
  );
}

import { AnimatePresence } from 'framer-motion';

function Section({ title, description, icon: Icon, children, footer }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {Icon ? <Icon className="h-4 w-4 text-text-secondary" /> : null}
          {title}
        </CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
      {footer ? <div className="border-t border-white/[0.06] p-6">{footer}</div> : null}
    </Card>
  );
}

function ProfileSection() {
  return (
    <Section
      title="Profile"
      description="Your display name and email. Used in the studio UI."
      icon={User}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <Field id="profile-name" label="Display name">
          <Input id="profile-name" placeholder="Your name" disabled />
        </Field>
        <Field id="profile-email" label="Email">
          <Input id="profile-email" type="email" placeholder="you@example.com" disabled />
        </Field>
      </div>
      <p className="text-xs text-text-muted">
        Profile details are managed by your authentication provider.
      </p>
    </Section>
  );
}

function LinkedInSection() {
  return (
    <Section
      title="LinkedIn"
      description="Connect your LinkedIn account to publish drafts."
      icon={Linkedin}
    >
      <LinkedInCard />
    </Section>
  );
}

function AiSection() {
  return (
    <Section
      title="AI preferences"
      description="Tune how the writer and reviewer behave."
      icon={Sparkles}
    >
      <Field id="ai-default-tone" label="Default tone" optional>
        <Input id="ai-default-tone" placeholder="professional, candid…" disabled />
      </Field>
      <Field id="ai-default-style" label="Default style" optional>
        <Input id="ai-default-style" placeholder="technical, narrative…" disabled />
      </Field>
      <p className="text-xs text-text-muted">
        Per-draft overrides are available in the Create Post page. Global
        defaults coming soon.
      </p>
    </Section>
  );
}

function ApprovalSection({ form, update, approvalTone, approvalNeedsEmail }) {
  return (
    <Section
      title="Approval"
      description="Decide how drafts move from creation to publishing."
      icon={Mail}
    >
      <Field id="approval-mode" label="Approval mode">
        <Select
          id="approval-mode"
          value={form.approval_mode}
          onChange={(e) => update('approval_mode', e.target.value)}
        >
          {APPROVAL_MODES.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </Select>
        <div className="flex items-center gap-2">
          <Badge tone={approvalTone} size="sm" withDot>
            {form.approval_mode}
          </Badge>
          <span className="text-xs text-text-muted">
            {form.approval_mode === 'email'
              ? 'Newly generated posts will require approval via the notification email below.'
              : form.approval_mode === 'auto'
              ? 'Posts that pass the reviewer are approved automatically. No email.'
              : 'Posts always need explicit approval in the Approval queue.'}
          </span>
        </div>
      </Field>
      <Field
        id="notification-email"
        label={
          approvalNeedsEmail
            ? 'Notification email'
            : 'Notification email'
        }
        hint={
          approvalNeedsEmail
            ? 'Required when Email approval mode is selected.'
            : 'Only used when Email approval mode is selected.'
        }
        required={approvalNeedsEmail}
        error={
          approvalNeedsEmail && !form.notification_email?.trim()
            ? 'Please enter a notification email.'
            : null
        }
      >
        <Input
          id="notification-email"
          type="email"
          value={form.notification_email}
          onChange={(e) => update('notification_email', e.target.value)}
          placeholder="you@example.com"
        />
      </Field>
    </Section>
  );
}

function PublishingSection({ form, update }) {
  return (
    <Section
      title="Publishing"
      description="How drafts reach LinkedIn."
      icon={Send}
    >
      <Field id="publishing-mode" label="Publishing mode">
        <Select
          id="publishing-mode"
          value={form.publishing_mode}
          onChange={(e) => update('publishing_mode', e.target.value)}
        >
          {PUBLISHING_MODES.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </Select>
        <p className="text-xs text-text-muted">
          {form.publishing_mode === 'manual'
            ? 'Drafts are only published when you click Publish.'
            : 'Drafts you schedule are published automatically at the chosen time.'}
        </p>
      </Field>
    </Section>
  );
}

function NotificationsSection({ form, update }) {
  return (
    <Section
      title="Notifications"
      description="When the studio should reach out to you."
      icon={Bell}
    >
      <p className="text-sm text-text-secondary">
        Email notifications are sent for approval requests. We never
        send marketing emails.
      </p>
      <Field id="notif-timezone" label="Timezone" hint="Used for scheduled times.">
        <Input
          id="notif-timezone"
          value={form.timezone}
          onChange={(e) => update('timezone', e.target.value)}
          leftIcon={<Globe className="h-3.5 w-3.5" />}
        />
      </Field>
    </Section>
  );
}

function SecuritySection({ health }) {
  const healthy = health?.status === 'healthy';
  return (
    <Section
      title="Security"
      description="Account safety and infrastructure health."
      icon={Shield}
    >
      <div className="grid gap-3 sm:grid-cols-3">
        <Field id="sec-2fa" label="Two-factor auth" hint="Recommended">
          <Input id="sec-2fa" value="Off" disabled />
        </Field>
        <Field id="sec-sessions" label="Active sessions">
          <Input id="sec-sessions" value="1 active" disabled />
        </Field>
        <Field id="sec-backend" label="Backend health">
          <Input
            id="sec-backend"
            value={health ? health.status || 'unknown' : 'Loading…'}
            leftIcon={
              <Server
                className={
                  healthy
                    ? 'h-3.5 w-3.5 text-emerald-300'
                    : 'h-3.5 w-3.5 text-text-muted'
                }
              />
            }
            disabled
          />
        </Field>
      </div>
    </Section>
  );
}

function GeneralSection() {
  return (
    <Section
      title="General"
      description="Workspace-level preferences."
      icon={SettingsIcon}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <Field id="gen-language" label="Language" optional>
          <Input id="gen-language" value="English" disabled />
        </Field>
        <Field id="gen-theme" label="Theme" optional>
          <Input id="gen-theme" value="Dark (default)" disabled />
        </Field>
      </div>
      <p className="text-xs text-text-muted">
        Additional general preferences coming soon.
      </p>
    </Section>
  );
}
