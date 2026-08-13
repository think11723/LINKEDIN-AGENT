import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Sparkles } from 'lucide-react';

import { useAuth } from '../context/AuthContext.jsx';
import { useToast } from '../context/ToastContext.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input } from '../components/ui/Input.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';

export default function SignupPage() {
  const { signUp, status, firebaseEnabled } = useAuth();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (status === 'authenticated') {
      navigate('/dashboard', { replace: true });
    }
  }, [status, navigate]);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!email || password.length < 6) {
      toast.error('Password must be at least 6 characters.');
      return;
    }
    setSubmitting(true);
    try {
      await signUp(email, password);
      toast.success('Account created.');
    } catch (err) {
      toast.error('Sign-up failed', err?.code?.replace('auth/', '') ?? err?.message);
    } finally {
      setSubmitting(false);
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
              Create an account and start publishing faster.
            </h1>
            <p className="max-w-md text-zinc-400">
              Authentication uses Firebase. Once signed in, the studio attaches your Firebase ID token to
              every backend request.
            </p>
            {firebaseEnabled === false ? (
              <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-100">
                Firebase Web SDK is not configured. Add <code className="font-mono">VITE_FIREBASE_*</code>{' '}
                environment variables to enable account creation.
              </div>
            ) : null}
          </div>

          <Card className="w-full">
            <CardHeader>
              <CardTitle>Create your account</CardTitle>
              <CardDescription>Sign up with email and password.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <form className="space-y-4" onSubmit={handleSubmit}>
                <div>
                  <label className="label-muted mb-2 block">Display name (optional)</label>
                  <Input value={name} onChange={(event) => setName(event.target.value)} />
                </div>
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
                    autoComplete="new-password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    required
                    minLength={6}
                  />
                </div>
                <Button type="submit" loading={submitting} className="w-full">
                  Create account
                </Button>
              </form>

              <p className="text-sm text-zinc-400">
                Already have an account?{' '}
                <Link to="/login" className="font-medium text-violet-300 hover:text-violet-200">
                  Sign in
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