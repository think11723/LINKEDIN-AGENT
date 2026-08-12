"use client";

import { useEffect, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getPublishedDrafts } from "@/lib/api";

export default function PublishedPostsPage() {
  const [drafts, setDrafts] = useState<Awaited<ReturnType<typeof getPublishedDrafts>>>([]);

  useEffect(() => {
    async function loadDrafts() {
      try {
        const data = await getPublishedDrafts();
        setDrafts(data);
      } catch {
        setDrafts([]);
      }
    }

    loadDrafts();
  }, []);

  return (
    <main className="min-h-screen bg-[#09090b] px-4 py-6 text-zinc-50 md:px-8">
      <div className="mx-auto max-w-4xl space-y-6">
        <div>
          <h1 className="text-3xl font-semibold">Published Posts</h1>
          <p className="text-zinc-400">See the content that has already been published to LinkedIn.</p>
        </div>

        <Card className="bg-zinc-950/70">
          <CardHeader>
            <CardTitle>Recent Publishes</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 text-sm text-zinc-300">
              {drafts.length ? (
                drafts.map((draft) => (
                  <div key={draft.draft_id} className="rounded-xl border border-white/10 bg-white/5 p-3">
                    <div className="font-medium text-zinc-100">{draft.title}</div>
                    <div className="mt-1 text-zinc-400">LinkedIn Post ID: {draft.linkedin_post_id ?? "Unavailable"}</div>
                    <div className="mt-2 text-xs text-zinc-500">
                      Published {draft.published_at ? new Date(draft.published_at).toLocaleString() : "recently"}
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-xl border border-dashed border-white/10 bg-white/5 p-4 text-zinc-400">
                  No published posts found yet. Approved content will appear here once it is published.
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
