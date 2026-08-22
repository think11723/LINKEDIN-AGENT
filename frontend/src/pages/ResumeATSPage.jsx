import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Target,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Briefcase,
  GraduationCap,
  Code,
  Type,
  FileSearch,
  LayoutList,
  TrendingUp,
  Wand2,
  Linkedin,
  History,
  ListChecks,
} from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Textarea, Field, Input } from '../components/ui/Input.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { ErrorBanner, Skeleton, EmptyState } from '../components/ui/Feedback.jsx';
import { MotionPage } from '../components/ui/MotionPage.jsx';
import { QualityRing } from '../components/ui/QualityRing.jsx';
import { formatDateTime } from '../utils/date.js';
import { cn } from '../utils/cn.js';

const TONE_FOR_DIM = {
  keyword_match: 'good',
  skills_match: 'good',
  experience_relevance: 'neutral',
  education_relevance: 'neutral',
  title_alignment: 'neutral',
  formatting_readability: 'good',
  section_completeness: 'good',
};

const DIM_LABEL = {
  keyword_match: 'Keyword match',
  skills_match: 'Skills match',
  experience_relevance: 'Experience relevance',
  education_relevance: 'Education relevance',
  title_alignment: 'Title alignment',
  formatting_readability: 'Formatting & readability',
  section_completeness: 'Section completeness',
};

const PRIORITY_TONE = {
  high: 'danger',
  medium: 'warning',
  low: 'info',
};

function ScoreBar({ value, label }) {
  const tone =
    value >= 75 ? 'good' : value >= 50 ? 'warning' : 'danger';
  const color =
    tone === 'good'
      ? 'from-emerald-500 to-emerald-300'
      : tone === 'warning'
      ? 'from-amber-500 to-amber-300'
      : 'from-rose-500 to-rose-300';
  return (
    <div>
      <div className="flex items-center justify-between text-xs">
        <span className="text-text-muted">{label}</span>
        <span className="font-semibold tabular-nums text-zinc-100">
          {value}/100
        </span>
      </div>
      <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-white/[0.04]">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${value}%` }}
          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
          className={cn('h-full rounded-full bg-gradient-to-r', color)}
        />
      </div>
    </div>
  );
}

function KeywordChip({ text, kind }) {
  if (kind === 'matched') {
    return (
      <span className="inline-flex items-center gap-1 rounded-md border border-emerald-400/20 bg-emerald-500/15 px-2 py-0.5 text-xs text-emerald-200">
        <CheckCircle2 className="h-3 w-3" />
        {text}
      </span>
    );
  }
  if (kind === 'missing') {
    return (
      <span className="inline-flex items-center gap-1 rounded-md border border-rose-400/20 bg-rose-500/15 px-2 py-0.5 text-xs text-rose-200">
        <XCircle className="h-3 w-3" />
        {text}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-white/[0.08] bg-white/[0.04] px-2 py-0.5 text-xs text-text-secondary">
      {text}
    </span>
  );
}

export default function ResumeATSPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const api = useApi();
  const { toast } = useToast();

  const [resume, setResume] = useState(null);
  const [analyses, setAnalyses] = useState([]);
  const [active, setActive] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState(null);
  const [jobTitle, setJobTitle] = useState('');
  const [company, setCompany] = useState('');
  const [jdText, setJdText] = useState('');

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [r, a] = await Promise.all([
        api.getResume(id).catch(() => null),
        api.listResumeAnalyses(id).catch(() => []),
      ]);
      setResume(r);
      setAnalyses(Array.isArray(a) ? a : []);
      if (a && a.length > 0) {
        setActive(a[0]);
      }
      setErr(null);
    } catch (e) {
      setErr(e);
    } finally {
      setLoading(false);
    }
  }, [api, id]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleAnalyze(event) {
    event.preventDefault();
    if (!jdText.trim()) {
      toast.error('Job description is required.');
      return;
    }
    setSubmitting(true);
    try {
      const result = await api.analyzeResume(id, {
        job_title: jobTitle,
        company,
        job_description: jdText,
      });
      toast.success('ATS analysis complete.');
      setJdText('');
      setJobTitle('');
      setCompany('');
      setActive(result);
      await load();
    } catch (e) {
      toast.error('Analysis failed', e?.message);
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <MotionPage className="space-y-6 p-4 md:p-6 lg:p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40" />
      </MotionPage>
    );
  }

  if (!resume) {
    return (
      <MotionPage className="space-y-6 p-4 md:p-6 lg:p-8">
        <ErrorBanner error={err} onRetry={load} />
        <EmptyState
          title="Resume not found"
          description="Open the resume first and try again."
          action={
            <Button onClick={() => navigate('/resume')}>Back to Resume Studio</Button>
          }
        />
      </MotionPage>
    );
  }

  return (
    <MotionPage className="space-y-6 p-4 md:p-6 lg:p-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Link
          to={`/resume/${id}/edit`}
          className="inline-flex items-center gap-1.5 text-sm text-text-muted transition hover:text-zinc-100"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to editor
        </Link>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => navigate(`/resume/${id}/linkedin`)}
            leftIcon={<Linkedin className="h-3.5 w-3.5" />}
          >
            Create LinkedIn Post
          </Button>
        </div>
      </div>

      <header>
        <div className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-text-secondary">
          <Target className="h-3 w-3 text-brand-300" />
          ATS Compatibility
        </div>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight text-white sm:text-3xl">
          {resume.title || 'Untitled resume'}
        </h1>
        <p className="mt-1 text-sm text-text-secondary">
          Paste a Job Description below. The analyzer checks keyword match,
          skills match, experience relevance, title alignment, and
          resume structure. The output is deterministic — no fabricated
          numbers.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileSearch className="h-4 w-4 text-text-secondary" />
              New ATS check
            </CardTitle>
            <CardDescription>
              Paste a Job Description. The system will compare it to
              this resume and produce a 0–100 score.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleAnalyze} className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <Field id="jd-title" label="Job title" optional>
                  <Input
                    id="jd-title"
                    value={jobTitle}
                    onChange={(e) => setJobTitle(e.target.value)}
                    placeholder="Senior Software Engineer"
                  />
                </Field>
                <Field id="jd-company" label="Company" optional>
                  <Input
                    id="jd-company"
                    value={company}
                    onChange={(e) => setCompany(e.target.value)}
                    placeholder="Acme Corp"
                  />
                </Field>
              </div>
              <Field id="jd-text" label="Job description" required>
                <Textarea
                  id="jd-text"
                  rows={10}
                  value={jdText}
                  onChange={(e) => setJdText(e.target.value)}
                  placeholder="Paste the full Job Description here. Required skills, responsibilities, experience…"
                />
              </Field>
              <div className="flex justify-end">
                <Button
                  type="submit"
                  variant="brand"
                  loading={submitting}
                  leftIcon={<Wand2 className="h-4 w-4" />}
                >
                  {submitting ? 'Analyzing…' : 'Run ATS Analysis'}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        {active ? (
          <AnalysisView analysis={active} />
        ) : (
          <Card>
            <CardContent>
              <EmptyState
                icon={<History className="h-5 w-5" />}
                title="No analysis yet"
                description="Run your first ATS check to see the breakdown here."
              />
            </CardContent>
          </Card>
        )}
      </div>

      {analyses.length > 1 ? (
        <Card>
          <CardHeader>
            <CardTitle>Recent analyses</CardTitle>
            <CardDescription>Select an earlier run to view its breakdown.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {analyses.map((a) => (
                <button
                  key={a.id}
                  type="button"
                  onClick={() => setActive(a)}
                  className={cn(
                    'rounded-2xl border p-3 text-left transition',
                    a.id === active?.id
                      ? 'border-brand-400/40 bg-brand-500/[0.08]'
                      : 'border-white/[0.06] bg-white/[0.02] hover:border-white/[0.16]'
                  )}
                >
                  <div className="flex items-center justify-between">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-zinc-100">
                        {a.job_title || 'Untitled role'}
                      </div>
                      <div className="text-xs text-text-muted">
                        {a.company || '—'} · {formatDateTime(a.created_at)}
                      </div>
                    </div>
                    <div className="text-2xl font-semibold text-white">
                      {a.overall_score}
                      <span className="text-xs text-text-muted">/100</span>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}
    </MotionPage>
  );
}

function AnalysisView({ analysis }) {
  const breakdown = analysis.breakdown || {};
  const matched = analysis.matched_keywords || [];
  const missing = analysis.missing_keywords || [];
  const related = analysis.related_keywords || [];
  const improvements = analysis.improvements || [];
  const jd = analysis.jd_analysis || {};

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-text-secondary" />
              {analysis.job_title || 'ATS Compatibility'}
            </CardTitle>
            <CardDescription>
              {analysis.company || 'Job description'} · Run{' '}
              {formatDateTime(analysis.created_at)}
            </CardDescription>
          </div>
          <QualityRing
            score={analysis.overall_score}
            max={100}
            size={84}
            label={`Score ${analysis.overall_score} of 100`}
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-2 sm:grid-cols-2">
          {Object.entries(breakdown).map(([key, value]) => (
            <ScoreBar key={key} value={value || 0} label={DIM_LABEL[key] || key} />
          ))}
        </div>

        <div>
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-zinc-100">
            <CheckCircle2 className="h-4 w-4 text-emerald-300" />
            Matched keywords
            <Badge tone="success" size="sm">
              {matched.length}
            </Badge>
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {matched.length ? (
              matched.map((kw) => <KeywordChip key={kw} text={kw} kind="matched" />)
            ) : (
              <span className="text-xs text-text-muted">No matches</span>
            )}
          </div>
        </div>

        <div>
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-zinc-100">
            <XCircle className="h-4 w-4 text-rose-300" />
            Missing keywords
            <Badge tone="danger" size="sm">
              {missing.length}
            </Badge>
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {missing.length ? (
              missing.map((kw) => <KeywordChip key={kw} text={kw} kind="missing" />)
            ) : (
              <span className="text-xs text-text-muted">None — strong match</span>
            )}
          </div>
        </div>

        {related.length ? (
          <div>
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-zinc-100">
              <ListChecks className="h-4 w-4 text-brand-300" />
              Related keywords you already have
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {related.map((kw) => <KeywordChip key={kw} text={kw} />)}
            </div>
          </div>
        ) : null}

        {jd.required_skills && jd.required_skills.length ? (
          <div>
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-zinc-100">
              <Wand2 className="h-4 w-4 text-text-secondary" />
              Top requirements
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {jd.required_skills.map((kw) => (
                <span
                  key={kw}
                  className="inline-flex items-center gap-1 rounded-md border border-white/[0.08] bg-white/[0.04] px-2 py-0.5 text-xs text-zinc-200"
                >
                  {kw}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        <div>
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-zinc-100">
            <Target className="h-4 w-4 text-amber-300" />
            Improvement suggestions
          </h3>
          <ul className="space-y-2">
            {improvements.map((imp, idx) => (
              <li
                key={idx}
                className={cn(
                  'flex items-start gap-3 rounded-2xl border p-3',
                  imp.priority === 'high'
                    ? 'border-rose-400/20 bg-rose-500/[0.06]'
                    : imp.priority === 'medium'
                    ? 'border-amber-400/20 bg-amber-500/[0.06]'
                    : 'border-sky-400/20 bg-sky-500/[0.06]'
                )}
              >
                <Badge
                  tone={PRIORITY_TONE[imp.priority] || 'info'}
                  size="sm"
                >
                  {imp.priority}
                </Badge>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold text-zinc-100">
                    {imp.title}
                  </div>
                  <p className="mt-0.5 text-xs text-text-secondary">
                    {imp.detail}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}
