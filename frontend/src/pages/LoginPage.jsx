import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Sparkles } from 'lucide-react';

import { useAuth } from '../context/AuthContext.jsx';
import { useToast } from '../context/ToastContext.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input } from '../components/ui/Input.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';

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
    <div className="min-h-screen bg-zinc-950 text-zinc-50">
      <div className="mx-auto flex min-h-screen max-w-5xl items-center justify-center px-4 py-10">
        <div className="grid w-full items-center gap-10 lg:grid-cols-[1fr_0.95fr]">
          <div className="space-y-5">
            <Link to="/" className="inline-flex items-center gap-3 text-zinc-100">
              <span className="rounded-lg bg-violet-500/20 p-2 text-violet-300">
                <Sparkles className="h-4 w-4" />
              </span>
              <span className="font-semibold">LinkedIn AI Studio</span>
            </Link>
            <h1 className="text-4xl font-semibold tracking-tight">
              Sign in to your content operations workspace.
            </h1>
            <p className="max-w-md text-zinc-400">
              Manage drafts, approvals, scheduled posts, and published content backed by the existing
              LinkedIn content orchestration engine.
            </p>
            {firebaseEnabled === false ? (
              <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-100">
                Firebase Web SDK is not configured. Add <code className="font-mono">VITE_FIREBASE_*</code>{' '}
                environment variables to enable authentication.
              </div>
            ) : null}
          </div>

          <Card className="w-full">
            <CardHeader>
              <CardTitle>Sign in</CardTitle>
              <CardDescription>Use your Firebase credentials to access the studio.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <form className="space-y-4" onSubmit={handleSubmit}>
                <div>
                  <label className="label-muted mb-2 block">Email</label>
                  <Input
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    required
                  />
                </div>
                <div>
                  <label className="label-muted mb-2 block">Password</label>
                  <Input
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                  />
                </div>
                <Button type="submit" loading={submitting} className="w-full">
                  Sign in
                </Button>
              </form>

              <div className="relative">
                <div className="absolute inset-0 flex items-center" aria-hidden="true">
                  <div className="w-full border-t border-white/10" />
                </div>
                <div className="relative flex justify-center text-xs">
                  <span className="bg-zinc-950 px-2 text-zinc-500">OR</span>
                </div>
              </div>

              <Button
                type="button"
                variant="outline"
                onClick={handleGoogle}
                loading={googleSubmitting}
                className="w-full"
                disabled={!firebaseEnabled}
              >
                Continue with Google
              </Button>

              <p className="text-sm text-zinc-400">
                New here?{' '}
                <Link to="/signup" className="font-medium text-violet-300 hover:text-violet-200">
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