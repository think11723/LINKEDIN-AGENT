import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, ArrowRight } from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Textarea } from '../components/ui/Input.jsx';
import { Spinner, ErrorBanner, EmptyState } from '../components/ui/Feedback.jsx';
import { Badge } from '../components/ui/Badge.jsx';

/**
 * Phase 8B P1-2 — honest state machine.
 *
 * The backend is a synchronous request/response — there is no real
 * progress stream. We expose four honest states: idle, generating,
 * success, failure. No fake step indicator. A comment in the JSX records
 * the future opportunity to add SSE / WebSocket streaming.
 */
export default function CreatePostPage() {
  const api = useApi();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [topic, setTopic] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [state, setState] = useState('idle'); // idle | generating | success | failure
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  async function handleGenerate() {
    if (!topic.trim()) {
      toast.error('Please enter a topic.');
      return;
    }
    setSubmitting(true);
    setError(null);
    setState('generating');
    try {
      const response = await api.generateContent({ topic: topic.trim() });
      setResult(response);
      setState('success');
      toast.success('Content generated successfully.');
    } catch (err) {
      setError(err);
      setState('failure');
      toast.error('Generation failed', err?.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold">Create Post</h1>
        <p className="text-zinc-400">Generate a LinkedIn draft from a topic.</p>
      </div>

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
              onClick={handleGenerate}
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
              {state === 'idle' && 'Submit a topic to generate a draft.'}
              {state === 'generating' && 'Calling the workflow…'}
              {state === 'success' && 'Draft generated. Open the viewer to edit, schedule, or publish.'}
              {state === 'failure' && 'Generation failed. See the error below.'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <ErrorBanner error={error} onRetry={handleGenerate} />
            {state === 'generating' ? (
              <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-sm text-zinc-300">
                <Spinner /> Generating draft — typically 30–90s.
              </div>
            ) : null}
            {state === 'success' && result ? (
              <ResultPanel result={result} onOpen={() => navigate(`/drafts/${result.draft_id}`)} />
            ) : null}
            {state === 'idle' ? (
              <EmptyState
                title="Nothing to show yet"
                description="The generated draft will appear here."
              />
            ) : null}
          </CardContent>
        </Card>
      </div>
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
