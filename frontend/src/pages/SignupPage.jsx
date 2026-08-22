import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Sparkles,
  Mail,
  Lock,
  User,
  ArrowRight,
  ShieldCheck,
  FileText,
  Link2,
  Send,
} from 'lucide-react';

import { useAuth } from '../context/AuthContext.jsx';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Field } from '../components/ui/Input.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { cn } from '../utils/cn.js';

const FEATURE_CARDS = [
  { icon: FileText, label: 'Topic drafting', hint: 'Writer + reviewer' },
  { icon: Link2, label: 'Source ingestion', hint: 'GitHub, docs, blogs' },
  { icon: ShieldCheck, label: 'Approval flow', hint: 'Email or manual' },
  { icon: Send, label: 'LinkedIn publish', hint: 'OAuth-backed' },
];

function HeroGradient() {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
    >
      <div className="absolute -right-40 -top-40 h-[480px] w-[480px] rounded-full bg-accent-500/25 blur-3xl" />
      <div className="absolute -left-32 bottom-0 h-[420px] w-[420px] rounded-full bg-brand-500/25 blur-3xl" />
    </div>
  );
}

export default function SignupPage() {
  const { signUp, status, firebaseEnabled } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { toast } = useToast();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);

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
      await signUp(email, password, name || undefined);
      toast.success('Account created.');
    } catch (err) {
      const code = err?.code?.replace('auth/', '') || 'error';
      toast.error('Sign-up failed', code);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="relative min-h-screen overflow-hidden bg-background text-foreground">
      <HeroGradient />
      <div className="relative mx-auto flex min-h-screen max-w-6xl items-center justify-center px-4 py-12 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="grid w-full items-center gap-10 lg:grid-cols-2 lg:gap-16"
        >
          <div className="space-y-8">
            <div className="space-y-4">
              <div className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.04] px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-text-secondary">
                <Sparkles className="h-3 w-3 text-accent-400" />
                Get started
              </div>
              <h1 className="text-balance text-4xl font-semibold tracking-tight text-white sm:text-5xl">
                Create an account.{' '}
                <span className="gradient-text">Publish faster.</span>
              </h1>
              <p className="max-w-md text-base text-text-secondary">
                Authentication uses Firebase. Once signed in, the studio
                attaches your Firebase ID token to every backend request.
              </p>
              <div className="flex flex-wrap gap-2">
                <Badge tone="brand" size="md">
                  Free during preview
                </Badge>
                <Badge tone="accent" size="md">
                  Multi-account ready
                </Badge>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {FEATURE_CARDS.map((feature) => {
                const Icon = feature.icon;
                return (
                  <div
                    key={feature.label}
                    className="glass-card flex items-center gap-3 rounded-2xl p-4"
                  >
                    <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-white/[0.08] bg-gradient-brand-soft text-brand-300">
                      <Icon className="h-4 w-4" />
                    </span>
                    <div>
                      <div className="text-sm font-semibold text-zinc-100">
                        {feature.label}
                      </div>
                      <div className="text-xs text-text-muted">
                        {feature.hint}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <Card className="w-full max-w-md justify-self-center">
            <CardContent className="space-y-5 p-6 sm:p-8">
              <div className="flex items-center gap-3">
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-brand shadow-glow-brand">
                  <Sparkles className="h-4 w-4 text-white" />
                </span>
                <div>
                  <div className="text-base font-semibold text-white">
                    Create your account
                  </div>
                  <div className="text-xs text-text-muted">
                    Sign up with email and password
                  </div>
                </div>
              </div>

              <form className="space-y-3" onSubmit={handleSubmit}>
                <Field id="signup-name" label="Display name" optional>
                  <Input
                    id="signup-name"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    placeholder="Your name"
                    leftIcon={<User className="h-3.5 w-3.5" />}
                  />
                </Field>
                <Field id="signup-email" label="Email" required>
                  <Input
                    id="signup-email"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    leftIcon={<Mail className="h-3.5 w-3.5" />}
                    required
                  />
                </Field>
                <Field id="signup-password" label="Password" required>
                  <Input
                    id="signup-password"
                    type="password"
                    autoComplete="new-password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    leftIcon={<Lock className="h-3.5 w-3.5" />}
                    required
                    minLength={6}
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
                  {submitting ? 'Creating account…' : 'Create account'}
                </Button>
              </form>

              <p className="text-center text-sm text-text-secondary">
                Already have an account?{' '}
                <Link
                  to="/login"
                  className="font-medium text-brand-300 hover:text-brand-200 hover:underline"
                >
                  Sign in
                </Link>
                .
              </p>

              {firebaseEnabled === false ? (
                <div className="rounded-xl border border-amber-500/30 bg-amber-500/[0.08] p-3 text-sm text-amber-100">
                  Firebase Web SDK is not configured. Add{' '}
                  <code className="font-mono">VITE_FIREBASE_*</code> environment
                  variables to enable account creation.
                </div>
              ) : null}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
