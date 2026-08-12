"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useAppStore } from "@/store/use-app-store";
import { useDraftLibraryStore } from "@/store/use-draft-library";

const PAGE_SIZE = 4;

export default function DraftsPage() {
  const { title, content, hashtags, reviewScore, isReady } = useAppStore();
  const { drafts, currentDraftId, setCurrentDraft, updateDraft, deleteDraft, duplicateDraft } = useDraftLibraryStore();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortBy, setSortBy] = useState("updated");
  const [page, setPage] = useState(1);

  const filteredDrafts = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    const result = drafts.filter((draft) => {
      const matchesSearch = !normalized || [draft.title, draft.topic, draft.content].join(" ").toLowerCase().includes(normalized);
      const matchesStatus = statusFilter === "all" || draft.status === statusFilter;
      return matchesSearch && matchesStatus;
    });

    result.sort((left, right) => {
      if (sortBy === "title") return left.title.localeCompare(right.title);
      if (sortBy === "created") return left.createdAt.localeCompare(right.createdAt);
      return left.updatedAt.localeCompare(right.updatedAt);
    });

    return result;
  }, [drafts, search, sortBy, statusFilter]);

  const totalPages = Math.max(1, Math.ceil(filteredDrafts.length / PAGE_SIZE));
  const paginatedDrafts = filteredDrafts.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const selectedDraft = drafts.find((draft) => draft.id === currentDraftId) ?? null;

  function saveSelectedDraftEdits(field: "title" | "content" | "topic", value: string) {
    if (!currentDraftId) return;
    updateDraft(currentDraftId, { [field]: value });
    toast.success("Draft autosaved");
  }

  function openDraft(id: string) {
    setCurrentDraft(id);
    const draft = drafts.find((item) => item.id === id);
    if (draft) {
      useAppStore.getState().setDraft({
        title: draft.title,
        content: draft.content,
        hashtags: draft.hashtags,
        reviewScore: draft.reviewScore,
        reviewFeedback: draft.reviewFeedback,
        researchSummary: draft.researchSummary,
      });
    }
  }

  function handleDelete(id: string) {
    const confirmed = window.confirm("Delete this draft permanently?");
    if (confirmed) {
      deleteDraft(id);
      toast.success("Draft deleted");
    }
  }

  return (
    <main className="min-h-screen bg-[#09090b] px-4 py-6 text-zinc-50 md:px-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-semibold">Drafts</h1>
            <p className="text-zinc-400">Search, filter, edit, rename, duplicate, and organize your draft library.</p>
          </div>
          <Link href="/create-post">
            <Button>Generate New Draft</Button>
          </Link>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1.25fr_0.75fr]">
          <Card className="bg-zinc-950/70">
            <CardHeader>
              <CardTitle>Draft Library</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 md:grid-cols-3">
                <Input placeholder="Search drafts" value={search} onChange={(event) => setSearch(event.target.value)} />
                <select className="h-10 rounded-xl border border-zinc-700 bg-transparent px-3 text-sm" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                  <option value="all">All statuses</option>
                  <option value="draft">Draft</option>
                  <option value="approved">Approved</option>
                  <option value="published">Published</option>
                </select>
                <select className="h-10 rounded-xl border border-zinc-700 bg-transparent px-3 text-sm" value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
                  <option value="updated">Sort by updated</option>
                  <option value="created">Sort by created</option>
                  <option value="title">Sort by title</option>
                </select>
              </div>

              <div className="grid gap-3">
                {paginatedDrafts.length ? (
                  paginatedDrafts.map((draft) => (
                    <div key={draft.id} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                        <div className="space-y-1">
                          <div className="text-lg font-semibold text-white">{draft.title}</div>
                          <div className="text-sm text-zinc-400">Topic: {draft.topic}</div>
                          <div className="text-xs text-zinc-500">Created {new Date(draft.createdAt).toLocaleString()} · Updated {new Date(draft.updatedAt).toLocaleString()}</div>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Badge>{draft.status}</Badge>
                          <Badge variant="outline">Review {draft.reviewScore ?? "—"}</Badge>
                          <Badge variant="outline">{draft.workflowStatus}</Badge>
                        </div>
                      </div>

                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button size="sm" variant="outline" onClick={() => openDraft(draft.id)}>Open Draft</Button>
                        <Button size="sm" variant="outline" onClick={() => duplicateDraft(draft.id)}>Duplicate</Button>
                        <Button size="sm" variant="outline" onClick={() => handleDelete(draft.id)}>Delete</Button>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="rounded-2xl border border-dashed border-white/10 bg-white/5 p-4 text-zinc-400">
                    No drafts match the current search or status filter.
                  </div>
                )}
              </div>

              <div className="flex items-center justify-between gap-3">
                <div className="text-sm text-zinc-400">Page {page} / {totalPages}</div>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" disabled={page === 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>Previous</Button>
                  <Button size="sm" variant="outline" disabled={page === totalPages} onClick={() => setPage((current) => Math.min(totalPages, current + 1))}>Next</Button>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-zinc-950/70">
            <CardHeader>
              <CardTitle>Working Draft</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {isReady || selectedDraft ? (
                <>
                  <div>
                    <label className="mb-2 block text-sm text-zinc-400">Title</label>
                    <Input
                      value={selectedDraft?.title ?? title}
                      onChange={(event) => {
                        if (selectedDraft) {
                          saveSelectedDraftEdits("title", event.target.value);
                        }
                      }}
                    />
                  </div>
                  <div>
                    <label className="mb-2 block text-sm text-zinc-400">Topic</label>
                    <Input
                      value={selectedDraft?.topic ?? ""}
                      onChange={(event) => {
                        if (selectedDraft) {
                          saveSelectedDraftEdits("topic", event.target.value);
                        }
                      }}
                    />
                  </div>
                  <div>
                    <label className="mb-2 block text-sm text-zinc-400">Content</label>
                    <Textarea
                      value={selectedDraft?.content ?? content}
                      rows={12}
                      onChange={(event) => {
                        if (selectedDraft) {
                          saveSelectedDraftEdits("content", event.target.value);
                        }
                      }}
                    />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {(selectedDraft?.hashtags ?? hashtags).map((tag) => (
                      <Badge key={tag}>{tag}</Badge>
                    ))}
                  </div>
                  <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-sm text-zinc-300">
                    Review Score: {selectedDraft?.reviewScore ?? reviewScore ?? "—"}/10
                  </div>
                  <Link href="/draft-viewer">
                    <Button variant="outline" className="w-full">Open Draft Viewer</Button>
                  </Link>
                </>
              ) : (
                <div className="rounded-2xl border border-dashed border-white/10 p-4 text-sm text-zinc-400">
                  No draft is loaded yet. Generate a new post to populate this workspace.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </main>
  );
}
