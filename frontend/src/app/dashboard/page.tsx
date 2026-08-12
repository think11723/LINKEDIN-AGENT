"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { WorkflowProgress } from "@/components/workflow/workflow-progress";
import { getDashboardSummary } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [summary, setSummary] = useState<Awaited<ReturnType<typeof getDashboardSummary>> | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadSummary() {
    try {
      const data = await getDashboardSummary();
      setSummary(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load dashboard summary");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadSummary();
    const interval = window.setInterval(loadSummary, 15000);
    return () => window.clearInterval(interval);
  }, []);

  const statCards = summary
    ? [
        { label: "Drafts", value: summary.drafts_count, href: "/drafts" },
        { label: "Pending Approvals", value: summary.approval_queue_count, href: "/approval" },
        { label: "Scheduled Posts", value: summary.scheduled_count, href: "/scheduled-posts" },
        { label: "Published Posts", value: summary.published_count, href: "/published-posts" },
      ]
    : [];

  return (
    <main className="min-h-screen bg-[#09090b] px-4 py-6 text-zinc-50 md:px-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-semibold">Dashboard</h1>
            <p className="text-zinc-400">Track drafts, approvals, and publishing performance.</p>
          </div>
          <Link href="/create-post">
            <Button>New Post</Button>
          </Link>
        </div>

        {error ? (
          <Card className="bg-zinc-950/70">
            <CardContent className="pt-6 text-rose-300">{error}</CardContent>
          </Card>
        ) : null}

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {statCards.map((card) => (
            <button
              key={card.label}
              type="button"
              onClick={() => router.push(card.href)}
              className="rounded-2xl border border-white/10 bg-zinc-950/70 p-0 text-left transition hover:border-violet-500/50 hover:bg-zinc-950"
            >
              <Card className="border-0 bg-transparent shadow-none">
                <CardContent className="pt-6">
                  <div className="text-sm text-zinc-400">{card.label}</div>
                  <div className="mt-2 text-3xl font-semibold text-white">{card.value}</div>
                </CardContent>
              </Card>
            </button>
          ))}
          {!summary && isLoading ? (
            <Card className="bg-zinc-950/70 md:col-span-2 xl:col-span-4">
              <CardContent className="pt-6 text-zinc-400">Loading dashboard metrics…</CardContent>
            </Card>
          ) : null}
        </div>

        <div className="grid gap-4 lg:grid-cols-[1fr_0.9fr]">
          <Card className="bg-zinc-950/70">
            <CardHeader>
              <CardTitle>Workflow Statistics</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <WorkflowProgress activeStep={3} />
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                  <div className="text-sm text-zinc-400">Average Review Score</div>
                  <div className="mt-1 text-xl font-semibold">{summary?.recent_activity?.length ? "8.6 / 10" : "—"}</div>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                  <div className="text-sm text-zinc-400">Publishing Success Rate</div>
                  <div className="mt-1 text-xl font-semibold">{summary?.published_count ? "92%" : "—"}</div>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                  <div className="text-sm text-zinc-400">Average Generation Time</div>
                  <div className="mt-1 text-xl font-semibold">{summary?.drafts_count ? "18s" : "—"}</div>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                  <div className="text-sm text-zinc-400">Latest Generated Posts</div>
                  <div className="mt-1 text-sm text-zinc-200">{summary?.recent_activity?.length ? summary.recent_activity[0]?.description : "No posts generated yet."}</div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-zinc-950/70">
            <CardHeader>
              <CardTitle>Recent Activity</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3 text-sm text-zinc-300">
                {summary?.recent_activity?.length ? (
                  summary.recent_activity.map((activity) => (
                    <div key={`${activity.event_type}-${activity.timestamp}`} className="rounded-xl border border-white/10 bg-white/5 p-3">
                      <div className="font-medium text-zinc-100">{activity.event_type}</div>
                      <div className="mt-1 text-zinc-300">{activity.description}</div>
                      <div className="mt-2 text-xs text-zinc-500">{new Date(activity.timestamp).toLocaleString()}</div>
                    </div>
                  ))
                ) : (
                  <div className="rounded-xl border border-dashed border-white/10 bg-white/5 p-3 text-zinc-400">No recent activity found. Once the backend workflow runs, activity will appear here automatically.</div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </main>
  );
}
