import { createContext, useCallback, useContext, useMemo, useState } from 'react';

const DraftsContext = createContext(null);

export function DraftsProvider({ children }) {
  const [drafts, setDrafts] = useState([]);
  const [currentDraftId, setCurrentDraftId] = useState(null);

  const updateDraft = useCallback((id, updates) => {
    setDrafts((current) =>
      current.map((draft) =>
        draft.id === id ? { ...draft, ...updates, updatedAt: new Date().toISOString() } : draft,
      ),
    );
  }, []);

  const deleteDraft = useCallback((id) => {
    setDrafts((current) => current.filter((draft) => draft.id !== id));
    setCurrentDraftId((current) => (current === id ? null : current));
  }, []);

  const setCurrentDraft = useCallback((id) => {
    setCurrentDraftId(id);
  }, []);

  const currentDraft = useMemo(
    () => drafts.find((draft) => draft.id === currentDraftId) ?? null,
    [drafts, currentDraftId],
  );

  const value = useMemo(
    () => ({
      drafts,
      currentDraft,
      currentDraftId,
      setDrafts,
      updateDraft,
      deleteDraft,
      setCurrentDraft,
    }),
    [drafts, currentDraft, currentDraftId, setDrafts, updateDraft, deleteDraft, setCurrentDraft],
  );

  return <DraftsContext.Provider value={value}>{children}</DraftsContext.Provider>;
}

export function useDrafts() {
  const ctx = useContext(DraftsContext);
  if (!ctx) {
    throw new Error('useDrafts must be used inside DraftsProvider');
  }
  return ctx;
}