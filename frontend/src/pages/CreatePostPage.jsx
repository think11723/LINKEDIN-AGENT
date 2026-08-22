import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Sparkles,
  ArrowRight,
  Link2,
  FileText,
  Github,
  CheckCircle2,
  Wand2,
  Eye,
  AlertCircle,
  RotateCcw,
  Lightbulb,
} from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useToast } from '../context/ToastContext.jsx';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
  CardFooter,
} from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Textarea, Field } from '../components/ui/Input.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { PageHeader } from '../components/ui/PageHeader.jsx';
import { SegmentedTabs } from '../components/ui/SegmentedTabs.jsx';
import { StepProgress } from '../components/ui/StepProgress.jsx';
import { LinkedInPreview } from '../components/ui/LinkedInPreview.jsx';
import { SourcePreviewCard } from '../components/ui/SourcePreviewCard.jsx';
import { ErrorBanner, Spinner, EmptyState } from '../components/ui/Feedback.jsx';

const MODE_OPTIONS = [
  {
    value: 'topic',
    label: 'From Topic',
    description: 'Describe the post you want and let our writer draft it.',
    icon: <FileText className="h-5 w-5" />,
  },
  {
    value: 'source',
    label: 'From URL',
    description: 'Paste a GitHub repo, blog post, or docs page to summarize.',
    icon: <Link2 className="h-5 w-5" />,
  },
];

const TOPIC_PROGRESS_STEPS = [
  { id: 'plan', label: 'Planning post', hint: 'Intent, audience, tone' },
  { id: 'write', label: 'Writing draft', hint: 'LinkedIn-native format' },
  { id: 'review', label: 'Reviewing content', hint: 'Quality + score' },
];

const SOURCE_PROGRESS_STEPS = [
  { id: 'fetch', label: 'Fetching source', hint: 'SSRF-safe HTTP' },
  { id: 'analyze', label: 'Analyzing content', hint: 'Extracting insights' },
  { id: 'write', label: 'Writing draft', hint: 'LinkedIn-native format' },
  { id: 'review', label: 'Reviewing content', hint: 'Quality + score' },
];

export default function CreatePostPage() {
  const api = useApi();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [mode, setMode] = useState('topic');

  // Topic mode state.
  const [topic, setTopic] = useState('');
  const [intent, setIntent] = useState('');
  const [audience, setAudience] = useState('');
  const [tone, setTone] = useState('');
  const [topicSubmitting, setTopicSubmitting] = useState(false);
  const [topicError, setTopicError] = useState(null);
  const [topicResult, setTopicResult] = useState(null);

  // Source mode state.
  const [sourceUrl, setSourceUrl] = useState('');
  const [sourceOptionalTopic, setSourceOptionalTopic] = useState('');
  const [sourceStage, setSourceStage] = useState('idle');
  const [sourceError, setSourceError] = useState(null);
  const [sourcePreview, setSourcePreview] = useState(null);
  const [sourceResult, setSourceResult] = useState(null);

  // ---- Topic mode ----
  async function handleTopicGenerate() {
    if (!topic.trim()) {
      toast.error('Please enter a topic.');
      return;
    }
    setTopicSubmitting(true);
    setTopicError(null);
    setTopicResult(null);
    try {
      const response = await api.generateContent({
        topic: topic.trim(),
        intent: intent || undefined,
        audience: audience || undefined,
        tone: tone || undefined,
      });
      setTopicResult(response);
      toast.success('Draft generated.');
    } catch (err) {
      setTopicError(err);
      toast.error('Generation failed', err?.message);
    } finally {
      setTopicSubmitting(false);
    }
  }

  // ---- Source mode: analyze ----
  async function handleAnalyzeSource() {
    if (!sourceUrl.trim()) {
      toast.error('Please enter a URL.');
      return;
    }
    setSourceStage('analyzing');
    setSourceError(null);
    setSourcePreview(null);
    setSourceResult(null);
    try {
      const preview = await api.previewSource(sourceUrl.trim());
      setSourcePreview(preview);
      setSourceStage('analyzed');
    } catch (err) {
      setSourceError(err);
      setSourceStage('failure');
      toast.error('Could not read this source', err?.message);
    }
  }

  // ---- Source mode: generate ----
  async function handleSourceGenerate() {
    if (!sourcePreview) {
      toast.error('Analyze a source first.');
      return;
    }
    setSourceStage('generating');
    setSourceError(null);
    setSourceResult(null);
    try {
      const response = await api.generateContent({
        source_url: sourcePreview.source?.url || sourceUrl.trim(),
        topic: sourceOptionalTopic.trim() || undefined,
      });
      setSourceResult(response);
      setSourceStage('success');
      toast.success('Draft generated.');
    } catch (err) {
      setSourceError(err);
      setSourceStage('failure');
      toast.error('Generation failed', err?.message);
    }
  }

  function resetSource() {
    setSourceStage('idle');
    setSourceError(null);
    setSourcePreview(null);
    setSourceResult(null);
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      <PageHeader
        eyebrow="Workspace"
        title="Create LinkedIn Post"
        subtitle="Generate a draft from a topic or a public URL. The pipeline is the same — pick the input that fits how you think."
      />

      <Card>
        <CardHeader>
          <CardTitle>Choose an input</CardTitle>
          <CardDescription>Switch any time — your progress in each mode is independent.</CardDescription>
        </CardHeader>
        <CardContent>
          <SegmentedTabs value={mode} onChange={setMode} options={MODE_OPTIONS} />
        </CardContent>
      </Card>

      {mode === 'topic' ? (
        <TopicMode
          topic={topic}
          setTopic={setTopic}
          intent={intent}
          setIntent={setIntent}
          audience={audience}
          setAudience={setAudience}
          tone={tone}
          setTone={setTone}
          onGenerate={handleTopicGenerate}
          submitting={topicSubmitting}
          error={topicError}
          result={topicResult}
          onOpen={() => navigate(`/drafts/${topicResult.draft_id}`)}
          onReset={() => {
            setTopic('');
            setIntent('');
            setAudience('');
            setTone('');
            setTopicResult(null);
            setTopicError(null);
          }}
        />
      ) : (
        <SourceMode
          url={sourceUrl}
          setUrl={setSourceUrl}
          optionalTopic={sourceOptionalTopic}
          setOptionalTopic={setSourceOptionalTopic}
          stage={sourceStage}
          preview={sourcePreview}
          error={sourceError}
          result={sourceResult}
          onAnalyze={handleAnalyzeSource}
          onGenerate={handleSourceGenerate}
          onReset={resetSource}
          onOpen={() => navigate(`/drafts/${sourceResult.draft_id}`)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Topic mode
// ---------------------------------------------------------------------------

function TopicMode({
  topic,
  setTopic,
  intent,
  setIntent,
  audience,
  setAudience,
  tone,
  setTone,
  onGenerate,
  submitting,
  error,
  result,
  onOpen,
  onReset,
}) {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Topic</CardTitle>
          <CardDescription>What do you want to post about?</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Field id="topic" label="Topic" required>
            <Textarea
              id="topic"
              rows={4}
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Why async workflows matter for AI agents"
              disabled={submitting}
            />
          </Field>

          <div className="grid gap-3 sm:grid-cols-3">
            <Field id="intent" label="Intent">
              <Input
                id="intent"
                placeholder="Educate, announce…"
                value={intent}
                onChange={(e) => setIntent(e.target.value)}
                disabled={submitting}
              />
            </Field>
            <Field id="audience" label="Audience">
              <Input
                id="audience"
                placeholder="Engineers, founders…"
                value={audience}
                onChange={(e) => setAudience(e.target.value)}
                disabled={submitting}
              />
            </Field>
            <Field id="tone" label="Tone">
              <Input
                id="tone"
                placeholder="Professional, candid…"
                value={tone}
                onChange={(e) => setTone(e.target.value)}
                disabled={submitting}
              />
            </Field>
          </div>

          {error ? <ErrorBanner error={error} onRetry={onGenerate} /> : null}

          {submitting ? (
            <ProgressPanel
              steps={TOPIC_PROGRESS_STEPS}
              activeId="write"
              description="Creating your LinkedIn post…"
            />
          ) : null}

          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="brand"
              size="lg"
              onClick={onGenerate}
              disabled={submitting || !topic.trim()}
              loading={submitting}
              leftIcon={!submitting ? <Sparkles className="h-4 w-4" /> : null}
            >
              {submitting ? 'Generating…' : 'Generate LinkedIn Post'}
            </Button>
            {result || topic ? (
              <Button
                variant="ghost"
                size="md"
                onClick={onReset}
                disabled={submitting}
                leftIcon={<RotateCcw className="h-3.5 w-3.5" />}
              >
                Reset
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Preview</CardTitle>
          <CardDescription>
            {result
              ? 'Draft ready. Open the viewer to edit, schedule, or publish.'
              : submitting
              ? 'Generating…'
              : 'The generated draft will appear here.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {result ? (
            <ResultPreview result={result} onOpen={onOpen} />
          ) : submitting ? (
            <div className="space-y-3">
              <SkeletonPost />
            </div>
          ) : (
            <EmptyState
              icon={<Lightbulb className="h-5 w-5" />}
              title="Ready when you are"
              description="Type a topic on the left and click Generate. The whole pipeline usually takes 30–90 seconds."
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Source mode
// ---------------------------------------------------------------------------

function SourceMode({
  url,
  setUrl,
  optionalTopic,
  setOptionalTopic,
  stage,
  preview,
  error,
  result,
  onAnalyze,
  onGenerate,
  onReset,
  onOpen,
}) {
  const isAnalyzing = stage === 'analyzing';
  const isAnalyzed = stage === 'analyzed';
  const isGenerating = stage === 'generating';
  const isSuccess = stage === 'success';

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Source URL</CardTitle>
          <CardDescription>
            Public URLs only — GitHub repos, blog posts, documentation, product pages.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Field
            id="source-url"
            label="URL"
            required
            hint="https://github.com/owner/repo · https://example.com/article · https://docs.example.com/..."
          >
            <Input
              id="source-url"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://github.com/owner/repository"
              disabled={isAnalyzing || isAnalyzed || isGenerating || isSuccess}
              leftIcon={<Link2 className="h-3.5 w-3.5" />}
            />
          </Field>

          {isAnalyzed || isSuccess ? (
            <Field
              id="framing-hint"
              label="Optional framing hint"
              hint="A short angle the writer should focus on."
            >
              <Textarea
                id="framing-hint"
                rows={2}
                value={optionalTopic}
                onChange={(e) => setOptionalTopic(e.target.value)}
                placeholder="e.g. focus on the architecture"
                disabled={isGenerating || isSuccess}
              />
            </Field>
          ) : null}

          {error ? <ErrorBanner error={error} onRetry={isAnalyzed ? onGenerate : onAnalyze} /> : null}

          {isGenerating ? (
            <ProgressPanel
              steps={SOURCE_PROGRESS_STEPS}
              activeId="write"
              description="Creating your LinkedIn post from the source…"
            />
          ) : null}

          <div className="flex flex-wrap items-center gap-2">
            {!isAnalyzed && !isSuccess ? (
              <Button
                variant="brand"
                size="lg"
                onClick={onAnalyze}
                disabled={!url.trim() || isAnalyzing}
                loading={isAnalyzing}
                leftIcon={!isAnalyzing ? <Wand2 className="h-4 w-4" /> : null}
              >
                {isAnalyzing ? 'Analyzing…' : 'Analyze Source'}
              </Button>
            ) : null}
            {isAnalyzed ? (
              <Button
                variant="brand"
                size="lg"
                onClick={onGenerate}
                disabled={isGenerating}
                loading={isGenerating}
                leftIcon={!isGenerating ? <Sparkles className="h-4 w-4" /> : null}
              >
                {isGenerating ? 'Generating…' : 'Generate LinkedIn Post'}
              </Button>
            ) : null}
            {isAnalyzed || isSuccess ? (
              <Button
                variant="ghost"
                size="md"
                onClick={onReset}
                disabled={isGenerating}
                leftIcon={<RotateCcw className="h-3.5 w-3.5" />}
              >
                Use a different URL
              </Button>
            ) : null}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Source preview</CardTitle>
          <CardDescription>
            {stage === 'idle' && 'Paste a URL on the left and click Analyze.'}
            {isAnalyzing && 'Fetching the source safely…'}
            {isAnalyzed && 'Source found. Review and generate a draft.'}
            {isGenerating && 'Drafting the LinkedIn post — usually 30–90s.'}
            {isSuccess && 'Draft generated. Open the viewer to edit, schedule, or publish.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isAnalyzing ? (
            <SourceAnalyzingSkeleton />
          ) : isAnalyzed && preview ? (
            <SourcePreviewCard
              sourceType={preview.source_type}
              title={preview.source?.title}
              description={preview.source?.description}
              summary={preview.source?.summary}
              keyFacts={preview.source?.key_facts || []}
              url={preview.source?.url}
              finalUrl={preview.source?.final_url}
            />
          ) : isSuccess && result ? (
            <ResultPreview result={result} onOpen={onOpen} />
          ) : stage === 'idle' ? (
            <EmptyState
              icon={<Github className="h-5 w-5" />}
              title="No source analyzed yet"
              description="The source preview will appear here once you click Analyze."
            />
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Result preview — LinkedIn-style card on the right side
// ---------------------------------------------------------------------------

function ResultPreview({ result, onOpen }) {
  const post = result.final_post || {};
  const sourceUrl = result.source_url;
  return (
    <div className="space-y-4 animate-fadeIn">
      <LinkedInPreview
        authorName="You"
        authorHeadline="on LinkedIn"
        content={post.content}
        hashtags={post.hashtags || []}
        sourceAttribution={sourceUrl ? { label: 'Source', url: sourceUrl } : null}
      />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs text-text-muted">
          {result.iterations ? `${result.iterations} iteration${result.iterations === 1 ? '' : 's'}` : null}
          {result.review_feedback ? ` · ${result.review_feedback}` : null}
        </div>
        <Button variant="brand" size="md" onClick={onOpen} rightIcon={<ArrowRight className="h-4 w-4" />}>
          Open viewer
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Generation progress panel
// ---------------------------------------------------------------------------

function ProgressPanel({ steps, activeId, description }) {
  return (
    <div className="panel-inset flex flex-col gap-3 p-4">
      <div className="flex items-center gap-3">
        <Spinner size="md" />
        <div>
          <div className="text-sm font-medium text-white">{description}</div>
          <div className="text-xs text-text-muted">Backend usually takes 30–90 seconds.</div>
        </div>
      </div>
      <StepProgress
        steps={steps.map((step) => ({
          ...step,
          state: step.id === activeId ? 'active' : 'pending',
        }))}
      />
    </div>
  );
}

function SourceAnalyzingSkeleton() {
  return (
    <div className="space-y-3">
      <div className="panel-muted flex items-center gap-3 p-4">
        <Spinner />
        <div className="text-sm text-text-secondary">
          Fetching the source — typically 5–15 seconds.
        </div>
      </div>
      <div className="space-y-2">
        <div className="skeleton h-5 w-2/3" />
        <div className="skeleton h-4 w-full" />
        <div className="skeleton h-4 w-5/6" />
        <div className="skeleton h-4 w-3/4" />
      </div>
    </div>
  );
}

function SkeletonPost() {
  return (
    <div className="rounded-2xl border border-white/10 bg-[#0f1115] p-5">
      <div className="flex items-center gap-3">
        <div className="skeleton h-12 w-12 rounded-full" />
        <div className="flex-1 space-y-2">
          <div className="skeleton h-4 w-1/3" />
          <div className="skeleton h-3 w-1/4" />
        </div>
      </div>
      <div className="mt-4 space-y-2">
        <div className="skeleton h-4 w-full" />
        <div className="skeleton h-4 w-11/12" />
        <div className="skeleton h-4 w-2/3" />
      </div>
      <div className="mt-3 flex gap-2">
        <div className="skeleton h-5 w-12 rounded-full" />
        <div className="skeleton h-5 w-16 rounded-full" />
      </div>
    </div>
  );
}
