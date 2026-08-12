"use client";

import { Toaster } from "sonner";

import { QueryProvider } from "@/components/providers/query-provider";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <QueryProvider>
      {children}
      <Toaster position="top-right" richColors theme="dark" />
    </QueryProvider>
  );
}
