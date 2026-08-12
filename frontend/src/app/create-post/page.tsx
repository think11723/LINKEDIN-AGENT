"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { WorkflowProgress } from "@/components/workflow/workflow-progress";
import { generateContent } from "@/lib/api";
import { useAppStore } from "@/store/use-app-store";
import { useDraftLibraryStore } from "@/store/use-draft-library";

const initialState = {
  topic: "",
  writingStyle: "professional",
  tone: "confident",
  audience: "founders",
  length: "medium",
  imagePath: "",
};

export default function CreatePostPage() {
  const [form, setForm] = useState(initialState);
  const [isGenerating, setIsGenerating] = useState(false);
  const [result, setResult] = useState<any>(null);
  const setDraft = useAppStore((state) => state.setDraft);
  const addDraft = useDraftLibraryStore((state) => state.addDraft);

  async function handleGenerate() {
    if (!form.topic.trim()) {
      toast.error("Please enter a topic");
      return;
    }

    setIsGenerating(true);
    try {
      const response = await generateContent({ topic: form.topic, image_path: form.imagePath || undefined });
      setResult(response);
      const nextDraft = {
        id: `draft-${Date.now()}`,
        title: response.final_post?.title ?? "",
        topic: response.topic,
        content: response.final_post?.content ?? "",
        hashtags: response.final_post?.hashtags ?? [],
        reviewScore: response.review_scores ? Number(response.review_scores.overall ?? 0) : undefined,
        reviewFeedback: response.review_feedback ?? undefined,
        researchSummary: response.metadata?.research_package?.summary ?? undefined,
        status: "draft",
        workflowStatus: "completed",
        approvalStatus: "pending",
        provider: "openrouter",
        model: "gpt-4.1-mini",
        generationTime: 18,
      };
      setDraft({
        title: nextDraft.title,
        content: nextDraft.content,
        hashtags: nextDraft.hashtags,
        reviewScore: nextDraft.reviewScore,
        reviewFeedback: nextDraft.reviewFeedback,
        researchSummary: nextDraft.researchSummary,
      });
      addDraft(nextDraft);
      toast.success("Content generated successfully");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Generation failed");
    } finally {
      setIsGenerating(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#09090b] px-4 py-6 text-zinc-50 md:px-8">
      <div className="mx-auto grid max-w-6xl gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <Card className="bg-zinc-950/70">
          <CardHeader>
            <CardTitle>Create Post</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="mb-2 block text-sm">Topic</label>
              <Input value={form.topic} onChange={(e) => setForm({ ...form, topic: e.target.value })} placeholder="AI workflows for LinkedIn creators" />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="mb-2 block text-sm">Writing Style</label>
                <Input value={form.writingStyle} onChange={(e) => setForm({ ...form, writingStyle: e.target.value })} />
              </div>
              <div>
                <label className="mb-2 block text-sm">Tone</label>
                <Input value={form.tone} onChange={(e) => setForm({ ...form, tone: e.target.value })} />
              </div>
              <div>
                <label className="mb-2 block text-sm">Audience</label>
                <Input value={form.audience} onChange={(e) => setForm({ ...form, audience: e.target.value })} />
              </div>
              <div>
                <label className="mb-2 block text-sm">Length</label>
                <Input value={form.length} onChange={(e) => setForm({ ...form, length: e.target.value })} />
              </div>
            </div>
            <div>
              <label className="mb-2 block text-sm">Optional image upload</label>
              <Input type="file" onChange={(e) => setForm({ ...form, imagePath: e.target.value })} />
            </div>
            <Button onClick={handleGenerate} className="w-full" disabled={isGenerating}>
              {isGenerating ? "Generating…" : "Generate"}
            </Button>
          </CardContent>
        </Card>

        <Card className="bg-zinc-950/70">
          <CardHeader>
            <CardTitle>Workflow output</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {isGenerating ? <WorkflowProgress activeStep={2} /> : <WorkflowProgress activeStep={0} />}
            {result ? (
              <div className="space-y-3 rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="text-sm text-zinc-400">Title</div>
                <div className="text-xl font-semibold">{result.final_post?.title}</div>
                <div className="text-sm text-zinc-400">Content</div>
                <div className="whitespace-pre-line text-zinc-200">{result.final_post?.content}</div>
                <div className="text-sm text-zinc-400">Hashtags</div>
                <div className="text-zinc-200">{result.final_post?.hashtags?.join(" ")}</div>
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-white/10 p-6 text-sm text-zinc-400">
                Generation output will appear here after the backend returns a result.
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
