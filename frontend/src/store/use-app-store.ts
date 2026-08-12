import { create } from "zustand";

type DraftState = {
  title: string;
  content: string;
  hashtags: string[];
  reviewScore?: number;
  reviewFeedback?: string;
  researchSummary?: string;
  isReady: boolean;
  setDraft: (draft: Partial<DraftState>) => void;
  resetDraft: () => void;
};

export const useAppStore = create<DraftState>((set) => ({
  title: "",
  content: "",
  hashtags: [],
  reviewScore: undefined,
  reviewFeedback: undefined,
  researchSummary: undefined,
  isReady: false,
  setDraft: (draft) => set((state) => ({ ...state, ...draft, isReady: true })),
  resetDraft: () =>
    set({
      title: "",
      content: "",
      hashtags: [],
      reviewScore: undefined,
      reviewFeedback: undefined,
      researchSummary: undefined,
      isReady: false,
    }),
}));
