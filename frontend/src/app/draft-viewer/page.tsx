"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { approveDraft, rejectDraft, schedulePost } from "@/lib/api";
import { useAppStore } from "@/store/use-app-store";
import { useDraftLibraryStore } from "@/store/use-draft-library";

export default function DraftViewerPage() {
  const { title, content, hashtags, reviewScore, reviewFeedback, researchSummary, isReady } = useAppStore();
  const { drafts, currentDraftId, deleteDraft, duplicateDraft, updateDraft } = useDraftLibraryStore();
  const [scheduleTime, setScheduleTime] = useState("");
  const currentDraft = useMemo(
    () => drafts.find((draft) => draft.id === currentDraftId) ?? null,
    [currentDraftId, drafts],
  );

  const displayDraft = currentDraft ?? {
    title,
    topic: "",
    content,
    hashtags,
    reviewScore,
    reviewFeedback,
    researchSummary,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    provider: "OpenRouter",
    model: "gpt-4.1-mini",
    generationTime: 18,
    approvalStatus: "pending",
  };

  async function handleSchedule() {
    if (!scheduleTime || !displayDraft.content || !displayDraft.title) {
      toast.error("Please choose a schedule time first.");
      return;
    }

    try {
      const result = await schedulePost({
        title: displayDraft.title,
        content: displayDraft.content,
        hashtags: displayDraft.hashtags,
        scheduled_time: new Date(scheduleTime).toISOString(),
      });
      toast.success(`Post scheduled for ${result.scheduled_time}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Scheduling failed");
    }
  }

  async function handleApprove() {
    try {
      const result = await approveDraft(currentDraft?.approvalToken ?? "", undefined);
      toast.success(result.message || "Approval sent");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Approve request failed");
    }
  }

  async function handleReject() {
    try {
      const result = await rejectDraft(currentDraft?.approvalToken ?? "");
      toast.success(result.message || "Approval rejected");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Reject request failed");
    }
  }

  async function handleCopy(type: "content" | "linkedin") {
    const contentToCopy = type === "content" ? displayDraft.content : `${displayDraft.title}\n\n${displayDraft.content}\n\n${displayDraft.hashtags.join(" ")}`;
    await navigator.clipboard.writeText(contentToCopy);
    toast.success(type === "content" ? "Content copied" : "LinkedIn version copied");
  }

  function handleExportMarkdown() {
    const blob = new Blob([`# ${displayDraft.title}\n\n${displayDraft.content}\n\n${displayDraft.hashtags.join(" ")}`], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${displayDraft.title.toLowerCase().replace(/\s+/g, "-")}.md`;
    anchor.click();
    URL.revokeObjectURL(url);
    toast.success("Markdown downloaded");
  }

  function handleDelete() {
    if (!currentDraftId) {
      toast.error("No draft selected");
      return;
    }
    const shouldDelete = window.confirm("Delete this draft?");
    if (shouldDelete) {
      deleteDraft(currentDraftId);
      toast.success("Draft deleted");
    }
  }

  return (
    <main className="min-h-screen bg-[#09090b] px-4 py-6 text-zinc-50 md:px-8">
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-semibold">Draft Viewer</h1>
            <p className="text-zinc-400">Review the generated post before publishing.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Link href="/create-post">
              <Button variant="outline">Edit</Button>
            </Link>
            <Button variant="outline" onClick={() => currentDraftId && duplicateDraft(currentDraftId)}>Duplicate</Button>
            <Button variant="outline" onClick={handleDelete}>Delete</Button>
            <Button variant="outline" onClick={handleSchedule}>Schedule</Button>
            <Button variant="outline" onClick={handleApprove}>Publish</Button>
            <Button variant="outline" onClick={handleReject}>Reject</Button>
            <Button variant="outline" onClick={handleExportMarkdown}>Download Markdown</Button>
            <Button variant="outline" onClick={() => handleCopy("content")}>Copy Content</Button>
            <Button variant="outline" onClick={() => handleCopy("linkedin")}>Copy LinkedIn Version</Button>
            <Button variant="outline" onClick={() => window.print()}>Print</Button>
          </div>
        </div>

        <Card className="bg-zinc-950/70">
          <CardHeader>
            <CardTitle>Post Draft</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {!isReady && !currentDraft ? (
              <div className="space-y-3">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-32 w-full" />
                <Skeleton className="h-10 w-40" />
              </div>
            ) : (
              <>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-lg font-semibold">{displayDraft.title}</div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4 text-zinc-200 whitespace-pre-line">{displayDraft.content}</div>
                <div className="flex flex-wrap gap-2">
                  {displayDraft.hashtags.map((tag) => (
                    <Badge key={tag}>{tag}</Badge>
                  ))}
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <div className="text-sm text-zinc-400">Reviewer Score</div>
                    <div className="text-2xl font-semibold">{displayDraft.reviewScore ?? "—"} / 10</div>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <div className="text-sm text-zinc-400">Reviewer Feedback</div>
                    <div className="text-zinc-200">{displayDraft.reviewFeedback ?? "No review feedback yet."}</div>
                  </div>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <div className="text-sm text-zinc-400">Research Summary</div>
                  <div className="text-zinc-200">{displayDraft.researchSummary ?? "No research summary available."}</div>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <div className="text-sm text-zinc-400">Approval Status</div>
                    <div className="text-zinc-200">{displayDraft.approvalStatus ?? "pending"}</div>
                  </div>
                  <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <div className="text-sm text-zinc-400">Workflow Metadata</div>
                    <div className="text-zinc-200">{displayDraft.provider ?? "OpenRouter"} · {displayDraft.model ?? "gpt-4.1-mini"} · {displayDraft.generationTime ?? 18}s</div>
                  </div>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <label className="mb-2 block text-sm text-zinc-400">Schedule</label>
                  <Input type="datetime-local" value={scheduleTime} onChange={(event) => setScheduleTime(event.target.value)} />
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
