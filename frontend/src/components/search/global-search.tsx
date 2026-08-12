"use client";

import { useMemo, useState } from "react";
import { Search } from "lucide-react";

import { Input } from "@/components/ui/input";
import { useDraftLibraryStore } from "@/store/use-draft-library";

export function GlobalSearch() {
  const [query, setQuery] = useState("");
  const drafts = useDraftLibraryStore((state) => state.drafts);

  const results = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return [];

    return drafts.filter((draft) => {
      return [draft.title, draft.topic, draft.content, ...(draft.hashtags ?? [])]
        .join(" ")
        .toLowerCase()
        .includes(normalized);
    });
  }, [drafts, query]);

  return (
    <div className="relative w-full max-w-xl">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
      <Input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search drafts, approvals, scheduled or published posts"
        className="pl-9"
        aria-label="Global search"
      />
      {query ? (
        <div className="absolute left-0 right-0 top-12 z-20 rounded-xl border border-white/10 bg-zinc-950 p-2 shadow-2xl">
          {results.length ? (
            <div className="max-h-64 space-y-1 overflow-auto">
              {results.map((draft) => (
                <div key={draft.id} className="rounded-lg bg-white/5 px-3 py-2 text-sm text-zinc-200">
                  <div className="font-medium text-white">{draft.title}</div>
                  <div className="text-zinc-400">{draft.topic}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="px-3 py-2 text-sm text-zinc-400">No matching drafts found.</div>
          )}
        </div>
      ) : null}
    </div>
  );
}
