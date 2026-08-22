import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowLeft,
  Save,
  Trash2,
  Plus,
  Sparkles,
  Linkedin,
  Target,
  Briefcase,
  GraduationCap,
  Award,
  Layers,
  Trophy,
  Link2,
  AlertCircle,
  Eye,
  X,
} from 'lucide-react';

import { useApi } from '../services/api/backend.js';
import { useToast } from '../context/ToastContext.jsx';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input, Textarea, Field } from '../components/ui/Input.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { ConfirmDialog } from '../components/ConfirmDialog.jsx';
import { ErrorBanner, Skeleton, Spinner } from '../components/ui/Feedback.jsx';
import { MotionPage } from '../components/ui/MotionPage.jsx';

const EMPTY_RESUME = {
  personal: { full_name: '', headline: '', email: '', phone: '', location: '', linkedin_url: '', github_url: '', portfolio_url: '' },
  summary: '',
  experience: [],
  education: [],
  skills: [],
  projects: [],
  certifications: [],
  achievements: [],
  links: [],
};

function Section({ icon: Icon, title, children, action, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <Card>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 border-b border-white/[0.06] p-5 text-left"
      >
        <div className="flex items-center gap-3">
          <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-white/[0.08] bg-gradient-brand-soft text-brand-300">
            <Icon className="h-4 w-4" />
          </span>
          <div>
            <div className="text-sm font-semibold text-zinc-100">{title}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {action}
          <span className="text-text-muted">{open ? '−' : '+'}</span>
        </div>
      </button>
      {open ? (
        <CardContent className="space-y-3 p-5">{children}</CardContent>
      ) : null}
    </Card>
  );
}

function ListField({ label, value, onChange, placeholder, rows = 2 }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-text-muted">
        {label}
      </label>
      <Input
        value={value || ''}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  );
}

function ExperienceRow({ item, onChange, onRemove }) {
  const update = (field, value) => onChange({ ...item, [field]: value });
  const updateAchievement = (idx, value) => {
    const arr = [...(item.achievements || [])];
    arr[idx] = value;
    update('achievements', arr);
  };
  const removeAchievement = (idx) => {
    const arr = [...(item.achievements || [])];
    arr.splice(idx, 1);
    update('achievements', arr);
  };
  const addAchievement = () =>
    update('achievements', [...(item.achievements || []), '']);
  const updateTech = (idx, value) => {
    const arr = [...(item.technologies || [])];
    arr[idx] = value;
    update('technologies', arr);
  };
  return (
    <div className="space-y-3 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-3">
      <div className="grid gap-2 sm:grid-cols-2">
        <Input
          value={item.role || ''}
          onChange={(e) => update('role', e.target.value)}
          placeholder="Role"
        />
        <Input
          value={item.company || ''}
          onChange={(e) => update('company', e.target.value)}
          placeholder="Company"
        />
        <Input
          value={item.start_date || ''}
          onChange={(e) => update('start_date', e.target.value)}
          placeholder="Start (e.g. Jan 2022)"
        />
        <Input
          value={item.end_date || ''}
          onChange={(e) => update('end_date', e.target.value)}
          placeholder="End (e.g. Present)"
        />
      </div>
      <Textarea
        rows={2}
        value={item.description || ''}
        onChange={(e) => update('description', e.target.value)}
        placeholder="What you did"
      />
      <div>
        <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-text-muted">
          Achievements
        </label>
        <div className="space-y-2">
          {(item.achievements || []).map((a, idx) => (
            <div key={idx} className="flex gap-2">
              <Input
                value={a || ''}
                onChange={(e) => updateAchievement(idx, e.target.value)}
                placeholder="What you achieved (use real numbers; no fabrication)"
              />
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => removeAchievement(idx)}
                aria-label="Remove achievement"
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
          <Button
            variant="ghost"
            size="sm"
            onClick={addAchievement}
            leftIcon={<Plus className="h-3.5 w-3.5" />}
          >
            Add achievement
          </Button>
        </div>
      </div>
      <div>
        <label className="mb-1 block text-xs font-semibold uppercase tracking-wider text-text-muted">
          Technologies
        </label>
        <div className="space-y-2">
          {(item.technologies || []).map((t, idx) => (
            <div key={idx} className="flex gap-2">
              <Input
                value={t || ''}
                onChange={(e) => updateTech(idx, e.target.value)}
                placeholder="Technology"
              />
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => {
                  const arr = [...(item.technologies || [])];
                  arr.splice(idx, 1);
                  update('technologies', arr);
                }}
                aria-label="Remove technology"
              >
                <X className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => update('technologies', [...(item.technologies || []), ''])}
            leftIcon={<Plus className="h-3.5 w-3.5" />}
          >
            Add technology
          </Button>
        </div>
      </div>
      <div className="flex justify-end">
        <Button
          variant="ghost"
          size="sm"
          onClick={onRemove}
          className="text-rose-300 hover:text-rose-200"
        >
          Remove role
        </Button>
      </div>
    </div>
  );
}

function ProjectRow({ item, onChange, onRemove }) {
  const update = (field, value) => onChange({ ...item, [field]: value });
  return (
    <div className="space-y-3 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-3">
      <div className="grid gap-2 sm:grid-cols-2">
        <Input
          value={item.name || ''}
          onChange={(e) => update('name', e.target.value)}
          placeholder="Project name"
        />
        <Input
          value={(item.technologies || []).join(', ')}
          onChange={(e) => update('technologies', e.target.value.split(',').map((s) => s.trim()).filter(Boolean))}
          placeholder="Tech (comma-separated)"
        />
      </div>
      <Textarea
        rows={2}
        value={item.description || ''}
        onChange={(e) => update('description', e.target.value)}
        placeholder="Description"
      />
      <div className="grid gap-2 sm:grid-cols-2">
        <Input
          value={item.github_url || ''}
          onChange={(e) => update('github_url', e.target.value)}
          placeholder="GitHub URL"
        />
        <Input
          value={item.live_url || ''}
          onChange={(e) => update('live_url', e.target.value)}
          placeholder="Live URL"
        />
      </div>
      <div className="flex justify-end">
        <Button
          variant="ghost"
          size="sm"
          onClick={onRemove}
          className="text-rose-300 hover:text-rose-200"
        >
          Remove project
        </Button>
      </div>
    </div>
  );
}

function EducationRow({ item, onChange, onRemove }) {
  const update = (field, value) => onChange({ ...item, [field]: value });
  return (
    <div className="space-y-2 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-3">
      <div className="grid gap-2 sm:grid-cols-2">
        <Input
          value={item.institution || ''}
          onChange={(e) => update('institution', e.target.value)}
          placeholder="Institution"
        />
        <Input
          value={item.degree || ''}
          onChange={(e) => update('degree', e.target.value)}
          placeholder="Degree"
        />
        <Input
          value={item.field || ''}
          onChange={(e) => update('field', e.target.value)}
          placeholder="Field of study"
        />
        <Input
          value={item.end_date || ''}
          onChange={(e) => update('end_date', e.target.value)}
          placeholder="End year (e.g. 2020)"
        />
      </div>
      <div className="flex justify-end">
        <Button
          variant="ghost"
          size="sm"
          onClick={onRemove}
          className="text-rose-300 hover:text-rose-200"
        >
          Remove education
        </Button>
      </div>
    </div>
  );
}

function SkillsEditor({ skills, onChange }) {
  const update = (idx, field, value) => {
    const next = skills.map((g, i) => (i === idx ? { ...g, [field]: value } : g));
    onChange(next);
  };
  const updateCategorySkill = (gIdx, sIdx, value) => {
    const next = skills.map((g, i) => {
      if (i !== gIdx) return g;
      const arr = [...(g.skills || [])];
      arr[sIdx] = value;
      return { ...g, skills: arr };
    });
    onChange(next);
  };
  const addCategory = () => onChange([...skills, { category: '', skills: [] }]);
  const removeCategory = (idx) => onChange(skills.filter((_, i) => i !== idx));
  const addSkill = (idx) =>
    onChange(
      skills.map((g, i) =>
        i === idx ? { ...g, skills: [...(g.skills || []), ''] } : g
      )
    );
  const removeSkill = (gIdx, sIdx) =>
    onChange(
      skills.map((g, i) => {
        if (i !== gIdx) return g;
        const arr = (g.skills || []).filter((_, j) => j !== sIdx);
        return { ...g, skills: arr };
      })
    );
  return (
    <div className="space-y-3">
      {skills.map((g, idx) => (
        <div key={idx} className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-3">
          <div className="flex items-center gap-2">
            <Input
              value={g.category || ''}
              onChange={(e) => update(idx, 'category', e.target.value)}
              placeholder="Category (e.g. Languages)"
            />
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => removeCategory(idx)}
              aria-label="Remove category"
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
          <div className="mt-2 space-y-2">
            {(g.skills || []).map((s, sIdx) => (
              <div key={sIdx} className="flex gap-2">
                <Input
                  value={s || ''}
                  onChange={(e) => updateCategorySkill(idx, sIdx, e.target.value)}
                  placeholder="Skill"
                />
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => removeSkill(idx, sIdx)}
                  aria-label="Remove skill"
                >
                  <X className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => addSkill(idx)}
              leftIcon={<Plus className="h-3.5 w-3.5" />}
            >
              Add skill
            </Button>
          </div>
        </div>
      ))}
      <Button
        variant="secondary"
        size="sm"
        onClick={addCategory}
        leftIcon={<Plus className="h-3.5 w-3.5" />}
      >
        Add category
      </Button>
    </div>
  );
}

export default function ResumeEditorPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const api = useApi();
  const { toast } = useToast();

  const [resume, setResume] = useState(null);
  const [meta, setMeta] = useState({ title: '', target_role: '' });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const data = await api.getResume(id);
      if (!data) {
        setErr({ message: 'Resume not found.' });
        setResume(null);
      } else {
        setResume(data.resume || EMPTY_RESUME);
        setMeta({ title: data.title || '', target_role: data.target_role || '' });
        setErr(null);
      }
    } catch (e) {
      setErr(e);
    } finally {
      setLoading(false);
    }
  }, [api, id]);

  useEffect(() => {
    load();
  }, [load]);

  function update(field, value) {
    setResume((prev) => ({ ...prev, [field]: value }));
  }
  function updatePersonal(field, value) {
    setResume((prev) => ({ ...prev, personal: { ...(prev.personal || {}), [field]: value } }));
  }
  function updateList(field, idx, value) {
    setResume((prev) => {
      const arr = [...(prev[field] || [])];
      arr[idx] = value;
      return { ...prev, [field]: arr };
    });
  }
  function addListItem(field) {
    setResume((prev) => ({
      ...prev,
      [field]: [...(prev[field] || []), defaultItem(field)],
    }));
  }
  function removeListItem(field, idx) {
    setResume((prev) => {
      const arr = (prev[field] || []).filter((_, i) => i !== idx);
      return { ...prev, [field]: arr };
    });
  }

  async function handleSave() {
    if (!resume) return;
    setSaving(true);
    try {
      await api.updateResume(id, {
        title: meta.title.trim(),
        target_role: meta.target_role.trim(),
        resume,
      });
      toast.success('Resume saved.');
    } catch (e) {
      toast.error('Save failed', e?.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await api.deleteResume(id);
      toast.success('Resume deleted.');
      navigate('/resume');
    } catch (e) {
      toast.error('Delete failed', e?.message);
    } finally {
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  async function handleVersion() {
    const newTitle = window.prompt('New resume title', `${meta.title} (Optimized)`);
    if (!newTitle) return;
    try {
      const created = await api.createResumeVersion(id, { title: newTitle });
      toast.success('Optimized copy created.');
      navigate(`/resume/${created.id}/edit`);
    } catch (e) {
      toast.error('Copy failed', e?.message);
    }
  }

  if (loading) {
    return (
      <MotionPage className="space-y-6 p-4 md:p-6 lg:p-8">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40" />
        <Skeleton className="h-40" />
      </MotionPage>
    );
  }

  if (!resume) {
    return (
      <MotionPage className="space-y-6 p-4 md:p-6 lg:p-8">
        <ErrorBanner error={err} onRetry={load} />
      </MotionPage>
    );
  }

  return (
    <MotionPage className="space-y-6 p-4 md:p-6 lg:p-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Link
          to="/resume"
          className="inline-flex items-center gap-1.5 text-sm text-text-muted transition hover:text-zinc-100"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to Resume Studio
        </Link>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => navigate(`/resume/${id}/ats`)}
            leftIcon={<Target className="h-3.5 w-3.5" />}
          >
            ATS Check
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => navigate(`/resume/${id}/linkedin`)}
            leftIcon={<Linkedin className="h-3.5 w-3.5" />}
          >
            Create LinkedIn Post
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleVersion}
            leftIcon={<Sparkles className="h-3.5 w-3.5" />}
          >
            Create Optimized Copy
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setConfirmDelete(true)}
            className="text-text-muted hover:text-rose-300"
            leftIcon={<Trash2 className="h-3.5 w-3.5" />}
          >
            Delete
          </Button>
          <Button
            variant="brand"
            size="sm"
            onClick={handleSave}
            loading={saving}
            leftIcon={<Save className="h-3.5 w-3.5" />}
          >
            Save
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="grid gap-3 p-5 sm:grid-cols-2">
          <Field id="resume-title" label="Resume title">
            <Input
              id="resume-title"
              value={meta.title}
              onChange={(e) => setMeta((m) => ({ ...m, title: e.target.value }))}
              placeholder="e.g. AI Engineer Resume"
            />
          </Field>
          <Field id="resume-target" label="Target role" optional>
            <Input
              id="resume-target"
              value={meta.target_role}
              onChange={(e) => setMeta((m) => ({ ...m, target_role: e.target.value }))}
              placeholder="e.g. AI Engineer"
            />
          </Field>
        </CardContent>
      </Card>

      <Section icon={Sparkles} title="Personal">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field id="p-name" label="Full name">
            <Input
              id="p-name"
              value={resume.personal?.full_name || ''}
              onChange={(e) => updatePersonal('full_name', e.target.value)}
              placeholder="Jane Doe"
            />
          </Field>
          <Field id="p-headline" label="Headline">
            <Input
              id="p-headline"
              value={resume.personal?.headline || ''}
              onChange={(e) => updatePersonal('headline', e.target.value)}
              placeholder="Senior Software Engineer"
            />
          </Field>
          <Field id="p-email" label="Email">
            <Input
              id="p-email"
              type="email"
              value={resume.personal?.email || ''}
              onChange={(e) => updatePersonal('email', e.target.value)}
              placeholder="jane@example.com"
            />
          </Field>
          <Field id="p-phone" label="Phone" optional>
            <Input
              id="p-phone"
              value={resume.personal?.phone || ''}
              onChange={(e) => updatePersonal('phone', e.target.value)}
              placeholder="+1 555 000 0000"
            />
          </Field>
          <Field id="p-loc" label="Location" optional>
            <Input
              id="p-loc"
              value={resume.personal?.location || ''}
              onChange={(e) => updatePersonal('location', e.target.value)}
              placeholder="San Francisco, CA"
            />
          </Field>
          <Field id="p-li" label="LinkedIn URL" optional>
            <Input
              id="p-li"
              value={resume.personal?.linkedin_url || ''}
              onChange={(e) => updatePersonal('linkedin_url', e.target.value)}
              placeholder="https://linkedin.com/in/jane"
            />
          </Field>
          <Field id="p-gh" label="GitHub URL" optional>
            <Input
              id="p-gh"
              value={resume.personal?.github_url || ''}
              onChange={(e) => updatePersonal('github_url', e.target.value)}
              placeholder="https://github.com/jane"
            />
          </Field>
          <Field id="p-port" label="Portfolio URL" optional>
            <Input
              id="p-port"
              value={resume.personal?.portfolio_url || ''}
              onChange={(e) => updatePersonal('portfolio_url', e.target.value)}
              placeholder="https://jane.dev"
            />
          </Field>
        </div>
      </Section>

      <Section icon={Sparkles} title="Summary">
        <Textarea
          rows={4}
          value={resume.summary || ''}
          onChange={(e) => update('summary', e.target.value)}
          placeholder="2–4 sentences that summarize who you are and what you're looking for."
        />
      </Section>

      <Section icon={Briefcase} title="Experience">
        <div className="space-y-3">
          {(resume.experience || []).map((item, idx) => (
            <ExperienceRow
              key={idx}
              item={item}
              onChange={(value) => updateList('experience', idx, value)}
              onRemove={() => removeListItem('experience', idx)}
            />
          ))}
          <Button
            variant="secondary"
            size="sm"
            onClick={() => addListItem('experience')}
            leftIcon={<Plus className="h-3.5 w-3.5" />}
          >
            Add experience
          </Button>
        </div>
      </Section>

      <Section icon={GraduationCap} title="Education">
        <div className="space-y-3">
          {(resume.education || []).map((item, idx) => (
            <EducationRow
              key={idx}
              item={item}
              onChange={(value) => updateList('education', idx, value)}
              onRemove={() => removeListItem('education', idx)}
            />
          ))}
          <Button
            variant="secondary"
            size="sm"
            onClick={() => addListItem('education')}
            leftIcon={<Plus className="h-3.5 w-3.5" />}
          >
            Add education
          </Button>
        </div>
      </Section>

      <Section icon={Layers} title="Skills">
        <SkillsEditor
          skills={resume.skills || []}
          onChange={(value) => update('skills', value)}
        />
      </Section>

      <Section icon={Sparkles} title="Projects">
        <div className="space-y-3">
          {(resume.projects || []).map((item, idx) => (
            <ProjectRow
              key={idx}
              item={item}
              onChange={(value) => updateList('projects', idx, value)}
              onRemove={() => removeListItem('projects', idx)}
            />
          ))}
          <Button
            variant="secondary"
            size="sm"
            onClick={() => addListItem('projects')}
            leftIcon={<Plus className="h-3.5 w-3.5" />}
          >
            Add project
          </Button>
        </div>
      </Section>

      <Section icon={Award} title="Certifications" defaultOpen={false}>
        <div className="space-y-3">
          {(resume.certifications || []).map((item, idx) => (
            <div
              key={idx}
              className="grid gap-2 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-3 sm:grid-cols-2"
            >
              <Input
                value={item.name || ''}
                onChange={(e) => updateList('certifications', idx, { ...item, name: e.target.value })}
                placeholder="Certification"
              />
              <Input
                value={item.issuing_organization || ''}
                onChange={(e) => updateList('certifications', idx, { ...item, issuing_organization: e.target.value })}
                placeholder="Issuer"
              />
              <Input
                value={item.date || ''}
                onChange={(e) => updateList('certifications', idx, { ...item, date: e.target.value })}
                placeholder="Date"
              />
              <Input
                value={item.credential_url || ''}
                onChange={(e) => updateList('certifications', idx, { ...item, credential_url: e.target.value })}
                placeholder="Credential URL"
              />
            </div>
          ))}
          <Button
            variant="secondary"
            size="sm"
            onClick={() => addListItem('certifications')}
            leftIcon={<Plus className="h-3.5 w-3.5" />}
          >
            Add certification
          </Button>
        </div>
      </Section>

      <Section icon={Trophy} title="Achievements" defaultOpen={false}>
        <div className="space-y-3">
          {(resume.achievements || []).map((item, idx) => (
            <div key={idx} className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-3">
              <Input
                value={item.title || ''}
                onChange={(e) => updateList('achievements', idx, { ...item, title: e.target.value })}
                placeholder="Title"
              />
              <Textarea
                rows={2}
                className="mt-2"
                value={item.description || ''}
                onChange={(e) => updateList('achievements', idx, { ...item, description: e.target.value })}
                placeholder="Description"
              />
            </div>
          ))}
          <Button
            variant="secondary"
            size="sm"
            onClick={() => addListItem('achievements')}
            leftIcon={<Plus className="h-3.5 w-3.5" />}
          >
            Add achievement
          </Button>
        </div>
      </Section>

      <Section icon={Link2} title="Links" defaultOpen={false}>
        <div className="space-y-3">
          {(resume.links || []).map((item, idx) => (
            <div
              key={idx}
              className="grid gap-2 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-3 sm:grid-cols-2"
            >
              <Input
                value={item.label || ''}
                onChange={(e) => updateList('links', idx, { ...item, label: e.target.value })}
                placeholder="Label"
              />
              <Input
                value={item.url || ''}
                onChange={(e) => updateList('links', idx, { ...item, url: e.target.value })}
                placeholder="https://..."
              />
            </div>
          ))}
          <Button
            variant="secondary"
            size="sm"
            onClick={() => addListItem('links')}
            leftIcon={<Plus className="h-3.5 w-3.5" />}
          >
            Add link
          </Button>
        </div>
      </Section>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete this resume?"
        description="This permanently removes the resume and all its ATS analyses. The original is not recoverable."
        confirmLabel="Delete"
        danger
        confirming={deleting}
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(false)}
      />
    </MotionPage>
  );
}

function defaultItem(field) {
  if (field === 'experience') {
    return { role: '', company: '', start_date: '', end_date: '', description: '', achievements: [], technologies: [] };
  }
  if (field === 'education') {
    return { institution: '', degree: '', field: '', end_date: '' };
  }
  if (field === 'projects') {
    return { name: '', description: '', technologies: [], achievements: [], github_url: '', live_url: '' };
  }
  if (field === 'certifications') {
    return { name: '', issuing_organization: '', date: '', credential_url: '' };
  }
  if (field === 'achievements') {
    return { title: '', description: '', date: '' };
  }
  if (field === 'links') {
    return { label: '', url: '' };
  }
  return {};
}
