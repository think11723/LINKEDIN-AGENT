import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Sparkles,
  ArrowRight,
  Link2,
  FileText,
  Github,
  CheckCircle2,
  Wand2,
  RotateCcw,
  AlertCircle,
  Lightbulb,
  Check,
  ExternalLink,
  FileText as FileIcon,
} from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Textarea, Field } from '../components/ui/Input.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { Spinner, ErrorBanner, EmptyState, Skeleton } from '../components/ui/Feedback.jsx';
import { MotionPage } from '../components/ui/MotionPage.jsx';
import { SegmentedTabs } from '../components/ui/SegmentedTabs.jsx';
import { GenerationProgress } from '../components/ui/GenerationProgress.jsx';
import { GenerationResultCard } from '../components/ui/GenerationResultCard.jsx';
import { SourcePreviewCard } from '../components/ui/SourcePreviewCard.jsx';
import { LinkedInPreview } from '../components/ui/LinkedInPreview.jsx';

const MODE_OPTIONS = [
  {
    value: 'topic',
    label: 'From Topic',
    description:
      'Describe the post you want. The AI writes a LinkedIn-native draft and the reviewer polishes it.',
    icon: <FileText className="h-5 w-5" />,
  },
  {
    value: 'source',
    label: 'From URL',
    description:
      'Paste a GitHub repo, blog, article, or docs page. The AI reacts to the source — never invents facts.',
    icon: <Link2 className="h-5 w-5" />,
  },
];

export default function CreatePostPage() {
  const api = useApi();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [searchParams] = useSearchParams();

  const [mode, setMode] = useState('topic');

  // Topic mode
  const [topic, setTopic] = useState(() => searchParams.get('topic') || '');
  const [intent, setIntent] = useState('');
  const [audience, setAudience] = useState('');
  const [tone, setTone] = useState('');
  const [style, setStyle] = useState('');
  const [topicSubmitting, setTopicSubmitting] = useState(false);
  const [topicError, setTopicError] = useState(null);
  const [topicResult, setTopicResult] = useState(null);

  // Source mode
  const [sourceUrl, setSourceUrl] = useState('');
  const [sourceOptionalTopic, setSourceOptionalTopic] = useState('');
  const [sourceStage, setSourceStage] = useState('idle');
  const [sourceError, setSourceError] = useState(null);
  const [sourcePreview, setSourcePreview] = useState(null);
  const [sourceResult, setSourceResult] = useState(null);

  useEffect(() => {
    setTopicError(null);
    setSourceError(null);
  }, [mode]);

  async function handleTopicGenerate({ regenerate = false } = {}) {
    if (!topic.trim()) {
      toast.error('Please enter a topic.');
      return;
    }
    setTopicSubmitting(true);
    setTopicError(null);
    if (regenerate) setTopicResult(null);
    try {
      const response = await api.generateContent({
        topic: topic.trim(),
        intent: intent || undefined,
        audience: audience || undefined,
        tone: tone || undefined,
        style: style || undefined,
      });
      setTopicResult(response);
      if (regenerate) toast.success('A new draft is ready.');
      else toast.success('Draft generated.');
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

  async function handleSourceGenerate({ regenerate = false } = {}) {
    if (!sourcePreview) {
      toast.error('Analyze a source first.');
      return;
    }
    setSourceStage('generating');
    setSourceError(null);
    if (regenerate) setSourceResult(null);
    try {
      const response = await api.generateContent({
        source_url: sourcePreview.source?.url || sourceUrl.trim(),
        topic: sourceOptionalTopic.trim() || undefined,
      });
      setSourceResult(response);
      setSourceStage('success');
      if (regenerate) toast.success('A new draft is ready.');
      else toast.success('Draft generated.');
    } catch (err) {
      setSourceError(err);
      setSourceStage('failure');
      toast.error('Generation failed', err?.message);
    } finally {
      setSourceStage(false);
    }
  }

  function resetSource() {
    setSourceStage('idle');
    setSourceError(null);
    setSourcePreview(null);
    setSourceResult(null);
  }

  return (
    <MotionPage className="space-y-6 p-4 md:p-6 lg:p-8">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-text-secondary">
            <Sparkles className="h-3 w-3 text-brand-300" />
            AI Studio
          </div>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
            <span className="gradient-text">Create</span> a new LinkedIn post
          </h1>
          <p className="mt-1 max-w-xl text-sm text-text-secondary">
            Generate a real LinkedIn-native draft from a topic or a public URL.
            The same writer + reviewer pipeline powers both modes.
          </p>
        </div>
        {(topicResult || sourceResult) ? (
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
        ) : null}
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Choose an input</CardTitle>
          <CardDescription>
            Pick the input that fits how you think. Each mode uses the
            same writer + reviewer pipeline.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SegmentedTabs
            value={mode}
            onChange={setMode}
            options={MODE_OPTIONS}
          />
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
          onRegenerate={() => handleSourceGenerate({ regenerate: true })}
        />
      )}
    </MotionPage>
  );
}

const TOPIC_PLACEHOLDERS = [
  'What I learned building a RAG application with LangChain',
  'Why async workflows matter for AI agents',
  'Three lessons from shipping a side project in 30 days',
  'How we cut our LLM inference costs by 60%',
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
  useEffect(() => {
    if (submitting || result || topic.trim()) return undefined;
    const t = window.setInterval(() => {
      setPlaceholderIdx((i) => (i + 1) % TOPIC_PLACEHOLDERS.length);
    }, 5000);
    return () => window.clearInterval(t);
  }, [submitting, result, topic]);

  const canSubmit = topic.trim().length > 0 && !submitting;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1.05fr]">
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
              <Field id="intent" label="Intent" optional>
                <Input
                  id="intent"
                  placeholder="Educate, announce, share a lesson…"
                  value={intent}
                  onChange={(e) => setIntent(e.target.value)}
                  disabled={submitting}
                />
              </Field>
              <Field id="audience" label="Audience" optional>
                <Input
                  id="audience"
                  placeholder="Engineers, founders, students…"
                  value={audience}
                  onChange={(e) => setAudience(e.target.value)}
                  disabled={submitting}
                />
              </Field>
              <Field id="tone" label="Tone" optional>
                <Input
                  id="tone"
                  placeholder="Professional, candid, conversational…"
                  value={tone}
                  onChange={(e) => setTone(e.target.value)}
                  disabled={submitting}
                />
              </Field>
              <Field id="style" label="Style" optional>
                <Input
                  id="style"
                  placeholder="technical, narrative…"
                  value={style}
                  onChange={(e) => setStyle(e.target.value)}
                  disabled={submitting}
                />
              </Field>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="space-y-3">
            {error ? <ErrorBanner error={error} onRetry={() => onGenerate()} /> : null}
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="brand"
                size="lg"
                onClick={() => onGenerate()}
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
                Your previous draft is preserved — generating again creates
                a new draft in your library.
              </p>
            ) : null}
          </CardContent>
        </Card>

        {submitting ? (
          <Card>
            <CardContent>
              <GenerationProgress mode="topic" />
            </CardContent>
          </Card>
        ) : null}
      </div>

      <div>
        <Card>
          <CardHeader>
            <CardTitle>LinkedIn preview</CardTitle>
            <CardDescription>
              {result
                ? 'Draft ready. Open the viewer to edit, schedule, or publish.'
                : submitting
                ? 'The pipeline is running. This usually takes 30–90 seconds.'
                : 'The generated post will appear here.'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <AnimatePresence mode="wait">
              {result ? (
                <motion.div
                  key="result"
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                >
                  <LinkedInPreview
                    authorName="You"
                    authorHeadline="on LinkedIn"
                    content={result.final_post?.content}
                    hashtags={result.final_post?.hashtags || []}
                  />
                  <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
                    <div className="text-xs text-text-muted">
                      {result.iterations
                        ? `${result.iterations} iteration${result.iterations === 1 ? '' : 's'}`
                        : null}
                      {result.review_feedback ? ` · ${result.review_feedback}` : null}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={onRegenerate}
                        leftIcon={<RotateCcw className="h-3.5 w-3.5" />}
                      >
                        Generate Again
                      </Button>
                      <Button
                        variant="brand"
                        size="sm"
                        onClick={onOpen}
                        rightIcon={<ArrowRight className="h-3.5 w-3.5" />}
                      >
                        Open Draft
                      </Button>
                    </div>
                  </div>
                </motion.div>
              ) : submitting ? (
                <div className="space-y-3">
                  <Skeleton className="h-12 w-3/4" />
                  <Skeleton className="h-32 w-full" />
                  <Skeleton className="h-8 w-1/2" />
                </div>
              ) : (
                <EmptyState
                  icon={<Lightbulb className="h-5 w-5" />}
                  title="Ready when you are"
                  description="Type a topic on the left and click Generate. The AI will draft a real LinkedIn post — not a summary."
                />
              )}
            </AnimatePresence>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

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
  const isAnalyzedOrSuccess = isAnalyzed || isSuccess;

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1.05fr]">
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
                label="Framing hint"
                hint="A short angle the writer should focus on."
                optional
              >
                <Textarea
                  id="framing-hint"
                  rows={3}
                  value={optionalTopic}
                  onChange={(e) => setOptionalTopic(e.target.value)}
                  placeholder="e.g. focus on the architecture"
                  disabled={isGenerating}
                />
              </Field>
            ) : null}

            {error ? <ErrorBanner error={error} onRetry={isAnalyzed ? () => onGenerate() : onAnalyze} /> : null}

            {isGenerating ? (
              <GenerationProgress mode="source" />
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="space-y-3">
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
                  onClick={() => onGenerate()}
                  disabled={isGenerating}
                  loading={isGenerating}
                  leftIcon={!isGenerating ? <Sparkles className="h-4 w-4" /> : null}
                >
                  {isGenerating ? 'Generating…' : 'Generate LinkedIn Post'}
                </Button>
              ) : null}
              {isAnalyzed || isSuccess ? (
                <Button
                  variant="secondary"
                  size="md"
                  onClick={isSuccess ? () => onRegenerate() : onReset}
                  disabled={isGenerating}
                  leftIcon={isSuccess ? <RotateCcw className="h-3.5 w-3.5" /> : <Link2 className="h-3.5 w-3.5" />}
                >
                  {isSuccess ? 'Generate Again' : 'Use a different URL'}
                </Button>
              ) : null}
            </div>
            {isAnalyzedOrSuccess && !isGenerating ? (
              <p className="text-xs text-text-muted">
                The previous source preview is preserved — generating
                again creates a new draft in your library.
              </p>
            ) : null}
          </CardContent>
        </Card>
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
            </CardDescription>
          </CardHeader>
          <CardContent>
            <AnimatePresence mode="wait">
              {isAnalyzing ? (
                <motion.div key="analyzing" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  <div className="space-y-3">
                    <div className="glass-inset flex items-center gap-3 p-3">
                      <Spinner size="md" />
                      <div className="text-sm text-text-secondary">
                        Fetching the source — typically 5–15 seconds.
                      </div>
                    </div>
                    <div className="space-y-2">
                      <Skeleton className="h-5 w-2/3" />
                      <Skeleton className="h-4 w-full" />
                      <Skeleton className="h-4 w-5/6" />
                      <Skeleton className="h-4 w-3/4" />
                    </div>
                  </div>
                </motion.div>
              ) : isAnalyzed && preview ? (
                <motion.div
                  key="analyzed"
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.3 }}
                >
                  <SourcePreviewCard
                    sourceType={preview.source_type}
                    title={preview.source?.title}
                    description={preview.source?.description}
                    summary={preview.source?.summary}
                    keyFacts={preview.source?.key_facts || []}
                    url={preview.source?.url}
                    finalUrl={preview.source?.final_url}
                  />
                </motion.div>
              ) : isSuccess && result ? (
                <motion.div
                  key="success"
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                >
                  <LinkedInPreview
                    authorName="You"
                    authorHeadline="on LinkedIn"
                    content={result.final_post?.content}
                    hashtags={result.final_post?.hashtags || []}
                    sourceAttribution={result.source_url ? {
                      label: preview?.source_label || 'Source',
                      title: preview?.source?.title,
                      url: result.source_url,
                    } : null}
                  />
                  <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
                    <div className="text-xs text-text-muted">
                      {result.iterations
                        ? `${result.iterations} iteration${result.iterations === 1 ? '' : 's'}`
                        : null}
                      {result.review_feedback ? ` · ${result.review_feedback}` : null}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={onRegenerate}
                        leftIcon={<RotateCcw className="h-3.5 w-3.5" />}
                      >
                        Generate Again
                      </Button>
                      <Button
                        variant="brand"
                        size="sm"
                        onClick={onOpen}
                        rightIcon={<ArrowRight className="h-3.5 w-3.5" />}
                      >
                        Open Draft
                      </Button>
                    </div>
                  </div>
                </motion.div>
              ) : stage === 'idle' ? (
                <EmptyState
                  icon={<Github className="h-5 w-5" />}
                  title="No source analyzed yet"
                  description="Paste a GitHub repository, blog post, article, documentation or product URL on the left and click Analyze Source."
                />
              ) : null}
            </AnimatePresence>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
