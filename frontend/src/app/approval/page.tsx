"use client";

import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { approveDraft, getApprovalDraft, getApprovalQueue, rejectDraft } from "@/lib/api";

export default function ApprovalPage() {
  const [queue, setQueue] = useState<Awaited<ReturnType<typeof getApprovalQueue>>>([]);
  const [token, setToken] = useState("");
  const [draft, setDraft] = useState<Awaited<ReturnType<typeof getApprovalDraft>> | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    async function loadQueue() {
      try {
        const items = await getApprovalQueue();
        setQueue(items);
        if (items[0]?.token) {
          setToken(items[0].token);
        }
      } finally {
        setIsLoading(false);
      }
    }

    loadQueue();
  }, []);

  useEffect(() => {
    if (!token) {
      setDraft(null);
      return;
    }

    async function loadDraft() {
      try {
        const nextDraft = await getApprovalDraft(token);
        setDraft(nextDraft);
        setMessage(null);
      } catch (err) {
        setMessage(err instanceof Error ? err.message : "Unable to load draft");
      }
    }

    loadDraft();
  }, [token]);

  const tokenLink = useMemo(() => `app.domain.com/approve/${token || "{token}"}`, [token]);

  async function handleApprove() {
    if (!token) return;
    setIsSubmitting(true);
    try {
      const result = await approveDraft(token);
      setMessage(result.message);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Approval failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleReject() {
    if (!token) return;
    setIsSubmitting(true);
    try {
      const result = await rejectDraft(token);
      setMessage(result.message);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Reject request failed");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#09090b] px-4 py-6 text-zinc-50 md:px-8">
      <div className="mx-auto max-w-4xl space-y-6">
        <div>
          <h1 className="text-3xl font-semibold">Approval</h1>
          <p className="text-zinc-400">Review approval tokens and finalize publishing decisions.</p>
        </div>

        <Card className="bg-zinc-950/70">
          <CardHeader>
            <CardTitle>Approval Token Review</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="mb-3 flex items-center gap-2">
                <Badge>Token</Badge>
                <span className="text-sm text-zinc-400">{tokenLink}</span>
              </div>
              <label className="mb-2 block text-sm text-zinc-300">Approval token</label>
              <input
                className="w-full rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-zinc-100"
                value={token}
                onChange={(event) => setToken(event.target.value)}
                placeholder="Paste the approval token"
              />
            </div>

            <div className="flex flex-wrap gap-2">
              <Button onClick={handleApprove} disabled={!token || isSubmitting}>
                {isSubmitting ? "Working…" : "Approve"}
              </Button>
              <Button variant="outline" onClick={handleReject} disabled={!token || isSubmitting}>
                Reject
              </Button>
            </div>

            {message ? <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-sm text-zinc-200">{message}</div> : null}

            {draft ? (
              <div className="space-y-3 rounded-2xl border border-white/10 bg-white/5 p-4">
                <div className="text-lg font-semibold">{draft.title}</div>
                <div className="whitespace-pre-line text-zinc-200">{draft.content}</div>
                <div className="flex flex-wrap gap-2">
                  {draft.hashtags.map((tag) => (
                    <Badge key={tag}>{tag}</Badge>
                  ))}
                </div>
                <div className="text-sm text-zinc-400">Review score: {draft.review_score}/10</div>
                <div className="text-sm text-zinc-400">Status: {draft.status}</div>
              </div>
            ) : !isLoading ? (
              <div className="rounded-2xl border border-dashed border-white/10 p-4 text-sm text-zinc-400">
                No draft is currently attached to that token.
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card className="bg-zinc-950/70">
          <CardHeader>
            <CardTitle>Pending Queue</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {queue.length ? (
                queue.map((item) => (
                  <button
                    key={item.draft_id}
                    className="w-full rounded-xl border border-white/10 bg-white/5 p-3 text-left"
                    onClick={() => setToken(item.token)}
                  >
                    <div className="font-medium text-zinc-100">{item.title}</div>
                    <div className="text-sm text-zinc-400">{item.topic}</div>
                    <div className="mt-1 text-xs text-zinc-500">{item.token}</div>
                  </button>
                ))
              ) : (
                <div className="text-sm text-zinc-400">No pending approval items found.</div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
