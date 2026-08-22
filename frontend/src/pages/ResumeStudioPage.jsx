import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Briefcase,
  Upload,
  Plus,
  ArrowRight,
  FileText,
  Sparkles,
  TrendingUp,
  CheckCircle2,
  BarChart3,
  Clock,
  Target,
  Inbox,
  Linkedin,
} from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Field } from '../components/ui/Input.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { ErrorBanner, EmptyState, Skeleton, Spinner } from '../components/ui/Feedback.jsx';
import { MotionPage } from '../components/ui/MotionPage.jsx';
import { formatDateTime } from '../utils/date.js';
import { cn } from '../utils/cn.js';

function StatCard({ label, value, icon: Icon, tone = 'brand' }) {
  const toneClass = {
    brand: 'text-brand-300 bg-brand-500/15 border-brand-400/20',
    accent: 'text-accent-400 bg-accent-500/15 border-accent-400/20',
    success: 'text-emerald-300 bg-emerald-500/15 border-emerald-400/20',
    info: 'text-sky-300 bg-sky-500/15 border-sky-400/20',
  }[tone];
  return (
    <motion.div
      whileHover={{ y: -2 }}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
      className="panel relative flex flex-col gap-3 p-5"
    >
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">
          {label}
        </div>
        <span
          className={cn(
            'inline-flex h-9 w-9 items-center justify-center rounded-xl border',
            toneClass
          )}
        >
          <Icon className="h-4 w-4" />
        </span>
      </div>
      <div className="text-3xl font-semibold tracking-tight text-white">
        {value}
      </div>
    </motion.div>
  );
}

export default function ResumeStudioPage() {
  const api = useApi();
  const navigate = useNavigate();
  const { toast } = useToast();
  const fileInputRef = useRef(null);

  const [stats, setStats] = useState(null);
  const [resumes, setResumes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState('');
  const [showNewForm, setShowNewForm] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [d, r] = await Promise.all([
        api.getResumeDashboard().catch(() => null),
        api.listResumes().catch(() => []),
      ]);
      setStats(d);
      setResumes(Array.isArray(r) ? r : []);
      setError(null);
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleUploadFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    const title = file.name.replace(/\.(pdf|docx)$/i, '').replace(/[_-]+/g, ' ').trim();
    try {
      setUploading(true);
      const result = await api.uploadResume(file, title || 'Untitled resume');
      const id = result?.resume?._id || result?.resume?.id;
      toast.success('Resume uploaded and parsed.');
      if (id) {
        navigate(`/resume/${id}/edit`);
      } else {
        await load();
      }
    } catch (e) {
      const detail = e?.message || 'Upload failed.';
      if (!/Unsupported file type/.test(detail)) {
        toast.error('Upload failed', detail);
      } else {
        toast.error('Unsupported file type', 'Please upload a PDF or DOCX.');
      }
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  async function handleCreate() {
    const title = newTitle.trim();
    if (!title) {
      toast.error('Title is required.');
      return;
    }
    try {
      setCreating(true);
      const created = await api.createResume({ title });
      toast.success('Resume created.');
      navigate(`/resume/${created.id}/edit`);
    } catch (e) {
      toast.error('Create failed', e?.message);
    } finally {
      setCreating(false);
    }
  }

  return (
    <MotionPage className="space-y-6 p-4 md:p-6 lg:p-8">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-text-secondary">
            <Briefcase className="h-3 w-3 text-brand-300" />
            Career
          </div>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            <span className="text-text-secondary">AI </span>
            <span className="gradient-text">Resume Studio</span>
          </h1>
          <p className="mt-1 max-w-xl text-sm text-text-secondary">
            Upload your resume, analyse it against a Job Description, optimize
            it, and create LinkedIn content — all in one workspace.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx"
            className="hidden"
            onChange={handleUploadFile}
          />
          <Button
            variant="secondary"
            size="md"
            onClick={() => fileInputRef.current?.click()}
            loading={uploading}
            leftIcon={<Upload className="h-4 w-4" />}
          >
            Upload PDF / DOCX
          </Button>
          <Button
            variant="brand"
            size="md"
            onClick={() => setShowNewForm(true)}
            leftIcon={<Plus className="h-4 w-4" />}
          >
            New Resume
          </Button>
        </div>
      </header>

      <ErrorBanner error={error} onRetry={load} />

      <AnimatePresence>
        {showNewForm ? (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
          >
            <Card>
              <CardHeader>
                <CardTitle>Create a new resume</CardTitle>
                <CardDescription>You can edit and upload content next.</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-end">
                <div className="flex-1">
                  <Field label="Title">
                    <Input
                      placeholder="e.g. AI Engineer Resume"
                      value={newTitle}
                      onChange={(e) => setNewTitle(e.target.value)}
                      autoFocus
                    />
                  </Field>
                </div>
                <Button
                  variant="brand"
                  onClick={handleCreate}
                  loading={creating}
                  rightIcon={<ArrowRight className="h-4 w-4" />}
                >
                  Create
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    setShowNewForm(false);
                    setNewTitle('');
                  }}
                >
                  Cancel
                </Button>
              </CardContent>
            </Card>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Resumes" value={stats?.resume_count ?? 0} icon={FileText} tone="brand" />
        <StatCard
          label="Avg ATS Score"
          value={stats?.average_ats_score ?? 0}
          icon={Target}
          tone="success"
        />
        <StatCard
          label="Recent Analyses"
          value={stats?.recent_analyses?.length ?? 0}
          icon={BarChart3}
          tone="accent"
        />
        <StatCard
          label="LinkedIn Posts"
          value={0}
          icon={Linkedin}
          tone="info"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Your resumes</CardTitle>
                <CardDescription>Edit, optimize, or analyze against a job.</CardDescription>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={load}
                leftIcon={<Clock className="h-3.5 w-3.5" />}
              >
                Refresh
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, idx) => (
                  <Skeleton key={idx} className="h-16" />
                ))}
              </div>
            ) : resumes.length === 0 ? (
              <EmptyState
                icon={<Inbox className="h-5 w-5" />}
                title="No resumes yet"
                description="Upload a PDF/DOCX or create a new one to get started."
                action={
                  <div className="flex gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => fileInputRef.current?.click()}
                      leftIcon={<Upload className="h-4 w-4" />}
                    >
                      Upload
                    </Button>
                    <Button
                      variant="brand"
                      size="sm"
                      onClick={() => setShowNewForm(true)}
                      leftIcon={<Plus className="h-4 w-4" />}
                    >
                      New Resume
                    </Button>
                  </div>
                }
              />
            ) : (
              <ul className="space-y-2">
                {resumes.map((resume, idx) => (
                  <motion.li
                    key={resume.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.04, duration: 0.22 }}
                  >
                    <button
                      type="button"
                      onClick={() => navigate(`/resume/${resume.id}/edit`)}
                      className="group w-full rounded-2xl border border-white/[0.06] bg-white/[0.02] p-3 text-left transition hover:border-white/[0.16] hover:bg-white/[0.04]"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-semibold text-zinc-100">
                            {resume.title || 'Untitled resume'}
                          </div>
                          {resume.target_role ? (
                            <div className="mt-0.5 truncate text-xs text-text-muted">
                              Target: {resume.target_role}
                            </div>
                          ) : null}
                        </div>
                        <Badge tone="brand" size="sm">
                          {resume.source_type === 'uploaded_pdf' || resume.source_type === 'uploaded_docx'
                            ? 'Uploaded'
                            : 'Manual'}
                        </Badge>
                        <ArrowRight className="h-3.5 w-3.5 text-text-muted opacity-0 transition group-hover:translate-x-0.5 group-hover:opacity-100" />
                      </div>
                    </button>
                  </motion.li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent analyses</CardTitle>
            <CardDescription>Your last few ATS runs.</CardDescription>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-2">
                {Array.from({ length: 2 }).map((_, idx) => (
                  <Skeleton key={idx} className="h-12" />
                ))}
              </div>
            ) : stats?.recent_analyses?.length ? (
              <ul className="space-y-2">
                {stats.recent_analyses.map((a) => (
                  <li
                    key={a.id}
                    className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-medium text-zinc-100">
                          {a.job_title || 'Untitled role'}
                        </div>
                        <div className="text-xs text-text-muted">
                          {a.company || '—'}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-base font-semibold text-white">
                          {a.overall_score}
                          <span className="text-xs text-text-muted">/100</span>
                        </div>
                        <div className="text-[11px] text-text-muted">
                          {formatDateTime(a.created_at)}
                        </div>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                size="sm"
                icon={<BarChart3 className="h-4 w-4" />}
                title="No analyses yet"
                description="Open a resume and run an ATS check against a job."
              />
            )}
          </CardContent>
        </Card>
      </div>
    </MotionPage>
  );
}
