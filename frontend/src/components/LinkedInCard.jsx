import { useEffect, useState } from 'react';

import { useApi } from '../services/api/backend.js';
import { useToast } from '../context/ToastContext.jsx';
import { Button } from './ui/Button.jsx';
import { Spinner } from './ui/Feedback.jsx';
import { ConfirmDialog } from './ConfirmDialog.jsx';

/**
 * Phase 8B P1-1 + P1-11 — LinkedIn connection card.
 *
 * Reads ``GET /api/v1/linkedin/status`` to display the current state, lets
 * the user connect (full-page redirect to the authorization URL from
 * ``GET /api/v1/linkedin/connect``) and disconnect (POST
 * ``/api/v1/linkedin/disconnect``).
 *
 * Reads ``?linkedin=connected|error&reason=...`` on mount so the
 * LinkedIn OAuth callback can land the user on a real status.
 */
export function LinkedInCard() {
  const api = useApi();
  const { toast } = useToast();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      const data = await api.getLinkedInStatus();
      setStatus(data);
    } catch (err) {
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // Read URL flags from the LinkedIn OAuth callback.
    const params = new URLSearchParams(window.location.search);
    const flag = params.get('linkedin');
    if (flag === 'connected') {
      toast.success('LinkedIn connected.');
    } else if (flag === 'error') {
      const reason = params.get('reason') || 'unknown';
      toast.error('LinkedIn connection failed.', reason);
    }
    // Clean the flag from the URL.
    if (flag) {
      const url = new URL(window.location.href);
      url.searchParams.delete('linkedin');
      url.searchParams.delete('reason');
      window.history.replaceState({}, '', url.toString());
    }
  }, []);

  async function handleConnect() {
    setConnecting(true);
    try {
      const { authorization_url } = await api.startLinkedInConnect();
      window.location.href = authorization_url;
    } catch (err) {
      toast.error('Could not start LinkedIn OAuth.', err?.message);
      setConnecting(false);
    }
  }

  async function handleDisconnect() {
    setDisconnecting(true);
    try {
      await api.disconnectLinkedIn();
      toast.success('LinkedIn disconnected.');
      await refresh();
    } catch (err) {
      toast.error('Disconnect failed.', err?.message);
    } finally {
      setDisconnecting(false);
      setConfirmOpen(false);
    }
  }

  return (
    <div className="rounded-2xl border border-white/10 bg-zinc-950/60 p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-zinc-50">LinkedIn</h2>
          <p className="mt-1 text-sm text-zinc-400">
            Connect your LinkedIn account to publish drafts and read your member URN.
          </p>
        </div>
        {loading ? (
          <Spinner />
        ) : status?.connected ? (
          <span className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-200">
            Connected
          </span>
        ) : (
          <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-0.5 text-xs font-medium text-zinc-400">
            Not connected
          </span>
        )}
      </div>

      {status?.connected ? (
        <dl className="mt-4 grid grid-cols-1 gap-2 text-sm">
          {status.person_urn ? (
            <div className="flex items-center gap-2">
              <dt className="text-zinc-400">Person URN</dt>
              <dd className="font-mono text-zinc-200 truncate">{status.person_urn}</dd>
            </div>
          ) : null}
          {status.scope ? (
            <div className="flex items-center gap-2">
              <dt className="text-zinc-400">Scopes</dt>
              <dd className="text-zinc-200 truncate">{status.scope}</dd>
            </div>
          ) : null}
          {status.expires_at ? (
            <div className="flex items-center gap-2">
              <dt className="text-zinc-400">Token expires</dt>
              <dd className="text-zinc-200">{new Date(status.expires_at).toLocaleString()}</dd>
            </div>
          ) : null}
        </dl>
      ) : null}

      <div className="mt-4 flex items-center gap-2">
        {status?.connected ? (
          <Button variant="danger" onClick={() => setConfirmOpen(true)} disabled={loading || disconnecting}>
            Disconnect
          </Button>
        ) : (
          <Button onClick={handleConnect} disabled={loading || connecting} loading={connecting}>
            Connect LinkedIn
          </Button>
        )}
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title="Disconnect LinkedIn?"
        description="Scheduled and on-demand publishes will fail until you reconnect. Existing scheduled jobs that have not run yet are not deleted."
        confirmLabel="Disconnect"
        danger
        confirming={disconnecting}
        onConfirm={handleDisconnect}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}
