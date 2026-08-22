import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Upload,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Globe,
  ExternalLink,
} from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Textarea, Field } from '../components/ui/Input.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { ErrorBanner, Spinner } from '../components/ui/Feedback.jsx';
import { MotionPage } from '../components/ui/MotionPage.jsx';

export default function JobImportPage() {
  const api = useApi();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [company, setCompany] = useState('');
  const [description, setDescription] = useState('');
  const [mode, setMode] = useState('url'); // 'url' | 'manual'
  const [importing, setImporting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setImporting(true);
    try {
      if (mode === 'url') {
        if (!url.trim()) {
          toast.error('URL is required.');
          return;
        }
        const res = await api.importJob({
          url: url.trim(),
          title: title.trim(),
          company: company.trim(),
        });
        toast.success('Job imported. Review and save.');
        navigate(`/jobs/${res.job?.id || res.job_id || ''}`);
      } else {
        if (!title.trim()) {
          toast.error('Title is required.');
          return;
        }
        const res = await api.createJob({
          title: title.trim(),
          company: company.trim(),
          description: description,
        });
        toast.success('Job created.');
        navigate(`/jobs/${res.id}`);
      }
    } catch (e) {
      toast.error('Save failed', e?.message);
    } finally {
      setImporting(false);
    }
  }

  return (
    <MotionPage className="space-y-6 p-4 md:p-6 lg:p-8">
      <button
        type="button"
        onClick={() => navigate('/job-tracker')}
        className="inline-flex items-center gap-1.5 text-sm text-text-muted transition hover:text-zinc-100"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to Job Tracker
      </button>

      <header>
        <div className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-[11px] uppercase tracking-[0.14em] text-text-secondary">
          <Upload className="h-3 w-3 text-accent-400" />
          Job · Add
        </div>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-4xl">
          <span className="text-text-secondary">Add a </span>
          <span className="gradient-text">job</span>
        </h1>
        <p className="mt-1 max-w-xl text-sm text-text-secondary">
          Import a job from a public URL, or paste the description
          manually. The same JD analysis and matching pipeline
          runs on either source.
        </p>
      </header>

      <ErrorBanner error={null} />

      <div className="glass-inset inline-flex items-center gap-1 rounded-2xl p-1">
        {[
          { value: 'url', label: 'From URL' },
          { value: 'manual', label: 'Manual' },
        ].map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => setMode(opt.value)}
            className={
              'rounded-xl px-3 py-1 text-xs font-medium transition ' +
              (mode === opt.value
                ? 'bg-white/[0.08] text-zinc-100'
                : 'text-text-muted hover:text-zinc-200')
            }
          >
            {opt.label}
          </button>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>
            {mode === 'url' ? 'Import from URL' : 'Add manually'}
          </CardTitle>
          <CardDescription>
            {mode === 'url'
              ? 'The page is fetched through the SSRF-safe source-fetching layer. The Job Description is extracted and a deterministic JD analysis runs.'
              : 'Paste the description exactly as the employer published it. The system never invents missing fields.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-3">
            {mode === 'url' ? (
              <>
                <Field id="import-url" label="Job URL" required>
                  <Input
                    id="import-url"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://jobs.lever.co/... or https://linkedin.com/jobs/..."
                    leftIcon={<Globe className="h-3.5 w-3.5" />}
                  />
                </Field>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field id="import-title" label="Title" optional>
                    <Input
                      id="import-title"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      placeholder="Override the extracted title"
                    />
                  </Field>
                  <Field id="import-company" label="Company" optional>
                    <Input
                      id="import-company"
                      value={company}
                      onChange={(e) => setCompany(e.target.value)}
                      placeholder="Override the extracted company"
                    />
                  </Field>
                </div>
                <p className="text-xs text-text-muted">
                  Imports are subject to the existing SSRF guard. Loopback,
                  private networks, and cloud-metadata endpoints are
                  rejected. Manual paste is recommended for blocked sites.
                </p>
              </>
            ) : (
              <>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field id="manual-title" label="Title" required>
                    <Input
                      id="manual-title"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      placeholder="Senior Software Engineer"
                    />
                  </Field>
                  <Field id="manual-company" label="Company" optional>
                    <Input
                      id="manual-company"
                      value={company}
                      onChange={(e) => setCompany(e.target.value)}
                      placeholder="Acme Corp"
                    />
                  </Field>
                </div>
                <Field id="manual-desc" label="Description" required>
                  <Textarea
                    id="manual-desc"
                    rows={10}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Paste the full Job Description here."
                  />
                </Field>
              </>
            )}
            <div className="flex justify-end gap-2">
              <Button
                variant="ghost"
                type="button"
                onClick={() => navigate('/job-tracker')}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="brand"
                loading={importing}
                leftIcon={<Sparkles className="h-4 w-4" />}
              >
                {importing
                  ? mode === 'url'
                    ? 'Importing…'
                    : 'Saving…'
                  : mode === 'url'
                  ? 'Import job'
                  : 'Create job'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </MotionPage>
  );
}
