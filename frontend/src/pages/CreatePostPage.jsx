import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Sparkles,
  ArrowRight,
  Link2,
  FileText,
  Github,
  CheckCircle2,
  Wand2,
  RotateCcw,
  Lightbulb,
  AlertCircle,
  PencilLine,
  X,
} from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useToast } from '../context/ToastContext.jsx';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Textarea, Field } from '../components/ui/Input.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { PageHeader } from '../components/ui/PageHeader.jsx';
import { SegmentedTabs } from '../components/ui/SegmentedTabs.jsx';
import { GenerationProgress } from '../components/ui/GenerationProgress.jsx';
import { GenerationResultCard } from '../components/ui/GenerationResultCard.jsx';
import { SourcePreviewCard } from '../components/ui/SourcePreviewCard.jsx';
import { ErrorBanner, Spinner, EmptyState } from '../components/ui/Feedback.jsx';

const MODE_OPTIONS = [
  {
    value: 'topic',
    label: 'From Topic',
    description:
      'Describe the post you want. The writer drafts a LinkedIn-native post and the reviewer polishes it.',
    icon: <FileText className="h-5 w-5" />,
  },
  {
    value: 'source',
    label: 'From URL',
    description:
      'Paste a GitHub repo, blog, article, documentation or product page. The writer reacts to the source, never invents facts.',
    icon: <Link2 className="h-5 w-5" />,
  },
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
  const [style, setStyle] = useState('');
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

  // Reset error state when switching modes so a stale error does
  // not bleed across.
  useEffect(() => {
    setTopicError(null);
    setSourceError(null);
  }, [mode]);

  // ---- Topic mode ----
  async function handleTopicGenerate({ regenerate = false } = {}) {
    if (!topic.trim()) {
      toast.error('Please enter a topic.');
      return;
    }
    setTopicSubmitting(true);
    setTopicError(null);
    try {
      const response = await api.generateContent({
        topic: topic.trim(),
        intent: intent || undefined,
        audience: audience || undefined,
        tone: tone || undefined,
      });
      setTopicResult(response);
      if (regenerate) {
        toast.success('A new draft is ready.');
      } else {
        toast.success('Draft generated.');
      }
    } catch (err) {
      setTopicError(err);
      toast.error('Generation failed', err?.message);
    } finally {
      setTopicSubmitting(false);
    }
  }

  function handleTopicReset() {
    setTopic('');
    setIntent('');
    setAudience('');
    setTone('');
    setStyle('');
    setTopicResult(null);
    setTopicError(null);
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
  async function handleSourceGenerate({ regenerate = false } = {}) {
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
      toast.success(regenerate ? 'A new draft is ready.' : 'Draft generated.');
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
        actions={
          topicResult || sourceResult ? (
            <Button
              variant="ghost"
              size="md"
              onClick={() => {
                if (mode === 'topic') handleTopicReset();
                else resetSource();
              }}
              leftIcon={<RotateCcw className="h-3.5 w-3.5" />}
            >
              Start over
            </Button>
          ) : null
        }
      />

      <Card>
        <CardHeader>
          <CardTitle>Choose an input</CardTitle>
          <CardDescription>
            Pick the input that fits how you think. Each mode uses the same
            writer + reviewer pipeline.
          </CardDescription>
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
          style={style}
          setStyle={setStyle}
          onGenerate={handleTopicGenerate}
          submitting={topicSubmitting}
          error={topicError}
          result={topicResult}
          onOpen={() => navigate(`/drafts/${topicResult.draft_id}`)}
          onRegenerate={() => handleTopicGenerate({ regenerate: true })}
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
          onRegenerate={() =>
            handleSourceGenerate({ regenerate: true })
          }
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Topic mode
// ---------------------------------------------------------------------------

const TOPIC_PLACEHOLDERS = [
  "What I learned building a RAG application with LangChain",
  "Why async workflows matter for AI agents",
  "Three lessons from shipping a side project in 30 days",
];

function TopicMode({
  topic,
  setTopic,
  intent,
  setIntent,
  audience,
  setAudience,
  tone,
  setTone,
  style,
  setStyle,
  onGenerate,
  submitting,
  error,
  result,
  onOpen,
  onRegenerate,
}) {
  const [placeholderIdx, setPlaceholderIdx] = useState(0);

  // Cycle placeholder every 6s while idle so the example feels
  // alive. Pure visual hint, not a backend call.
  useEffect(() => {
    if (submitting || result) return undefined;
    const t = window.setInterval(() => {
      setPlaceholderIdx((i) => (i + 1) % TOPIC_PLACEHOLDERS.length);
    }, 6000);
    return () => window.clearInterval(t);
  }, [submitting, result]);

  const canSubmit = topic.trim().length > 0 && !submitting;

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Topic</CardTitle>
            <CardDescription>What do you want to post about?</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field id="topic" label="Topic or idea" required>
              <Textarea
                id="topic"
                rows={4}
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder={TOPIC_PLACEHOLDERS[placeholderIdx]}
                disabled={submitting}
              />
            </Field>

            <div className="grid gap-3 sm:grid-cols-2">
              <Field id="intent" label="Intent" hint="The angle or purpose.">
                <Input
                  id="intent"
                  placeholder="Educate, announce, share a lesson…"
                  value={intent}
                  onChange={(e) => setIntent(e.target.value)}
                  disabled={submitting}
                />
              </Field>
              <Field id="audience" label="Audience" hint="Who is this for?">
                <Input
                  id="audience"
                  placeholder="Engineers, founders, students…"
                  value={audience}
                  onChange={(e) => setAudience(e.target.value)}
                  disabled={submitting}
                />
              </Field>
              <Field id="tone" label="Tone" hint="How should it read?">
                <Input
                  id="tone"
                  placeholder="Professional, candid, conversational…"
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                  disabled={submitting}
                />
              </Field>
              <Field id="style" label="Style" hint="Optional writing style.">
                <Input
                  id="style"
                  placeholder="professional, technical, narrative…"
                  value={style}
                  onChange={(e) => setStyle(e.target.value)}
                  disabled={submitting}
                />
              </Field>
            </div>
          </CardContent>
        </Card>

        <GenerationActions
          submitting={submitting}
          result={result}
          canSubmit={canSubmit}
          onGenerate={() => onGenerate()}
          onRegenerate={onRegenerate}
          error={error}
        />
      </div>

      <div>
        <Card>
          <CardHeader>
            <CardTitle>Preview</CardTitle>
            <CardDescription>
              {result
                ? 'Draft ready. Open the viewer to edit, schedule, or publish.'
                : submitting
                ? 'The pipeline is running. This usually takes 30–90 seconds.'
                : 'The generated post will appear here.'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {submitting ? (
              <GenerationProgress mode="topic" />
            ) : result ? (
              <GenerationResultCard
                result={result}
                onOpen={onOpen}
                onRegenerate={onRegenerate}
                regenerating={false}
              />
            ) : (
              <EmptyState
                icon={<Lightbulb className="h-5 w-5" />}
                title="Ready when you are"
                description="Type a topic on the left and click Generate. The writer will draft a real LinkedIn post — not a summary."
              />
            )}
          </CardContent>
        </Card>
      </div>
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
  onRegenerate,
}) {
  const isAnalyzing = stage === 'analyzing';
  const isAnalyzed = stage === 'analyzed';
  const isGenerating = stage === 'generating';
  const isSuccess = stage === 'success';
  const isFailure = stage === 'failure';
  const isAnalyzedOrSuccess = isAnalyzed || isSuccess;

  const canSubmit = url.trim().length > 0 && !isAnalyzing;

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Source URL</CardTitle>
            <CardDescription>
              Public URLs only — GitHub repositories, blog posts,
              documentation, product pages.
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

            {isAnalyzedOrSuccess ? (
              <Field
                id="framing-hint"
                label="Framing hint (optional)"
                hint="A short angle the writer should focus on. Forwarded to the backend."
              >
                <Textarea
                  id="framing-hint"
                  rows={3}
                  value={optionalTopic}
                  onChange={(e) => setOptionalTopic(e.target.value)}
                  placeholder="e.g. focus on the architecture; share what I learned"
                  disabled={isGenerating}
                />
              </Field>
            ) : null}

            {error ? <ErrorBanner error={error} onRetry={isAnalyzed ? onGenerate : onAnalyze} /> : null}

            {isAnalyzing ? (
              <SourceAnalyzingPanel />
            ) : null}

            {isGenerating ? (
              <GenerationProgress mode="source" />
            ) : null}
          </CardContent>
        </Card>

        <SourceActionRow
          stage={stage}
          canSubmit={canSubmit}
          isAnalyzed={isAnalyzed}
          isGenerating={isGenerating}
          isSuccess={isSuccess}
          onAnalyze={onAnalyze}
          onGenerate={() => onGenerate()}
          onRegenerate={onRegenerate}
          onReset={onReset}
        />
      </div>

      <div>
        <Card>
          <CardHeader>
            <CardTitle>Source preview</CardTitle>
            <CardDescription>
              {stage === 'idle' &&
                'Paste a URL on the left and click Analyze. The system will fetch the source safely and identify its type.'}
              {isAnalyzing && 'Fetching the source safely via the SSRF-guarded fetcher…'}
              {isAnalyzed && 'Source found. Review the preview, then generate a draft.'}
              {isGenerating && 'Drafting the LinkedIn post — usually 30–90 seconds.'}
              {isSuccess && 'Draft generated. Open the viewer to edit, schedule, or publish.'}
              {isFailure && "We couldn't analyze this source. Try another public URL."}
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
              <GenerationResultCard
                result={result}
                onOpen={onOpen}
                onRegenerate={onRegenerate}
                regenerating={false}
              />
            ) : stage === 'idle' ? (
              <EmptyState
                icon={<Github className="h-5 w-5" />}
                title="No source analyzed yet"
                description="Paste a GitHub repository, blog post, article, documentation or product URL on the left and click Analyze Source."
              />
            ) : isFailure ? (
              <SourceFailureHint
                error={error}
                onRetry={onAnalyze}
                onReset={onReset}
              />
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared action row
// ---------------------------------------------------------------------------

function GenerationActions({ submitting, result, canSubmit, onGenerate, onRegenerate, error }) {
  return (
    <Card>
      <CardContent className="space-y-3">
        {error ? <ErrorBanner error={error} onRetry={onGenerate} /> : null}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="brand"
            size="lg"
            onClick={onGenerate}
            disabled={!canSubmit}
            loading={submitting}
            leftIcon={!submitting ? <Sparkles className="h-4 w-4" /> : null}
          >
            {submitting ? 'Generating…' : 'Generate LinkedIn Post'}
          </Button>
          {result ? (
            <Button
              variant="secondary"
              size="md"
              onClick={onRegenerate}
              leftIcon={<RotateCcw className="h-3.5 w-3.5" />}
            >
              Generate Again
            </Button>
          ) : null}
        </div>
        {result ? (
          <p className="text-xs text-text-muted">
            <CheckCircle2 className="-mt-0.5 mr-1 inline h-3 w-3" /> Your previous draft is preserved — generating again creates a new draft in your library.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function SourceActionRow({
  stage,
  canSubmit,
  isAnalyzed,
  isGenerating,
  isSuccess,
  onAnalyze,
  onGenerate,
  onRegenerate,
  onReset,
}) {
  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          {!isAnalyzed && !isSuccess ? (
            <Button
              variant="brand"
              size="lg"
              onClick={onAnalyze}
              disabled={!canSubmit}
              loading={isGenerating || stage === 'analyzing'}
              leftIcon={!isGenerating && stage !== 'analyzing' ? <Wand2 className="h-4 w-4" /> : null}
            >
              {stage === 'analyzing' ? 'Analyzing…' : 'Analyze Source'}
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
          {isSuccess ? (
            <Button
              variant="secondary"
              size="md"
              onClick={onRegenerate}
              disabled={isGenerating}
              leftIcon={<RotateCcw className="h-3.5 w-3.5" />}
            >
              Generate Again
            </Button>
          ) : null}
          {isAnalyzed || isSuccess ? (
            <Button
              variant="ghost"
              size="md"
              onClick={onReset}
              disabled={isGenerating}
              leftIcon={<X className="h-3.5 w-3.5" />}
            >
              Use a different URL
            </Button>
          ) : null}
        </div>
        {(isAnalyzed || isSuccess) && !isGenerating ? (
          <p className="text-xs text-text-muted">
            <CheckCircle2 className="-mt-0.5 mr-1 inline h-3 w-3 text-emerald-300" />{' '}
            The previous source preview is preserved — generating again creates a new draft in your library.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Source failure / analyzing surfaces
// ---------------------------------------------------------------------------

function SourceAnalyzingPanel() {
  return (
    <div className="panel-inset flex items-center gap-3 p-3">
      <Spinner size="md" />
      <div>
        <div className="text-sm font-medium text-white">
          Fetching the source…
        </div>
        <div className="text-xs text-text-muted">
          Typically 5–15 seconds. We use the SSRF-safe fetcher.
        </div>
      </div>
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

function SourceFailureHint({ error, onRetry, onReset }) {
  return (
    <div className="space-y-3">
      <div className="rounded-2xl border border-rose-500/30 bg-rose-500/[0.06] p-4">
        <div className="flex items-center gap-2 text-rose-200">
          <AlertCircle className="h-4 w-4" />
          <span className="text-sm font-semibold">Couldn't analyze this source</span>
        </div>
        <p className="mt-1 text-sm text-rose-200/80">
          {error?.message ||
            'Try another public GitHub repository, article, documentation page, or product URL.'}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={onRetry}>
            Try again
          </Button>
          <Button variant="ghost" size="sm" onClick={onReset}>
            Use a different URL
          </Button>
        </div>
      </div>
    </div>
  );
}
