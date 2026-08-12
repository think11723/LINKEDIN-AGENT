import { create } from "zustand";
import { persist } from "zustand/middleware";

export type DraftRecord = {
  id: string;
  title: string;
  topic: string;
  content: string;
  hashtags: string[];
  reviewScore?: number;
  reviewFeedback?: string;
  researchSummary?: string;
  status: string;
  workflowStatus: string;
  approvalStatus: string;
  createdAt: string;
  updatedAt: string;
  provider?: string;
  model?: string;
  generationTime?: number;
  approvalToken?: string;
};

type DraftLibraryState = {
  drafts: DraftRecord[];
  currentDraftId?: string;
  addDraft: (draft: Omit<DraftRecord, "createdAt" | "updatedAt"> & { createdAt?: string; updatedAt?: string }) => void;
  updateDraft: (id: string, updates: Partial<DraftRecord>) => void;
  deleteDraft: (id: string) => void;
  duplicateDraft: (id: string) => void;
  setCurrentDraft: (id: string) => void;
  resetCurrentDraft: () => void;
};

export const useDraftLibraryStore = create<DraftLibraryState>()(
  persist(
    (set, get) => ({
      drafts: [],
      currentDraftId: undefined,
      addDraft: (draft) => {
        const timestamp = new Date().toISOString();
        const createdAt = draft.createdAt ?? timestamp;
        const nextDraft: DraftRecord = {
          ...draft,
          createdAt,
          updatedAt: draft.updatedAt ?? timestamp,
          status: draft.status ?? "draft",
          workflowStatus: draft.workflowStatus ?? "completed",
          approvalStatus: draft.approvalStatus ?? "pending",
        };

        set((state) => ({
          drafts: [nextDraft, ...state.drafts],
          currentDraftId: nextDraft.id,
        }));
      },
      updateDraft: (id, updates) => {
        set((state) => ({
          drafts: state.drafts.map((draft) =>
            draft.id === id
              ? {
                  ...draft,
                  ...updates,
                  updatedAt: new Date().toISOString(),
                }
              : draft,
          ),
        }));
      },
      deleteDraft: (id) => {
        set((state) => ({
          drafts: state.drafts.filter((draft) => draft.id !== id),
          currentDraftId: state.currentDraftId === id ? undefined : state.currentDraftId,
        }));
      },
      duplicateDraft: (id) => {
        const source = get().drafts.find((draft) => draft.id === id);
        if (!source) return;

        const timestamp = new Date().toISOString();
        const duplicateDraft: DraftRecord = {
          ...source,
          id: `${source.id}-${Date.now()}`,
          title: `${source.title} Copy`,
          createdAt: timestamp,
          updatedAt: timestamp,
          approvalStatus: "draft",
        };

        set((state) => ({
          drafts: [duplicateDraft, ...state.drafts],
          currentDraftId: duplicateDraft.id,
        }));
      },
      setCurrentDraft: (id) => set({ currentDraftId: id }),
      resetCurrentDraft: () => set({ currentDraftId: undefined }),
    }),
    {
      name: "linkedin-ai-studio-drafts",
    },
  ),
);
