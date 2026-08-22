import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  ExternalLink,
  Target,
  Sparkles,
  Linkedin,
  FileText,
  CheckCircle2,
  Save,
  Trash2,
  Building2,
  MapPin,
  Wallet,
  Calendar,
  ListChecks,
  Target as TargetIcon,
} from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Textarea, Select, Field } from '../components/ui/Input.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { ConfirmDialog } from '../components/ConfirmDialog.jsx';
import { ErrorBanner, Skeleton, EmptyState } from '../components/ui/Feedback.jsx';
import { MotionPage } from '../components/ui/MotionPage.jsx';
import { QualityRing } from '../components/ui/QualityRing.jsx';
import { formatDateTime } from '../utils/date.js';

const APP_STATUSES = [
  'saved',
  'preparing',
  'applied',
  'screening',
  'interview',
  'offer',
  'rejected',
  'withdrawn',
];
const POST_TYPES = [
  { value: 'career_achievement', label: 'Career achievement' },
  { value: 'project_launch', label: 'Project launch' },
  { value: 'learning_journey', label: 'Learning journey' },
  { value: 'job_experience', label: 'Job experience' },
  { value: 'certification', label: 'Certification' },
  { value: 'technical_deep_dive', label: 'Technical deep dive' },
  { value: 'career_milestone', label: 'Career milestone' },
];
const ANGLES = [
  { value: 'researching', label: 'Researching' },
  { value: 'applying', label: 'Applying' },
  { value: 'employed', label: 'Employed' },
];

export default function JobDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const api = useApi();
  const { toast } = useToast();

  const [job, setJob] = useState(null);
  const [application, setApplication] = useState(null);
  const [matches, setMatches] = useState([]);
  const [events, setEvents] = useState([]);
  const [resumes, setResumes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [matching, setMatching] = useState(false);
  const [optimizing, setOptimizing] = useState(false);
  const [posting, setPosting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const [appForm, setAppForm] = useState({
    resume_id: '',
    status: 'saved',
    notes: '',
    next_action: '',
    next_action_date: '',
    recruiter_name: '',
    recruiter_contact: '',
    salary: '',
    location: '',
  });

  const [linkedinForm, setLinkedinForm] = useState({
    resume_id: '',
    post_type: 'career_achievement',
    tone: 'professional',
    angle: 'researching',
  });

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [j, m, a, r] = await Promise.all([
        api.getJob(id).catch(() => null),
        api.listJobMatches(id).catch(() => []),
        api.getApplicationByJob ? api.getApplicationByJob(id).catch(() => null) : Promise.resolve(null),
        api.listResumes ? api.listResumes().catch(() => []) : Promise.resolve([]),
      ]);
      setJob(j);
      setMatches(m || []);
      setResumes(r || []);
      if (a) {
        setApplication(a);
        setAppForm({
          resume_id: a.resume_id || '',
          status: a.status || 'saved',
          notes: a.notes || '',
          next_action: a.next_action || '',
          next_action_date: a.next_action_date || '',
          recruiter_name: a.recruiter_name || '',
          recruiter_contact: a.recruiter_contact || '',
          salary: a.salary || '',
          location: a.location || '',
        });
        const ev = await api.listApplicationEvents(a.id).catch(() => []);
        setEvents(ev || []);
      } else {
        setApplication(null);
        setEvents([]);
      }
    } catch (e) {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [api, id]);

  useEffect(() => {
    load();
  }, [load]);

  async function patchApplication(patch) {
    if (!application?.id) return null;
    try {
      const updated = await api.updateApplication(application.id, patch);
      setApplication(updated);
      return updated;
    } catch (e) {
      toast.error('Update failed', e?.message);
      return null;
    }
  }

  async function handleAnalyze() {
    setAnalyzing(true);
    try {
      const updated = await api.analyzeJob(id);
      setJob(updated);
      toast.success('JD analyzed.');
    } catch (e) {
      toast.error('Analyze failed', e?.message);
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleMatch() {
    setMatching(true);
    try {
      const out = await api.matchResumes(id, {});
      setMatches(out || []);
      toast.success(`Matched ${out?.length || 0} resume(s).`);
    } catch (e) {
      toast.error('Match failed', e?.message);
    } finally {
      setMatching(false);
    }
  }

  async function handleOptimize(resumeId) {
    setOptimizing(true);
    try {
      const result = await api.optimizeResume(id, { job_id: id, resume_id: resumeId });
      toast.success('Optimized copy created.');
      navigate(`/resume/${result.id}/edit`);
    } catch (e) {
      toast.error('Optimize failed', e?.message);
    } finally {
      setOptimizing(false);
    }
  }

  async function handleLinkedIn(event) {
    event.preventDefault();
    setPosting(true);
    try {
      const res = await api.linkedinFromJob(id, linkedinForm);
      toast.success('LinkedIn draft created.');
      navigate(`/drafts/${res.draft_id}`);
    } catch (e) {
      toast.error('LinkedIn failed', e?.message);
    } finally {
      setPosting(false);
    }
  }

  async function handleCreateApplication(event) {
    event.preventDefault();
    try {
      const created = await api.createApplication({
        job_id: id,
        ...appForm,
      });
      setApplication(created);
      toast.success('Application created.');
    } catch (e) {
      toast.error('Create failed', e?.message);
    }
  }

  async function handleDelete() {
    if (!application?.id) return;
    try {
      await api.deleteApplication(application.id);
      setApplication(null);
      setConfirmDelete(false);
      toast.success('Application removed.');
    } catch (e) {
      toast.error('Delete failed', e?.message);
    } finally {
      setConfirmDelete(false);
    }
  }

  if (loading) {
    return (
      <MotionPage className="space-y-6 p-4 md:p-6 lg:p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64" />
      </MotionPage>
    );
  }

  if (!job) {
    return (
      <MotionPage className="space-y-6 p-4 md:p-6 lg:p-8">
        <Link
          to="/job-tracker"
          className="inline-flex items-center gap-1.5 text-sm text-text-muted transition hover:text-zinc-100"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to Job Tracker
        </Link>
        <EmptyState
          title="Job not found"
          description="It may have been removed or never existed."
          action={
            <Button onClick={() => navigate('/job-tracker')}>
              Back to Job Tracker
            </Button>
          }
        />
      </MotionPage>
    );
  }

  const jd = job.jd_analysis || {};

  return (
    <MotionPage className="space-y-6 p-4 md:p-6 lg:p-8">
      <Link
        to="/job-tracker"
        className="inline-flex items-center gap-1.5 text-sm text-text-muted transition hover:text-zinc-100"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to Job Tracker
      </Link>

      <header className="space-y-2">
        <div className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-text-secondary">
          <FileText className="h-3 w-3 text-accent-400" />
          Job
        </div>
        <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">
          {job.title || 'Untitled role'}
        </h1>
        <div className="flex flex-wrap items-center gap-3 text-sm text-text-secondary">
          {job.company ? (
            <span className="inline-flex items-center gap-1">
              <Building2 className="h-3.5 w-3.5" />
              {job.company}
            </span>
          ) : null}
          {job.location ? (
            <span className="inline-flex items-center gap-1">
              <MapPin className="h-3.5 w-3.5" />
              {job.location}
            </span>
          ) : null}
          {(job.salary_min || job.salary_max) ? (
            <span className="inline-flex items-center gap-1">
              <Wallet className="h-3.5 w-3.5" />
              {job.salary_min || '?'}
              {job.salary_min && job.salary_max ? '–' : ''}
              {job.salary_max || ''} {job.salary_currency || ''}
            </span>
          ) : null}
          {job.deadline ? (
            <span className="inline-flex items-center gap-1">
              <Calendar className="h-3.5 w-3.5" />
              Deadline: {job.deadline}
            </span>
          ) : null}
          {job.job_url ? (
            <a
              className="inline-flex items-center gap-1 text-brand-300 hover:underline"
              href={job.job_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Original <ExternalLink className="h-3.5 w-3.5" />
            </a>
          ) : null}
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>JD Analysis</CardTitle>
                <CardDescription>
                  Top requirements, keywords, and responsibilities.
                </CardDescription>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleAnalyze}
                loading={analyzing}
                leftIcon={<Sparkles className="h-3.5 w-3.5" />}
              >
                {analyzing ? 'Analyzing…' : jd.role_title ? 'Re-analyze' : 'Analyze JD'}
              </Button>
            </CardHeader>
            <CardContent>
              {jd.role_title ? (
                <div className="space-y-4">
                  <div className="grid gap-2 sm:grid-cols-2">
                    <div>
                      <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                        Role
                      </div>
                      <div className="text-sm text-zinc-100">
                        {jd.role_title}
                      </div>
                    </div>
                    {jd.experience_years ? (
                      <div>
                        <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">
                          Experience
                        </div>
                        <div className="text-sm text-zinc-100">
                          {jd.experience_years}
                        </div>
                      </div>
                    ) : null}
                  </div>
                  {jd.required_skills && jd.required_skills.length > 0 ? (
                    <div>
                      <div className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-text-muted">
                        Required skills
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {jd.required_skills.map((s) => (
                          <Badge key={s} tone="brand" size="sm">
                            {s}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {jd.responsibilities && jd.responsibilities.length > 0 ? (
                    <div>
                      <div className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-text-muted">
                        Responsibilities
                      </div>
                      <ul className="space-y-1.5 text-sm text-zinc-200">
                        {(jd.responsibilities || []).slice(0, 6).map((r, idx) => (
                          <li key={idx} className="flex items-start gap-2">
                            <ListChecks className="mt-0.5 h-3.5 w-3.5 shrink-0 text-text-muted" />
                            <span>{r}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              ) : (
                <p className="text-sm text-text-muted">
                  Click <strong>Analyze JD</strong> to extract role,
                  requirements, keywords, and responsibilities.
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Resume match</CardTitle>
                <CardDescription>
                  Match all your resumes against this Job Description.
                </CardDescription>
              </div>
              <Button
                variant="secondary"
                size="sm"
                onClick={handleMatch}
                loading={matching}
                leftIcon={<TargetIcon className="h-3.5 w-3.5" />}
              >
                {matching ? 'Matching…' : 'Run match'}
              </Button>
            </CardHeader>
            <CardContent>
              {matches.length === 0 ? (
                <p className="text-sm text-text-muted">
                  No matches yet. Click <strong>Run match</strong> to
                  compare your resumes against this JD.
                </p>
              ) : (
                <ul className="space-y-3">
                  {matches.map((m) => (
                    <li
                      key={m.id}
                      className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-3"
                    >
                      <div className="flex items-center gap-3">
                        <QualityRing
                          score={m.overall_score}
                          max={100}
                          size={56}
                          stroke={4}
                        />
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-sm font-semibold text-zinc-100">
                            {m.resume_title || 'Untitled resume'}
                          </div>
                          {m.resume_target_role ? (
                            <div className="truncate text-xs text-text-muted">
                              Target: {m.resume_target_role}
                            </div>
                          ) : null}
                        </div>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => handleOptimize(m.resume_id)}
                          loading={optimizing}
                          leftIcon={<Sparkles className="h-3.5 w-3.5" />}
                        >
                          Optimize
                        </Button>
                      </div>
                      <div className="mt-2 text-xs text-text-muted">
                        Missing: {(m.missing_keywords || []).slice(0, 6).join(', ') || 'None'}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Job description</CardTitle>
              <CardDescription>
                The original JD is preserved exactly as imported.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-xl border border-white/[0.06] bg-white/[0.02] p-3 text-sm text-zinc-200">
                {job.description || 'No description captured yet.'}
              </pre>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Application</CardTitle>
                <CardDescription>Track this job's lifecycle.</CardDescription>
              </div>
              {application ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setConfirmDelete(true)}
                  className="text-text-muted hover:text-rose-300"
                  leftIcon={<Trash2 className="h-3.5 w-3.5" />}
                >
                  Remove
                </Button>
              ) : null}
            </CardHeader>
            <CardContent>
              {application ? (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    patchApplication({});
                    toast.success('Application updated.');
                  }}
                  className="space-y-3"
                >
                  <div className="grid gap-2 sm:grid-cols-2">
                    <Field label="Status">
                      <Select
                        value={application.status}
                        onChange={(e) => patchApplication({ status: e.target.value })}
                      >
                        {APP_STATUSES.map((s) => (
                          <option key={s} value={s}>
                            {s.charAt(0).toUpperCase() + s.slice(1)}
                          </option>
                        ))}
                      </Select>
                    </Field>
                    <Field label="Next action">
                      <Input
                        value={application.next_action || ''}
                        onChange={(e) => patchApplication({ next_action: e.target.value })}
                      />
                    </Field>
                    <Field label="Recruiter">
                      <Input
                        value={application.recruiter_name || ''}
                        onChange={(e) => patchApplication({ recruiter_name: e.target.value })}
                      />
                    </Field>
                    <Field label="Next action date">
                      <Input
                        value={application.next_action_date || ''}
                        onChange={(e) => patchApplication({ next_action_date: e.target.value })}
                      />
                    </Field>
                  </div>
                  <Field label="Notes">
                    <Textarea
                      rows={3}
                      value={application.notes || ''}
                      onChange={(e) => patchApplication({ notes: e.target.value })}
                    />
                  </Field>
                  <div className="flex justify-end">
                    <Button type="submit" variant="brand" size="sm">
                      Save application
                    </Button>
                  </div>
                </form>
              ) : (
                <EmptyState
                  size="sm"
                  icon={<ListChecks className="h-4 w-4" />}
                  title="Not tracked yet"
                  description="Create an application to track this job's status, notes, and next steps."
                  action={
                    <Button
                      variant="brand"
                      size="sm"
                      onClick={() =>
                        setAppForm((p) => ({
                          ...p,
                          resume_id: resumes[0]?.id || '',
                        }))
                      }
                    >
                      Create application
                    </Button>
                  }
                />
              )}
              {application ? null : (
                <form
                  onSubmit={handleCreateApplication}
                  className="mt-3 space-y-2"
                >
                  <Field label="Resume">
                    <Select
                      value={appForm.resume_id}
                      onChange={(e) => setAppForm((p) => ({ ...p, resume_id: e.target.value }))}
                      required
                    >
                      <option value="">— select —</option>
                      {resumes.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.title || 'Untitled resume'}
                        </option>
                      ))}
                    </Select>
                  </Field>
                  <Button type="submit" variant="brand" size="sm" disabled={!appForm.resume_id}>
                    Create application
                  </Button>
                </form>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Linkedin className="h-4 w-4 text-sky-300" />
                LinkedIn post
              </CardTitle>
              <CardDescription>
                Pick a resume and an angle. The post is grounded in
                your experience — never deceptive.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleLinkedIn} className="space-y-3">
                <Field label="Resume">
                  <Select
                    value={linkedinForm.resume_id}
                    onChange={(e) =>
                      setLinkedinForm((p) => ({ ...p, resume_id: e.target.value }))
                    }
                    required
                  >
                    <option value="">— select —</option>
                    {resumes.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.title || 'Untitled resume'}
                      </option>
                    ))}
                  </Select>
                </Field>
                <div className="grid gap-2 sm:grid-cols-2">
                  <Field label="Post type">
                    <Select
                      value={linkedinForm.post_type}
                      onChange={(e) =>
                        setLinkedinForm((p) => ({ ...p, post_type: e.target.value }))
                      }
                    >
                      {POST_TYPES.map((p) => (
                        <option key={p.value} value={p.value}>
                          {p.label}
                        </option>
                      ))}
                    </Select>
                  </Field>
                  <Field label="Angle">
                    <Select
                      value={linkedinForm.angle}
                      onChange={(e) =>
                        setLinkedinForm((p) => ({ ...p, angle: e.target.value }))
                      }
                    >
                      {ANGLES.map((a) => (
                        <option key={a.value} value={a.value}>
                          {a.label}
                        </option>
                      ))}
                    </Select>
                  </Field>
                </div>
                <div className="flex justify-end">
                  <Button
                    type="submit"
                    variant="brand"
                    size="sm"
                    loading={posting}
                    disabled={!linkedinForm.resume_id}
                    leftIcon={<Sparkles className="h-3.5 w-3.5" />}
                  >
                    Generate
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          {events.length > 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>History</CardTitle>
                <CardDescription>Application events in order.</CardDescription>
              </CardHeader>
              <CardContent>
                <ol className="space-y-1.5 text-sm">
                  {events.map((ev) => (
                    <li
                      key={ev.id}
                      className="flex items-center gap-2 text-zinc-300"
                    >
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-300" />
                      <span className="text-xs uppercase tracking-wider text-text-muted">
                        {ev.event_type}
                      </span>
                      <span className="text-text-muted text-xs">
                        {formatDateTime(ev.timestamp)}
                      </span>
                    </li>
                  ))}
                </ol>
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>

      <ConfirmDialog
        open={confirmDelete}
        title="Remove this application?"
        description="The job stays saved. The application and its history are removed."
        confirmLabel="Remove"
        danger
        confirming={false}
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(false)}
      />
    </MotionPage>
  );
}
