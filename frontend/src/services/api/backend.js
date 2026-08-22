import { useAuth } from '../../context/AuthContext.jsx';
import { useMemo } from 'react';
import { request } from './client.js';

async function getIdToken(user) {
  if (!user) return null;
  try {
    return await user.getIdToken();
  } catch {
    return null;
  }
}

export function useApi() {
  const { user } = useAuth();

  return useMemo(() => {
    const authedRequest = async (options) => {
      const token = await getIdToken(user);
      return request({ ...options, token });
    };

    return {
      // H7 (Phase 8C) - removed orphaned methods that had no UI caller
      // after P1: getCurrentUser, getRecentActivity, createDraft,
      // editDraft. These are not used by any page today; the SPA now
      // uses DraftsPage/DraftViewerPage for the draft CRUD flow
      // and the dashboard activity feed reads from the summary payload.
      getProfile: () => authedRequest({ path: '/api/v1/profile' }),
      updateProfile: (payload) =>
        authedRequest({ method: 'PUT', path: '/api/v1/profile', body: payload }),
      getSettings: () => authedRequest({ path: '/api/v1/settings' }),
      updateSettings: (payload) =>
        authedRequest({ method: 'PUT', path: '/api/v1/settings', body: payload }),
      publishDraft: (draftId) =>
        authedRequest({ method: 'POST', path: `/api/v1/drafts/${encodeURIComponent(draftId)}/publish` }),
      getDashboardSummary: () => authedRequest({ path: '/api/v1/dashboard/summary' }),
      generateContent: (payload) =>
        authedRequest({ method: 'POST', path: '/api/v1/content/generate', body: payload }),
      // Phase 3 — synchronous source preview. The "Analyze Source"
      // button on Create Post. No draft is created, no LLM is called.
      previewSource: (url) =>
        authedRequest({
          method: 'POST',
          path: '/api/v1/content/source/preview',
          body: { url },
        }),
      // Phase 8D — async URL-generation job. Used by the legacy
      // flow for very long-running fetches; the synchronous
      // /generate path is preferred for normal use.
      generateFromUrl: (payload) =>
        authedRequest({
          method: 'POST',
          path: '/api/v1/content/generate-from-url',
          body: payload,
        }),
      getUrlJob: (jobId) =>
        authedRequest({
          path: `/api/v1/content/generate-from-url/${encodeURIComponent(jobId)}`,
        }),
      listDrafts: (params = {}) => {
        const search = new URLSearchParams();
        if (params.status) search.set('status', params.status);
        if (params.search) search.set('search', params.search);
        if (params.sort_by) search.set('sort_by', params.sort_by);
        if (params.page) search.set('page', String(params.page));
        if (params.page_size) search.set('page_size', String(params.page_size));
        const qs = search.toString();
        return authedRequest({ path: `/api/v1/drafts${qs ? `?${qs}` : ''}` });
      },
      getDraft: (draftId) =>
        authedRequest({ path: `/api/v1/drafts/${encodeURIComponent(draftId)}` }),
      updateDraft: (draftId, payload) =>
        authedRequest({ method: 'PUT', path: `/api/v1/drafts/${encodeURIComponent(draftId)}`, body: payload }),
      deleteDraft: (draftId) =>
        authedRequest({ method: 'DELETE', path: `/api/v1/drafts/${encodeURIComponent(draftId)}` }),
      getApprovalQueue: () => authedRequest({ path: '/api/v1/approval/queue' }),
      getApprovalDraft: (tokenValue) =>
        authedRequest({ path: `/api/v1/approval/draft?token=${encodeURIComponent(tokenValue)}` }),
      approveDraft: (payload) =>
        authedRequest({ method: 'POST', path: '/api/v1/approval/approve', body: payload }),
      rejectDraft: (payload) =>
        authedRequest({ method: 'POST', path: '/api/v1/approval/reject', body: payload }),
      getPublishedDrafts: () => authedRequest({ path: '/api/v1/approval/published' }),
      getScheduledJobs: () => authedRequest({ path: '/api/v1/scheduler/jobs' }),
      schedulePost: (payload) =>
        authedRequest({ method: 'POST', path: '/api/v1/scheduler/schedule', body: payload }),
      cancelScheduledJob: (jobId) =>
        authedRequest({ method: 'DELETE', path: `/api/v1/scheduler/jobs/${encodeURIComponent(jobId)}` }),
      getLinkedInStatus: () => authedRequest({ path: '/api/v1/linkedin/status' }),
      startLinkedInConnect: () => authedRequest({ path: '/api/v1/linkedin/connect' }),
      disconnectLinkedIn: () =>
        authedRequest({ method: 'POST', path: '/api/v1/linkedin/disconnect' }),
      healthCheck: () => request({ path: '/health' }),
      // Phase 10 / AI Resume Studio
      listResumes: () => authedRequest({ path: '/api/v1/resumes' }),
      getResumeDashboard: () =>
        authedRequest({ path: '/api/v1/resumes/dashboard' }),
      getResume: (resumeId) =>
        authedRequest({
          path: `/api/v1/resumes/${encodeURIComponent(resumeId)}`,
        }),
      createResume: (payload) =>
        authedRequest({ method: 'POST', path: '/api/v1/resumes', body: payload }),
      updateResume: (resumeId, payload) =>
        authedRequest({
          method: 'PUT',
          path: `/api/v1/resumes/${encodeURIComponent(resumeId)}`,
          body: payload,
        }),
      deleteResume: (resumeId) =>
        authedRequest({
          method: 'DELETE',
          path: `/api/v1/resumes/${encodeURIComponent(resumeId)}`,
        }),
      createResumeVersion: (resumeId, payload) =>
        authedRequest({
          method: 'POST',
          path: `/api/v1/resumes/${encodeURIComponent(resumeId)}/versions`,
          body: payload,
        }),
      uploadResume: async (file, title, targetRole = '') => {
        const form = new FormData();
        form.append('file', file);
        form.append('title', title);
        if (targetRole) form.append('target_role', targetRole);
        return authedRequest({
          method: 'POST',
          path: '/api/v1/resumes/upload',
          body: form,
        });
      },
      parseResumeText: (text) =>
        authedRequest({
          method: 'POST',
          path: '/api/v1/resumes/parse',
          body: { text },
        }),
      analyzeResume: (resumeId, payload) =>
        authedRequest({
          method: 'POST',
          path: `/api/v1/resumes/${encodeURIComponent(resumeId)}/ats/analyze`,
          body: payload,
        }),
      listResumeAnalyses: (resumeId) =>
        authedRequest({
          path: `/api/v1/resumes/${encodeURIComponent(resumeId)}/ats/analyses`,
        }),
      getResumeAnalysis: (analysisId) =>
        authedRequest({
          path: `/api/v1/resumes/ats/analyses/${encodeURIComponent(analysisId)}`,
        }),
      createLinkedInFromResume: (resumeId, payload) =>
        authedRequest({
          method: 'POST',
          path: `/api/v1/resumes/${encodeURIComponent(resumeId)}/linkedin`,
          body: payload,
        }),
    };
  }, [user]);
}