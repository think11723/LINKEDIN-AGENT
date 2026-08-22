import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, ArrowRight, Link2, FileText, Github, Globe, BookOpen, Rocket, CheckCircle2 } from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Textarea } from '../components/ui/Input.jsx';
import { Spinner, ErrorBanner, EmptyState } from '../components/ui/Feedback.jsx';
import { Badge } from '../components/ui/Badge.jsx';

/**
 * Phase 3 — Create Post page.
 *
 * The page now has two mutually-exclusive modes:
 *
 *   * Topic mode (legacy) — user types a topic, server runs the
 *     existing writer+reviewer pipeline. No network fetch, no source
 *     metadata persisted.
 *
 *   * Source mode — user pastes a public URL. The server fetches the
 *     URL through the SSRF guard + adapter layer, classifies the
 *     source, and shows a preview card. The user confirms and we run
 *     the writer+reviewer pipeline with the source context attached.
 *     Source metadata (URL, title, description, source_type) is
 *     persisted on the resulting draft.
 *
 * State machine (honest four-state model retained):
 *   idle → analyzing → analyzed → generating → success | failure
 */
export default function CreatePostPage() {
  const api = useApi();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [mode, setMode] = useState('topic'); // 'topic' | 'source'

  // Topic mode state.
  const [topic, setTopic] = useState('');
  const [topicSubmitting, setTopicSubmitting] = useState(false);
  const [topicError, setTopicError] = useState(null);
  const [topicResult, setTopicResult] = useState(null);

  // Source mode state.
  const [sourceUrl, setSourceUrl] = useState('');
  const [sourceStage, setSourceStage] = useState('idle'); // idle | analyzing | analyzed | generating | failure
  const [sourceError, setSourceError] = useState(null);
  const [sourcePreview, setSourcePreview] = useState(null);
  const [sourceResult, setSourceResult] = useState(null);
  const [optionalTopic, setOptionalTopic] = useState('');

  // ------------------------------------------------------------------
  // Topic mode
  // ------------------------------------------------------------------
  async function handleTopicGenerate() {
    if (!topic.trim()) {
      toast.error('Please enter a topic.');
      return;
    }
    setTopicSubmitting(true);
    setTopicError(null);
    try {
      const response = await api.generateContent({ topic: topic.trim() });
      setTopicResult(response);
      toast.success('Content generated successfully.');
    } catch (err) {
      setTopicError(err);
      toast.error('Generation failed', err?.message);
    } finally {
      setTopicSubmitting(false);
    }
  }

  // ------------------------------------------------------------------
  // Source mode — analyze
  // ------------------------------------------------------------------
  async function handleAnalyzeSource() {
    if (!sourceUrl.trim()) {
      toast.error('Please enter a URL.');
      return;
    }
    setSourceStage('analyzing');
    setSourceError(null);
    setSourcePreview(null);
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

  // ------------------------------------------------------------------
  // Source mode — generate draft from the analyzed source
  // ------------------------------------------------------------------
  async function handleSourceGenerate() {
    if (!sourcePreview) {
      toast.error('Analyze a source first.');
      return;
    }
    setSourceStage('generating');
    setSourceError(null);
    try {
      const response = await api.generateContent({
        source_url: sourcePreview.source?.url || sourceUrl.trim(),
        topic: optionalTopic.trim() || undefined,
      });
      setSourceResult(response);
      setSourceStage('success');
      toast.success('Content generated successfully.');
    } catch (err) {
      setSourceError(err);
      setSourceStage('failure');
      toast.error('Generation failed', err?.message);
    }
  }

  function resetSourceMode() {
    setSourceStage('idle');
    setSourceError(null);
    setSourcePreview(null);
    setSourceResult(null);
  }

  function switchMode(nextMode) {
    if (nextMode === mode) return;
    setMode(nextMode);
    setSourceError(null);
    setTopicError(null);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Create Post</h1>
        <p className="text-zinc-400">
          Generate a LinkedIn draft from a topic or from a public URL.
        </p>
      </div>

      {/* Mode selector */}
      <div className="inline-flex rounded-xl border border-white/10 bg-white/[0.03] p-1">
        <ModeTab
          active={mode === 'topic'}
          onClick={() => switchMode('topic')}
          icon={<FileText className="h-4 w-4" />}
          label="From Topic"
        />
        <ModeTab
          active={mode === 'source'}
          onClick={() => switchMode('source')}
          icon={<Link2 className="h-4 w-4" />}
          label="From URL"
        />
      </div>

      {mode === 'topic' ? (
        <TopicMode
          topic={topic}
          setTopic={setTopic}
          onGenerate={handleTopicGenerate}
          submitting={topicSubmitting}
          error={topicError}
          result={topicResult}
          onOpen={() => navigate(`/drafts/${topicResult.draft_id}`)}
        />
      ) : (
        <SourceMode
          url={sourceUrl}
          setUrl={setSourceUrl}
          optionalTopic={optionalTopic}
          setOptionalTopic={setOptionalTopic}
          stage={sourceStage}
          preview={sourcePreview}
          error={sourceError}
          result={sourceResult}
          onAnalyze={handleAnalyzeSource}
          onGenerate={handleSourceGenerate}
          onReset={resetSourceMode}
          onOpen={() => navigate(`/drafts/${sourceResult.draft_id}`)}
        />
      )}
    </div>
  );
}

function ModeTab({ active, onClick, icon, label }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        'inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition ' +
        (active
          ? 'bg-white/10 text-white'
          : 'text-zinc-400 hover:text-zinc-200')
      }
      aria-pressed={active}
    >
      {icon}
      {label}
    </button>
  );
}

function SourceTypeIcon({ sourceType }) {
  switch (sourceType) {
    case 'github_repository':
    case 'github_readme':
      return <Github className="h-4 w-4" />;
    case 'documentation':
      return <BookOpen className="h-4 w-4" />;
    case 'product_page':
      return <Rocket className="h-4 w-4" />;
    case 'blog_article':
    case 'generic_webpage':
    default:
      return <Globe className="h-4 w-4" />;
  }
}

// ---------------------------------------------------------------------------
// Topic mode (legacy / unchanged behavior)
// ---------------------------------------------------------------------------

function TopicMode({ topic, setTopic, onGenerate, submitting, error, result, onOpen }) {
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
      <Card>
        <CardHeader>
          <CardTitle>Topic</CardTitle>
          <CardDescription>Describe what you want to publish.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="mb-2 block text-sm">Topic</label>
            <Input
              placeholder="AI workflows for LinkedIn creators"
              value={topic}
              onChange={(event) => setTopic(event.target.value)}
              disabled={submitting}
            />
          </div>
          <Button
            onClick={onGenerate}
            disabled={submitting}
            loading={submitting}
            className="w-full"
          >
            <Sparkles className="h-4 w-4" />
            {submitting ? 'Generating…' : 'Generate draft'}
          </Button>
          <p className="text-xs text-zinc-500">
            The backend runs a single synchronous call today. Future work can
            stream per-node progress (SSE / WebSocket) when the workflow
            becomes long-running.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Output</CardTitle>
          <CardDescription>
            {error ? 'Generation failed. See the error below.' : result ? 'Draft generated. Open the viewer to edit, schedule, or publish.' : 'Submit a topic to generate a draft.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <ErrorBanner error={error} />
          {submitting ? (
            <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-zinc-300">
              <Spinner /> Generating draft — typically 30–90s.
            </div>
          ) : null}
          {result ? (
            <ResultPanel result={result} onOpen={onOpen} />
          ) : !error ? (
            <EmptyState
              title="Nothing to show yet"
              description="The generated draft will appear here."
            />
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Source mode (Phase 3)
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
  const isFailure = stage === 'failure';

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
      <Card>
        <CardHeader>
          <CardTitle>Source URL</CardTitle>
          <CardDescription>
            Provide a public URL — a GitHub repository, blog post, or documentation page.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="mb-2 block text-sm">URL</label>
            <Input
              type="url"
              placeholder="https://github.com/owner/repository"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              disabled={isAnalyzing || isAnalyzed || isGenerating || isSuccess}
            />
          </div>
          {isAnalyzed || isSuccess ? (
            <div>
              <label className="mb-2 block text-sm">
                Optional framing hint for the writer
              </label>
              <Textarea
                rows={2}
                placeholder="e.g. focus on the architecture"
                value={optionalTopic}
                onChange={(event) => setOptionalTopic(event.target.value)}
                disabled={isGenerating || isSuccess}
              />
            </div>
          ) : null}

          {!isSuccess ? (
            <div className="flex flex-wrap gap-2">
              {!isAnalyzed ? (
                <Button
                  onClick={onAnalyze}
                  disabled={!url.trim() || isAnalyzing}
                  loading={isAnalyzing}
                  className="flex-1"
                >
                  {isAnalyzing ? 'Analyzing…' : 'Analyze Source'}
                </Button>
              ) : (
                <>
                  <Button
                    onClick={onGenerate}
                    disabled={isGenerating}
                    loading={isGenerating}
                    className="flex-1"
                  >
                    <Sparkles className="h-4 w-4" />
                    {isGenerating ? 'Generating…' : 'Generate LinkedIn Post'}
                  </Button>
                  <Button
                    onClick={onReset}
                    variant="outline"
                    disabled={isGenerating}
                  >
                    Use a different URL
                  </Button>
                </>
              )}
            </div>
          ) : null}

          <p className="text-xs text-zinc-500">
            Only public http(s) URLs are accepted. The source is fetched through
            an SSRF-safe network guard and never persisted beyond a small
            metadata blob.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Source Preview</CardTitle>
          <CardDescription>
            {stage === 'idle' && 'Paste a URL above and click "Analyze Source".'}
            {isAnalyzing && 'Fetching the source safely…'}
            {isAnalyzed && 'Source found. Review and generate a draft.'}
            {isGenerating && 'Drafting the LinkedIn post — typically 30–90s.'}
            {isSuccess && 'Draft generated. Open the viewer to edit, schedule, or publish.'}
            {isFailure && 'Could not read this source. See the error below.'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <ErrorBanner error={error} onRetry={isAnalyzed ? onGenerate : onAnalyze} />
          {isAnalyzing ? (
            <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-zinc-300">
              <Spinner /> Reading the source — typically 5–15s.
            </div>
          ) : null}
          {isAnalyzed && preview ? (
            <SourcePreviewCard preview={preview} />
          ) : null}
          {isSuccess && result ? (
            <ResultPanel result={result} onOpen={onOpen} />
          ) : null}
          {stage === 'idle' ? (
            <EmptyState
              title="No source analyzed yet"
              description="The source preview will appear here once you click Analyze."
            />
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

function SourcePreviewCard({ preview }) {
  const source = preview?.source || {};
  const label = preview?.source_label || source.type || 'Source';
  const title = source.title || 'Untitled source';
  const summary = source.summary || source.description || '';
  const facts = Array.isArray(source.key_facts) ? source.key_facts : [];
  const sourceUrl = source.final_url || source.url || '';
  return (
    <div className="space-y-3 rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-4">
      <div className="flex items-center gap-2 text-emerald-300">
        <CheckCircle2 className="h-4 w-4" />
        <span className="text-sm font-medium">Source found</span>
      </div>
      <div className="flex items-center gap-2 text-zinc-200">
        <SourceTypeIcon sourceType={source.type} />
        <span className="text-base font-semibold">{label}</span>
      </div>
      <div>
        <div className="text-lg font-semibold text-white">{title}</div>
        {summary ? (
          <div className="mt-1 text-sm text-zinc-300">{summary}</div>
        ) : null}
      </div>
      {facts.length ? (
        <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-zinc-300">
          {facts.slice(0, 5).map((fact, idx) => (
            <li key={idx}>{fact}</li>
          ))}
        </ul>
      ) : null}
      {sourceUrl ? (
        <div className="text-xs text-zinc-400">
          Source:{' '}
          <a
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-zinc-200 underline decoration-dotted hover:text-white"
          >
            {sourceUrl}
          </a>
        </div>
      ) : null}
    </div>
  );
}

function ResultPanel({ result, onOpen }) {
  return (
    <div className="space-y-3 rounded-2xl border border-white/10 bg-white/[0.03] p-4">
      <div>
        <div className="text-sm text-zinc-400">Title</div>
        <div className="text-xl font-semibold text-white">
          {result.final_post?.title || 'Untitled draft'}
        </div>
      </div>
      <div>
        <div className="text-sm text-zinc-400">Content</div>
        <div className="whitespace-pre-line text-zinc-200">
          {result.final_post?.content || ''}
        </div>
      </div>
      <div>
        <div className="text-sm text-zinc-400">Hashtags</div>
        <div className="mt-2 flex flex-wrap gap-2">
          {(result.final_post?.hashtags ?? []).map((tag) => (
            <Badge key={tag}>{tag}</Badge>
          ))}
        </div>
      </div>
      {result.source_url ? (
        <div className="text-xs text-zinc-500">
          Inspired by:{' '}
          <a
            href={result.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-zinc-300 underline decoration-dotted"
          >
            {result.source_url}
          </a>
        </div>
      ) : null}
      {result.review_feedback ? (
        <div>
          <div className="text-sm text-zinc-400">Reviewer feedback</div>
          <div className="text-zinc-200">{result.review_feedback}</div>
        </div>
      ) : null}
      {result.iterations ? (
        <div className="text-xs text-zinc-500">Iterations: {result.iterations}</div>
      ) : null}
      <div className="flex justify-end">
        <Button onClick={onOpen}>
          Open viewer <ArrowRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
