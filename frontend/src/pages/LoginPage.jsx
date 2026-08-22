import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Sparkles, Mail, Lock, ArrowRight, CheckCircle2, FileText, Link2, Send, BarChart3, ShieldCheck } from 'lucide-react';

import { useAuth } from '../context/AuthContext.jsx';
import { useToast } from '../context/ToastContext.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Field } from '../components/ui/Input.jsx';
import { Card, CardContent } from '../components/ui/Card.jsx';

const FEATURE_CARDS = [
  { icon: FileText, label: 'Topic drafting', hint: 'Writer + reviewer' },
  { icon: Link2, label: 'Source ingestion', hint: 'GitHub, docs, blogs' },
  { icon: ShieldCheck, label: 'Approval flow', hint: 'Email or manual' },
  { icon: Send, label: 'LinkedIn publish', hint: 'OAuth-backed' },
];

export default function LoginPage() {
  const { signIn, signInWithGoogle, status, firebaseEnabled } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { toast } = useToast();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [googleSubmitting, setGoogleSubmitting] = useState(false);

  useEffect(() => {
    if (status === 'authenticated') {
      const target = location.state?.from?.pathname ?? '/dashboard';
      navigate(target, { replace: true });
    }
  }, [status, location.state, navigate]);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!email || !password) {
      toast.error('Email and password are required.');
      return;
    }
    setSubmitting(true);
    try {
      await signIn(email, password);
      toast.success('Welcome back.');
    } catch (err) {
      const code = err?.code?.replace('auth/', '') || 'error';
      toast.error('Sign-in failed', code);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleGoogle() {
    setGoogleSubmitting(true);
    try {
      await signInWithGoogle();
      toast.success('Signed in with Google.');
    } catch (err) {
      toast.error('Google sign-in failed', err?.code?.replace('auth/', ''));
    } finally {
      setGoogleSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div
        className="pointer-events-none absolute inset-0 -z-10"
        aria-hidden
        style={{
          background:
            'radial-gradient(ellipse 80% 50% at 20% 0%, rgba(139, 92, 246, 0.18), transparent 60%), radial-gradient(ellipse 60% 40% at 100% 100%, rgba(56, 189, 248, 0.10), transparent 60%)',
        }}
      />
      <div className="mx-auto flex min-h-screen max-w-6xl items-center justify-center px-4 py-10 sm:px-6 lg:px-8">
        <div className="grid w-full items-center gap-10 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="space-y-8 animate-fadeIn">
            <Link to="/" className="inline-flex items-center gap-3 text-zinc-100">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-glow-brand">
                <Sparkles className="h-4 w-4" />
              </span>
              <span className="text-base font-semibold tracking-tight">LinkedIn AI Studio</span>
            </Link>

            <div>
              <span className="label-faint mb-3 inline-block">Content operations</span>
              <h1 className="text-balance text-3xl font-semibold tracking-tight text-white sm:text-4xl lg:text-5xl">
                Sign in to your{' '}
                <span className="bg-gradient-to-r from-brand-300 via-brand-200 to-sky-300 bg-clip-text text-transparent">
                  content operations
                </span>{' '}
                workspace.
              </h1>
              <p className="mt-4 max-w-lg text-base text-text-secondary">
                Drafts, approvals, scheduled posts, and published content — all backed by the
                existing LinkedIn content orchestration engine.
              </p>
            </div>

            <ul className="grid grid-cols-2 gap-2 sm:gap-3">
              {FEATURE_CARDS.map((feature) => {
                const Icon = feature.icon;
                return (
                  <li
                    key={feature.label}
                    className="panel-inset flex items-center gap-3 p-3"
                  >
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-white/10 bg-white/[0.04] text-brand-300">
                      <Icon className="h-4 w-4" />
                    </span>
                    <span>
                      <span className="block text-sm font-semibold text-zinc-100">{feature.label}</span>
                      <span className="block text-xs text-text-muted">{feature.hint}</span>
                    </span>
                  </li>
                );
              })}
            </ul>

            {firebaseEnabled === false ? (
              <div className="rounded-xl border border-amber-500/30 bg-amber-500/[0.08] p-4 text-sm text-amber-100">
                Firebase Web SDK is not configured. Add <code className="font-mono">VITE_FIREBASE_*</code>{' '}
                environment variables to enable authentication.
              </div>
            ) : null}
          </div>

          <Card className="w-full animate-fadeIn">
            <CardContent className="space-y-5 p-6 sm:p-8">
              <div>
                <h2 className="text-xl font-semibold tracking-tight text-white">Sign in</h2>
                <p className="mt-1 text-sm text-text-secondary">
                  Use your Firebase credentials to access the studio.
                </p>
              </div>
              <form className="space-y-4" onSubmit={handleSubmit}>
                <Field id="login-email" label="Email" required>
                  <Input
                    id="login-email"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="you@example.com"
                    leftIcon={<Mail className="h-3.5 w-3.5" />}
                    required
                  />
                </Field>
                <Field id="login-password" label="Password" required>
                  <Input
                    id="login-password"
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="••••••••"
                    leftIcon={<Lock className="h-3.5 w-3.5" />}
                    required
                  />
                </Field>
                <Button
                  type="submit"
                  variant="brand"
                  size="lg"
                  loading={submitting}
                  className="w-full"
                  rightIcon={!submitting ? <ArrowRight className="h-4 w-4" /> : null}
                >
                  {submitting ? 'Signing in…' : 'Sign in'}
                </Button>
              </form>

              <div className="relative">
                <div className="absolute inset-0 flex items-center" aria-hidden="true">
                  <div className="w-full border-t border-white/[0.06]" />
                </div>
                <div className="relative flex justify-center text-xs">
                  <span className="bg-[#0f0f12] px-2 text-text-muted">OR</span>
                </div>
              </div>

              <Button
                type="button"
                variant="outline"
                size="lg"
                onClick={handleGoogle}
                loading={googleSubmitting}
                className="w-full"
                disabled={!firebaseEnabled}
              >
                Continue with Google
              </Button>

              <p className="text-center text-sm text-text-secondary">
                New here?{' '}
                <Link to="/signup" className="font-medium text-brand-300 hover:text-brand-200 hover:underline">
                  Create an account
                </Link>
                .
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
