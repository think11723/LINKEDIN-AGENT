"use client";

import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";

const steps = [
  "Research",
  "Planning",
  "Writing",
  "Reviewing",
  "Approval",
  "Publishing",
];

export function WorkflowProgress({ activeStep = 0 }: { activeStep?: number }) {
  return (
    <div className="rounded-2xl border border-zinc-200/70 bg-white/70 p-5 dark:border-zinc-800 dark:bg-zinc-950/60">
      <div className="mb-4 flex items-center gap-2 text-sm font-medium text-zinc-900 dark:text-zinc-100">
        <Sparkles className="h-4 w-4 text-violet-500" />
        Workflow progress
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {steps.map((step, index) => {
          const isActive = index === activeStep;
          const isDone = index < activeStep;

          return (
            <motion.div
              key={step}
              className={`rounded-xl border px-3 py-3 text-sm transition ${
                isActive
                  ? "border-violet-500 bg-violet-500/10 text-violet-700 dark:text-violet-200"
                  : isDone
                    ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-200"
                    : "border-zinc-200 bg-zinc-50 text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400"
              }`}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, delay: index * 0.04 }}
            >
              <div className="flex items-center justify-between">
                <span>{step}</span>
                {isActive ? <span className="h-2 w-2 rounded-full bg-violet-500" /> : null}
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
