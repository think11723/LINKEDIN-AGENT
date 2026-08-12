"use client";

import { useEffect, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getScheduledJobs } from "@/lib/api";

export default function ScheduledPostsPage() {
  const [jobs, setJobs] = useState<Awaited<ReturnType<typeof getScheduledJobs>>>([]);

  useEffect(() => {
    async function loadJobs() {
      try {
        const data = await getScheduledJobs();
        setJobs(data);
      } catch {
        setJobs([]);
      }
    }

    loadJobs();
  }, []);

  return (
    <main className="min-h-screen bg-[#09090b] px-4 py-6 text-zinc-50 md:px-8">
      <div className="mx-auto max-w-4xl space-y-6">
        <div>
          <h1 className="text-3xl font-semibold">Scheduled Posts</h1>
          <p className="text-zinc-400">Review queued publishing jobs and upcoming send windows.</p>
        </div>

        <Card className="bg-zinc-950/70">
          <CardHeader>
            <CardTitle>Upcoming Jobs</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 text-sm text-zinc-300">
              {jobs.length ? (
                jobs.map((job) => (
                  <div key={job.job_id} className="rounded-xl border border-white/10 bg-white/5 p-3">
                    <div className="font-medium text-zinc-100">{job.title}</div>
                    <div className="mt-1 text-zinc-400">{new Date(job.scheduled_time).toLocaleString()} · {job.status}</div>
                    <div className="mt-2 text-xs text-zinc-500">Job ID: {job.job_id}</div>
                  </div>
                ))
              ) : (
                <div className="rounded-xl border border-dashed border-white/10 bg-white/5 p-4 text-zinc-400">
                  No scheduled jobs found yet. Generate a draft and route it through approval to create a publish window.
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
