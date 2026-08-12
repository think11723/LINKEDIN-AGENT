import Link from "next/link";
import { ArrowRight, Sparkles, Wand2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function Home() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(129,140,248,0.22),_transparent_44%),linear-gradient(180deg,#09090b_0%,#111827_100%)] px-6 py-8 text-zinc-50 md:px-10">
      <div className="mx-auto flex max-w-6xl flex-col gap-8">
        <header className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/5 px-4 py-3 backdrop-blur">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-violet-500/20 p-2 text-violet-300">
              <Sparkles className="h-4 w-4" />
            </div>
            <div>
              <div className="text-sm font-semibold">LinkedIn AI Studio</div>
              <div className="text-xs text-zinc-400">Modern content workflow</div>
            </div>
          </div>
          <Link href="/dashboard">
            <Button>Open Dashboard</Button>
          </Link>
        </header>

        <section className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-[28px] border border-white/10 bg-zinc-950/60 p-8 shadow-[0_0_0_1px_rgba(255,255,255,0.02),0_20px_80px_rgba(0,0,0,0.45)]">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-violet-500/40 bg-violet-500/10 px-3 py-1 text-xs text-violet-200">
              <Sparkles className="h-3.5 w-3.5" />
              AI-powered publishing workflow
            </div>
            <h1 className="max-w-2xl text-5xl font-semibold tracking-tight text-white md:text-6xl">
              Turn ideas into polished LinkedIn content in one workflow.
            </h1>
            <p className="mt-5 max-w-2xl text-lg leading-8 text-zinc-300">
              Research, plan, draft, review, approve, and publish from a premium interface built around the existing backend workflow.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/create-post">
                <Button size="lg">
                  Create Post
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </Link>
              <Link href="/dashboard">
                <Button variant="outline" size="lg">
                  View Dashboard
                </Button>
              </Link>
            </div>
          </div>

          <Card className="border-white/10 bg-zinc-950/70">
            <CardContent className="space-y-4 pt-6">
              <div className="flex items-center gap-3 rounded-2xl bg-white/5 p-4">
                <div className="rounded-xl bg-emerald-500/15 p-2 text-emerald-300">
                  <Wand2 className="h-4 w-4" />
                </div>
                <div>
                  <div className="font-medium">Live workflow stream</div>
                  <div className="text-sm text-zinc-400">Research → Plan → Write → Review → Approve</div>
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                {[
                  "Dashboard",
                  "Create Post",
                  "Draft Viewer",
                  "Approval Page",
                  "Scheduled Posts",
                  "Published Posts",
                ].map((item) => (
                  <div key={item} className="rounded-xl border border-white/10 bg-white/5 px-3 py-3 text-sm text-zinc-200">
                    {item}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </section>
      </div>
    </main>
  );
}
