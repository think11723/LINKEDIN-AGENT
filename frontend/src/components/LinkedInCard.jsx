import { useEffect, useState } from 'react';
import { CheckCircle2, Linkedin, ShieldCheck, X } from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useToast } from '../context/ToastContext.jsx';
import { Button } from './ui/Button.jsx';
import { Badge } from './ui/Badge.jsx';
import { Spinner } from './ui/Feedback.jsx';
import { ConfirmDialog } from './ConfirmDialog.jsx';

/**
 * LinkedIn connection card. Reads ``GET /api/v1/linkedin/status`` to
 * display the current state, lets the user connect (full-page
 * redirect to the authorization URL from
 * ``GET /api/v1/linkedin/connect``) and disconnect (POST
 * ``/api/v1/linkedin/disconnect``).
 *
 * NEVER displays tokens, refresh tokens, client secrets, or other
 * credentials. Only safe metadata is rendered: connection status,
 * person URN, scopes, expiry timestamp.
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
    const params = new URLSearchParams(window.location.search);
    const flag = params.get('linkedin');
    if (flag === 'connected') {
      toast.success('LinkedIn connected.');
    } else if (flag === 'error') {
      const reason = params.get('reason') || 'unknown';
      const detail = params.get('detail');
      toast.error('LinkedIn connection failed.', detail ? `${reason} (${detail})` : reason);
    }
    if (flag) {
      const url = new URL(window.location.href);
      url.searchParams.delete('linkedin');
      url.searchParams.delete('reason');
      url.searchParams.delete('detail');
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

  const isConnected = Boolean(status?.connected);

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3">
        <div
          className={
            'flex h-10 w-10 items-center justify-center rounded-xl border ' +
            (isConnected
              ? 'border-emerald-400/30 bg-emerald-500/15 text-emerald-300'
              : 'border-white/10 bg-white/[0.04] text-text-secondary')
          }
        >
          <Linkedin className="h-5 w-5" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <div className="text-sm font-semibold text-zinc-100">LinkedIn account</div>
            {loading ? (
              <Spinner size="xs" />
            ) : isConnected ? (
              <Badge tone="success" size="xs" withDot>
                <CheckCircle2 className="h-3 w-3" /> Connected
              </Badge>
            ) : (
              <Badge tone="neutral" size="xs" withDot>
                Not connected
              </Badge>
            )}
          </div>
          <p className="mt-0.5 text-sm text-text-secondary">
            {isConnected
              ? 'Drafts can be published to LinkedIn immediately.'
              : 'Connect your account to publish drafts and read your member URN.'}
          </p>
          {isConnected && status?.expires_at ? (
            <p className="mt-1 text-xs text-text-muted">
              Token expires {new Date(status.expires_at).toLocaleString()}
            </p>
          ) : null}
        </div>
      </div>
      <div className="flex items-center gap-2">
        {isConnected ? (
          <Button
            variant="outline"
            onClick={() => setConfirmOpen(true)}
            disabled={loading || disconnecting}
            leftIcon={<X className="h-3.5 w-3.5" />}
          >
            Disconnect
          </Button>
        ) : (
          <Button
            variant="brand"
            onClick={handleConnect}
            disabled={loading || connecting}
            loading={connecting}
            leftIcon={<Linkedin className="h-4 w-4" />}
          >
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
