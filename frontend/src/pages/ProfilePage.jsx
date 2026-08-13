import { useEffect, useState } from 'react';

import { useApi } from '../services/api/backend.js';
import { useAuth } from '../context/AuthContext.jsx';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Textarea } from '../components/ui/Input.jsx';
import { ErrorBanner, Spinner } from '../components/ui/Feedback.jsx';

export default function ProfilePage() {
  const api = useApi();
  const { user } = useAuth();
  const { toast } = useToast();

  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  const [form, setForm] = useState({
    display_name: '',
    headline: '',
    bio: '',
    linkedin_url: '',
    github_url: '',
    avatar_url: '',
  });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const data = await api.getProfile();
        if (cancelled) return;
        setProfile(data);
        setForm({
          display_name: data.display_name || '',
          headline: data.headline || '',
          bio: data.bio || '',
          linkedin_url: data.linkedin_url || '',
          github_url: data.github_url || '',
          avatar_url: data.avatar_url || '',
        });
        setDirty(false);
        setError(null);
      } catch (err) {
        if (!cancelled) setError(err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [api]);

  function update(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
    setDirty(true);
  }

  async function handleSave() {
    setSaving(true);
    try {
      const payload = Object.fromEntries(
        Object.entries(form).filter(([, v]) => v !== ''),
      );
      const updated = await api.updateProfile(payload);
      setProfile(updated);
      setForm({
        display_name: updated.display_name || '',
        headline: updated.headline || '',
        bio: updated.bio || '',
        linkedin_url: updated.linkedin_url || '',
        github_url: updated.github_url || '',
        avatar_url: updated.avatar_url || '',
      });
      setDirty(false);
      toast.success('Profile saved.');
    } catch (err) {
      toast.error('Save failed', err?.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Profile</h1>
        <p className="text-zinc-400">Manage how LinkedIn AI Studio represents you.</p>
      </div>

      <ErrorBanner error={error} onRetry={load} />

      <div className="grid gap-4 lg:grid-cols-[0.85fr_1.15fr]">
        <Card>
          <CardHeader>
            <CardTitle>Account</CardTitle>
            <CardDescription>Identity (read-only) is owned by Firebase.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex flex-col gap-1 sm:flex-row sm:justify-between sm:gap-2 sm:items-center">
              <span className="text-zinc-400">Display name</span>
              <span className="text-zinc-200">{profile?.name || user?.displayName || '—'}</span>
            </div>
            <div className="flex flex-col gap-1 sm:flex-row sm:justify-between sm:gap-2 sm:items-center">
              <span className="text-zinc-400">Email</span>
              <span className="text-zinc-200">{profile?.email || user?.email || '—'}</span>
            </div>
            <div className="flex flex-col gap-1 sm:flex-row sm:justify-between sm:gap-2 sm:items-center">
              <span className="text-zinc-400">Verified</span>
              <span className="text-zinc-200">
                {profile?.email_verified || user?.emailVerified ? 'Yes' : 'No'}
              </span>
            </div>
            <div className="flex flex-col gap-1 sm:flex-row sm:justify-between sm:gap-2 sm:items-center">
              <span className="text-zinc-400">UID</span>
              <span className="font-mono text-xs text-zinc-200 truncate">{profile?.uid || user?.uid || '—'}</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Profile details</CardTitle>
            <CardDescription>
              {loading
                ? 'Loading…'
                : dirty
                  ? 'Unsaved changes'
                  : 'Saved on the server'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {loading ? (
              <Spinner />
            ) : (
              <>
                <div>
                  <label className="mb-1 block text-sm">Display name</label>
                  <Input
                    value={form.display_name}
                    onChange={(event) => update('display_name', event.target.value)}
                    disabled={saving}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm">Headline</label>
                  <Input
                    value={form.headline}
                    onChange={(event) => update('headline', event.target.value)}
                    disabled={saving}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm">Bio</label>
                  <Textarea
                    rows={4}
                    value={form.bio}
                    onChange={(event) => update('bio', event.target.value)}
                    disabled={saving}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm">LinkedIn URL</label>
                  <Input
                    value={form.linkedin_url}
                    onChange={(event) => update('linkedin_url', event.target.value)}
                    placeholder="https://linkedin.com/in/username"
                    disabled={saving}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm">GitHub URL</label>
                  <Input
                    value={form.github_url}
                    onChange={(event) => update('github_url', event.target.value)}
                    placeholder="https://github.com/username"
                    disabled={saving}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm">Avatar URL</label>
                  <Input
                    value={form.avatar_url}
                    onChange={(event) => update('avatar_url', event.target.value)}
                    placeholder="https://…/avatar.png"
                    disabled={saving}
                  />
                </div>
                <div className="flex justify-end">
                  <Button onClick={handleSave} disabled={!dirty} loading={saving}>
                    {dirty ? 'Save changes' : 'Saved'}
                  </Button>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
