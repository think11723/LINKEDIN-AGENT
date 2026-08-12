"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart3,
  CirclePlus,
  FileCheck2,
  FolderKanban,
  LayoutDashboard,
  Menu,
  NotebookPen,
  Settings,
  UserRound,
  X,
  CalendarClock,
  Newspaper,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { GlobalSearch } from "@/components/search/global-search";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/create-post", label: "Create Post", icon: CirclePlus },
  { href: "/drafts", label: "Drafts", icon: NotebookPen },
  { href: "/approval", label: "Approval Queue", icon: FileCheck2 },
  { href: "/scheduled-posts", label: "Scheduled Posts", icon: CalendarClock },
  { href: "/published-posts", label: "Published Posts", icon: Newspaper },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
  { href: "/profile", label: "Profile", icon: UserRound },
];

const pageTitles: Record<string, string> = {
  dashboard: "Dashboard",
  "create-post": "Create Post",
  drafts: "Drafts",
  "draft-viewer": "Draft Details",
  approval: "Approval Queue",
  "scheduled-posts": "Scheduled Posts",
  "published-posts": "Published Posts",
  analytics: "Analytics",
  settings: "Settings",
  profile: "Profile",
};

function getBreadcrumbs(pathname: string) {
  const segments = pathname.split("/").filter(Boolean);
  const crumbs = [] as Array<{ label: string; href: string }>;

  if (pathname === "/draft-viewer") {
    return [
      { label: "Dashboard", href: "/dashboard" },
      { label: "Drafts", href: "/drafts" },
      { label: "Draft Details", href: "/draft-viewer" },
    ];
  }

  let currentPath = "";
  for (const segment of segments) {
    currentPath += `/${segment}`;
    const label = pageTitles[segment] ?? segment.replace(/-/g, " ");
    crumbs.push({
      label: label.charAt(0).toUpperCase() + label.slice(1),
      href: currentPath,
    });
  }

  return crumbs;
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col gap-3 p-4">
      <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
        <div className="text-xs uppercase tracking-[0.24em] text-zinc-400">LinkedIn AI Studio</div>
        <div className="mt-1 text-sm text-zinc-200">Production content ops</div>
      </div>

      <nav className="space-y-1">
        {navItems.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href === "/drafts" && pathname.startsWith("/draft")) ||
            (item.href === "/scheduled-posts" && pathname.startsWith("/schedule")) ||
            (item.href === "/published-posts" && pathname.startsWith("/published"));
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition",
                isActive
                  ? "bg-violet-500/15 text-violet-100 ring-1 ring-violet-400/50"
                  : "text-zinc-300 hover:bg-white/5 hover:text-white",
              )}
            >
              <Icon className="h-4 w-4" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto rounded-2xl border border-white/10 bg-white/5 p-3 text-sm text-zinc-300">
        Workspace status: operational
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);
  const breadcrumbs = useMemo(() => getBreadcrumbs(pathname), [pathname]);

  return (
    <div className="min-h-screen bg-[#09090b] text-zinc-50">
      <div className="flex min-h-screen">
        <aside className="hidden w-72 border-r border-white/10 bg-zinc-950/80 lg:block">
          <SidebarContent />
        </aside>

        <AnimatePresence>
          {isOpen ? (
            <motion.div
              className="fixed inset-0 z-40 bg-black/50 lg:hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsOpen(false)}
            >
              <motion.aside
                initial={{ x: -320 }}
                animate={{ x: 0 }}
                exit={{ x: -320 }}
                transition={{ type: "spring", stiffness: 280, damping: 28 }}
                className="h-full w-72 border-r border-white/10 bg-zinc-950/95"
                onClick={(e) => e.stopPropagation()}
              >
                <SidebarContent onNavigate={() => setIsOpen(false)} />
              </motion.aside>
            </motion.div>
          ) : null}
        </AnimatePresence>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 border-b border-white/10 bg-[#09090b]/85 backdrop-blur">
            <div className="flex items-center gap-3 px-4 py-3 lg:px-6">
              <Button
                variant="ghost"
                size="icon"
                className="lg:hidden"
                onClick={() => setIsOpen(true)}
                aria-label="Open navigation"
              >
                <Menu className="h-4 w-4" />
              </Button>

              <div className="flex items-center gap-2 text-sm text-zinc-400">
                <span className="hidden md:inline">Workspace</span>
                <span className="text-zinc-300">/</span>
                <span className="text-zinc-100">{pageTitles[pathname.replace("/", "").split("/")[0]] ?? "Home"}</span>
              </div>

              <div className="ml-auto hidden flex-1 justify-end lg:flex">
                <GlobalSearch />
              </div>
            </div>

            <div className="border-t border-white/10 px-4 py-3 lg:px-6">
              <nav className="flex flex-wrap items-center gap-2 text-sm text-zinc-400">
                <Link href="/dashboard" className="hover:text-zinc-100">
                  Home
                </Link>
                {breadcrumbs.map((crumb, index) => (
                  <div key={crumb.href} className="flex items-center gap-2">
                    <span>/</span>
                    <Link
                      href={crumb.href}
                      className={cn(
                        "hover:text-zinc-100",
                        index === breadcrumbs.length - 1 && "text-zinc-100",
                      )}
                    >
                      {crumb.label}
                    </Link>
                  </div>
                ))}
              </nav>
            </div>
          </header>

          <main className="min-w-0 flex-1 px-4 py-6 md:px-6 lg:px-8">{children}</main>
        </div>
      </div>
    </div>
  );
}
