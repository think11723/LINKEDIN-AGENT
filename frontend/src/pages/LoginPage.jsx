import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Sparkles,
  Mail,
  Lock,
  ArrowRight,
  Linkedin,
  ShieldCheck,
  FileText,
  Link2,
  Send,
  CheckCircle2,
} from 'lucide-react';

import { useAuth } from '../context/AuthContext.jsx';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Field } from '../components/ui/Input.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { cn } from '../utils/cn.js';

const FEATURE_CARDS = [
  {
    icon: FileText,
    label: 'Topic drafting',
    hint: 'Writer + reviewer',
  },
  {
    icon: Link2,
    label: 'Source ingestion',
    hint: 'GitHub, docs, blogs',
  },
  {
    icon: ShieldCheck,
    label: 'Approval flow',
    hint: 'Email or manual',
  },
  {
    icon: Send,
    label: 'LinkedIn publish',
    hint: 'OAuth-backed',
  },
];

function HeroGradient() {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
    >
      <div className="absolute -left-40 -top-40 h-[480px] w-[480px] rounded-full bg-brand-500/25 blur-3xl" />
      <div className="absolute -right-32 bottom-0 h-[420px] w-[420px] rounded-full bg-accent-500/25 blur-3xl" />
      <div className="absolute inset-0 opacity-50" style={{
        backgroundImage:
          'linear-gradient(to right, rgba(255,255,255,0.04) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.04) 1px, transparent 1px)',
        backgroundSize: '48px 48px',
        maskImage:
          'radial-gradient(ellipse at center, black 0%, transparent 70%)',
        WebkitMaskImage:
          'radial-gradient(ellipse at center, black 0%, transparent 70%)',
      }} />
    </div>
  );
}

function FloatingOrb({ className, delay = 0 }) {
  return (
    <motion.div
      aria-hidden
      className={cn('pointer-events-none absolute h-24 w-24 rounded-full blur-2xl', className)}
      animate={{ y: [0, -10, 0] }}
      transition={{ duration: 6, repeat: Infinity, ease: 'easeInOut', delay }}
    />
  );
}

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
    <div className="relative min-h-screen overflow-hidden bg-background text-foreground">
      <HeroGradient />
      <FloatingOrb className="left-10 top-1/3 bg-brand-500/30" />
      <FloatingOrb className="right-12 top-2/3 bg-accent-500/30" delay={1.2} />

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
                <Sparkles className="h-3 w-3 text-brand-300" />
                AI-powered content engine
              </div>
              <h1 className="text-balance text-4xl font-semibold tracking-tight text-white sm:text-5xl">
                Create{' '}
                <span className="gradient-text">viral LinkedIn content</span>{' '}
                powered by AI.
              </h1>
              <p className="max-w-md text-base text-text-secondary">
                Draft authentic posts from a topic or a public URL. The
                LinkedIn AI Studio handles the writing, the review, and
                the publishing — you keep the voice.
              </p>
              <div className="flex flex-wrap gap-2">
                <Badge tone="brand" size="md">
                  Topic + URL modes
                </Badge>
                <Badge tone="accent" size="md">
                  Grounded in your source
                </Badge>
                <Badge tone="success" size="md">
                  Reviewer checks every post
                </Badge>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              {FEATURE_CARDS.map((feature, idx) => {
                const Icon = feature.icon;
                return (
                  <motion.div
                    key={feature.label}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.05 + idx * 0.04, duration: 0.3 }}
                    className="glass-card flex items-center gap-3 rounded-2xl p-4"
                  >
                    <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-white/[0.08] bg-gradient-brand-soft text-brand-300">
                      <Icon className="h-4 w-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-semibold text-zinc-100">
                        {feature.label}
                      </div>
                      <div className="text-xs text-text-muted">
                        {feature.hint}
                      </div>
                    </div>
                  </motion.div>
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
                    LinkedIn AI Studio
                  </div>
                  <div className="text-xs text-text-muted">
                    Sign in to continue
                  </div>
                </div>
              </div>

              <form className="space-y-3" onSubmit={handleSubmit}>
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
                <div className="absolute inset-0 flex items-center" aria-hidden>
                  <div className="w-full border-t border-white/[0.06]" />
                </div>
                <div className="relative flex justify-center text-xs">
                  <span className="bg-bg-card px-2 text-text-muted">OR</span>
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
                leftIcon={
                  <svg
                    className="h-4 w-4"
                    viewBox="0 0 24 24"
                    aria-hidden
                  >
                    <path
                      fill="#EA4335"
                      d="M12 11v2.5h7a7 7 0 0 1-7 7 7 7 0 0 1-7-7 7 7 0 0 1 7-7 7 7 0 0 1 5 2l-2 2a4.5 4.5 0 0 0-3-1.2 4.5 4.5 0 0 0 0 9 4.5 4.5 0 0 0 3-1.2l2 2A7 7 0 0 1 12 11z"
                    />
                  </svg>
                }
              >
                Continue with Google
              </Button>

              <p className="text-center text-sm text-text-secondary">
                New here?{' '}
                <Link
                  to="/signup"
                  className="font-medium text-brand-300 hover:text-brand-200 hover:underline"
                >
                  Create an account
                </Link>
                .
              </p>

              {firebaseEnabled === false ? (
                <div className="rounded-xl border border-amber-500/30 bg-amber-500/[0.08] p-3 text-sm text-amber-100">
                  Firebase Web SDK is not configured. Add{' '}
                  <code className="font-mono">VITE_FIREBASE_*</code> environment
                  variables to enable authentication.
                </div>
              ) : null}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
