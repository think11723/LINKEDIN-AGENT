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
    };
  }, [user]);
}