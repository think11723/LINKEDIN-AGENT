import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Linkedin,
  Sparkles,
  Check,
  X,
  Wand2,
  AlertCircle,
  FileText,
} from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Textarea, Field } from '../components/ui/Input.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { ErrorBanner, Skeleton, EmptyState } from '../components/ui/Feedback.jsx';
import { MotionPage } from '../components/ui/MotionPage.jsx';
import { LinkedInPreview } from '../components/ui/LinkedInPreview.jsx';

const POST_TYPES = [
  { value: 'project_launch', label: 'Project launch' },
  { value: 'career_achievement', label: 'Career achievement' },
  { value: 'learning_journey', label: 'Learning journey' },
  { value: 'job_experience', label: 'Job experience' },
  { value: 'certification', label: 'Certification' },
  { value: 'technical_deep_dive', label: 'Technical deep dive' },
  { value: 'career_milestone', label: 'Career milestone' },
];

const TONES = [
  { value: 'professional', label: 'Professional' },
  { value: 'storytelling', label: 'Storytelling' },
  { value: 'educational', label: 'Educational' },
  { value: 'founder', label: 'Founder' },
  { value: 'opinion', label: 'Opinion' },
];

const SECTIONS = [
  { value: '', label: 'Whole resume' },
  { value: 'summary', label: 'Professional summary' },
  { value: 'experience', label: 'Most recent role' },
  { value: 'projects', label: 'A project' },
  { value: 'certifications', label: 'A certification' },
  { value: 'achievements', label: 'An achievement' },
];

export default function ResumeLinkedInPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const api = useApi();
  const { toast } = useToast();

  const [resume, setResume] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [section, setSection] = useState('');
  const [sectionId, setSectionId] = useState('');
  const [postType, setPostType] = useState('project_launch');
  const [tone, setTone] = useState('professional');
  const [result, setResult] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!id) return;
      setLoading(true);
      try {
        const data = await api.getResume(id);
        if (!cancelled) {
          setResume(data);
          setErr(null);
        }
      } catch (e) {
        if (!cancelled) setErr(e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [api, id]);

  async function handleGenerate(event) {
    event.preventDefault();
    setSubmitting(true);
    setResult(null);
    try {
      const res = await api.createLinkedInFromResume(id, {
        post_type: postType,
        tone,
        section,
        section_id: sectionId,
      });
      setResult(res);
      toast.success('LinkedIn post draft created.');
    } catch (e) {
      toast.error('Generation failed', e?.message);
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
        <ErrorBanner error={err} />
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
      <Link
        to={`/resume/${id}/edit`}
        className="inline-flex items-center gap-1.5 text-sm text-text-muted transition hover:text-zinc-100"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to editor
      </Link>

      <header>
        <div className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-text-secondary">
          <Linkedin className="h-3 w-3 text-sky-300" />
          Resume → LinkedIn
        </div>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight text-white sm:text-3xl">
          Create a LinkedIn post from your resume
        </h1>
        <p className="mt-1 max-w-xl text-sm text-text-secondary">
          Pick a section, set the angle, and the existing AI writer +
          reviewer produce a real LinkedIn post. The result is a
          normal draft that flows through your existing approval
          workflow.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Wand2 className="h-4 w-4 text-text-secondary" />
              Choose angle
            </CardTitle>
            <CardDescription>
              We never invent metrics. The post uses only what's in
              your resume.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleGenerate} className="space-y-3">
              <Field id="li-section" label="Section to focus on">
                <select
                  id="li-section"
                  className="input-base h-10 appearance-none pr-9"
                  value={section}
                  onChange={(e) => setSection(e.target.value)}
                >
                  {SECTIONS.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </Field>
              {section && section !== 'summary' ? (
                <Field id="li-section-id" label="Section item" optional>
                  <Input
                    id="li-section-id"
                    value={sectionId}
                    onChange={(e) => setSectionId(e.target.value)}
                    placeholder="Match the name of the item (e.g. role title, project name)"
                  />
                </Field>
              ) : null}
              <div className="grid gap-3 sm:grid-cols-2">
                <Field id="li-type" label="Post type">
                  <select
                    id="li-type"
                    className="input-base h-10 appearance-none pr-9"
                    value={postType}
                    onChange={(e) => setPostType(e.target.value)}
                  >
                    {POST_TYPES.map((p) => (
                      <option key={p.value} value={p.value}>
                        {p.label}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field id="li-tone" label="Tone">
                  <select
                    id="li-tone"
                    className="input-base h-10 appearance-none pr-9"
                    value={tone}
                    onChange={(e) => setTone(e.target.value)}
                  >
                    {TONES.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>
              <div className="flex justify-end pt-2">
                <Button
                  type="submit"
                  variant="brand"
                  loading={submitting}
                  leftIcon={<Sparkles className="h-4 w-4" />}
                >
                  {submitting ? 'Generating…' : 'Generate LinkedIn Post'}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        {result ? (
          <motion.div
            key="result"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="space-y-3"
          >
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Check className="h-4 w-4 text-emerald-300" />
                  LinkedIn draft created
                </CardTitle>
                <CardDescription>
                  {result.source_label || 'Resume section'} · Open the
                  draft to refine, approve, and publish.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="brand"
                    onClick={() => navigate(`/drafts/${result.draft_id}`)}
                    rightIcon={<ArrowLeft className="h-4 w-4 -rotate-180" />}
                  >
                    Open Draft
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => setResult(null)}
                    leftIcon={<Wand2 className="h-4 w-4" />}
                  >
                    Generate another
                  </Button>
                </div>
              </CardContent>
            </Card>
            <ResultPreview
              draftId={result.draft_id}
            />
          </motion.div>
        ) : (
          <Card>
            <CardContent>
              <EmptyState
                icon={<FileText className="h-5 w-5" />}
                title="No draft yet"
                description="Pick a section, choose a post type and tone, and the AI will produce a real LinkedIn post grounded in your resume."
              />
            </CardContent>
          </Card>
        )}
      </div>
    </MotionPage>
  );
}

function ResultPreview({ draftId }) {
  const api = useApi();
  const [draft, setDraft] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await api.getDraft(draftId);
        if (!cancelled) setDraft(data);
      } catch {
        // ignore — the user can still open the draft in the
        // library.
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [api, draftId]);

  if (loading) return <Skeleton className="h-72" />;
  if (!draft) return null;
  return (
    <LinkedInPreview
      authorName="You"
      authorHeadline="on LinkedIn"
      content={draft.content}
      hashtags={draft.hashtags || []}
    />
  );
}
