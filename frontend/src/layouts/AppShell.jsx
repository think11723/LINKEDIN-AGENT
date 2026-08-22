import { useState, useMemo } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  CirclePlus,
  NotebookPen,
  FileCheck2,
  CalendarClock,
  Newspaper,
  Settings,
  Menu,
  X,
  LogOut,
  Sparkles,
  Search,
  CheckCircle2,
  ChevronRight,
} from 'lucide-react';

import { cn } from '../utils/cn.js';
import { useAuth } from '../context/AuthContext.jsx';
import { useApi } from '../services/api/backend.js';
import { Button } from '../components/ui/Button.jsx';
import { Input } from '../components/ui/Input.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { useEffect } from 'react';

const navGroups = [
  {
    label: 'Workspace',
    items: [
      { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
      { to: '/create', label: 'Create Post', icon: CirclePlus, accent: true },
      { to: '/drafts', label: 'Drafts', icon: NotebookPen },
      { to: '/approval', label: 'Approval', icon: FileCheck2 },
    ],
  },
  {
    label: 'Publishing',
    items: [
      { to: '/scheduled-posts', label: 'Scheduled', icon: CalendarClock },
      { to: '/published-posts', label: 'Published', icon: Newspaper },
    ],
  },
  {
    label: 'Account',
    items: [
      { to: '/settings', label: 'Settings', icon: Settings },
    ],
  },
];

const titleMap = {
  dashboard: { eyebrow: 'Workspace', title: 'Dashboard' },
  create: { eyebrow: 'Workspace', title: 'Create Post' },
  drafts: { eyebrow: 'Workspace', title: 'Drafts' },
  approval: { eyebrow: 'Workspace', title: 'Approval Queue' },
  'scheduled-posts': { eyebrow: 'Publishing', title: 'Scheduled Posts' },
  'published-posts': { eyebrow: 'Publishing', title: 'Published Posts' },
  profile: { eyebrow: 'Account', title: 'Profile' },
  settings: { eyebrow: 'Account', title: 'Settings' },
};

function getCrumbs(pathname) {
  const segments = pathname.split('/').filter(Boolean);
  const crumbs = [];
  let current = '';
  for (let index = 0; index < segments.length; index += 1) {
    const segment = segments[index];
    current += `/${segment}`;
    const isDraftViewer =
      segment !== 'drafts' && segments[index - 1] === 'drafts' && segments[index + 1] === undefined;
    let label;
    if (isDraftViewer) {
      label = 'Draft Details';
    } else {
      label = titleMap[segment]?.title ?? segment.replace(/-/g, ' ');
    }
    crumbs.push({ href: current, label });
  }
  return crumbs;
}

function getPageTitle(pathname) {
  const segments = pathname.split('/').filter(Boolean);
  const top = segments[0] || '';
  if (segments.length >= 2 && top === 'drafts') {
    return titleMap.drafts;
  }
  return titleMap[top] ?? { eyebrow: '', title: 'Home' };
}

function NavItem({ to, label, Icon, accent, onNavigate }) {
  return (
    <NavLink
      to={to}
      end={to === '/dashboard'}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          'group relative flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-all duration-150',
          isActive
            ? 'bg-gradient-to-r from-brand-500/20 to-brand-500/5 text-white ring-1 ring-brand-400/30'
            : 'text-zinc-400 hover:bg-white/[0.04] hover:text-zinc-100',
        )
      }
    >
      {({ isActive }) => (
        <>
          <span
            className={cn(
              'flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border transition',
              isActive
                ? 'border-brand-400/40 bg-brand-500/20 text-brand-200'
                : 'border-white/10 bg-white/[0.02] text-text-muted group-hover:border-white/20 group-hover:text-zinc-200',
            )}
            aria-hidden
          >
            <Icon className="h-3.5 w-3.5" />
          </span>
          <span className="flex-1">{label}</span>
          {accent ? (
            <span
              className="rounded-md border border-brand-400/30 bg-brand-500/15 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-brand-200"
              aria-hidden
            >
              New
            </span>
          ) : null}
        </>
      )}
    </NavLink>
  );
}

function SidebarContent({ onNavigate, onSignOut }) {
  const { user } = useAuth();
  return (
    <div className="flex h-full flex-col gap-6 p-4">
      <Link
        to="/dashboard"
        onClick={onNavigate}
        className="group flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.03] p-3 transition hover:border-white/20 hover:bg-white/[0.05]"
      >
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-glow-brand">
          <Sparkles className="h-4 w-4" />
        </span>
        <div className="min-w-0">
          <div className="text-sm font-semibold text-white">LinkedIn AI Studio</div>
          <div className="truncate text-xs text-text-muted">Content operations</div>
        </div>
      </Link>

      <nav className="flex flex-1 flex-col gap-5 overflow-y-auto scrollbar-thin pr-1">
        {navGroups.map((group) => (
          <div key={group.label} className="space-y-1.5">
            <div className="px-2 text-[10px] font-semibold uppercase tracking-wider text-text-muted">
              {group.label}
            </div>
            <div className="space-y-0.5">
              {group.items.map((item) => (
                <NavItem
                  key={item.to}
                  to={item.to}
                  label={item.label}
                  Icon={item.icon}
                  accent={item.accent}
                  onNavigate={onNavigate}
                />
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="mt-auto space-y-3">
        {user ? (
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-sm font-semibold text-white">
                {(user.displayName || user.email || 'U').charAt(0).toUpperCase()}
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-zinc-100">
                  {user.displayName || 'Signed in'}
                </div>
                <div className="truncate text-xs text-text-muted">
                  {user.email}
                </div>
              </div>
            </div>
          </div>
        ) : null}
        <Button
          variant="outline"
          size="sm"
          className="w-full"
          onClick={onSignOut}
          leftIcon={<LogOut className="h-3.5 w-3.5" />}
        >
          Sign out
        </Button>
      </div>
    </div>
  );
}

function LinkedInConnectionPill() {
  const api = useApi();
  const [state, setState] = useState({ loading: true, connected: false, personUrn: null });
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await api.getLinkedInStatus();
        if (!cancelled) {
          setState({
            loading: false,
            connected: Boolean(data?.connected),
            personUrn: data?.person_urn || null,
          });
        }
      } catch {
        if (!cancelled) setState({ loading: false, connected: false, personUrn: null });
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [api]);

  if (state.loading) {
    return (
      <div className="hidden items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-text-muted sm:inline-flex">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-zinc-500" />
        LinkedIn
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={() => navigate('/settings')}
      className={
        'hidden items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition sm:inline-flex ' +
        (state.connected
          ? 'border-emerald-400/30 bg-emerald-500/[0.08] text-emerald-200 hover:border-emerald-400/50'
          : 'border-white/10 bg-white/[0.03] text-text-secondary hover:border-white/20 hover:text-zinc-100')
      }
      aria-label={state.connected ? 'LinkedIn connected — open settings' : 'LinkedIn not connected — open settings'}
    >
      <span
        className={
          'h-1.5 w-1.5 rounded-full ' +
          (state.connected ? 'bg-emerald-400' : 'bg-text-muted')
        }
      />
      {state.connected ? (
        <>
          <CheckCircle2 className="h-3.5 w-3.5" /> LinkedIn connected
        </>
      ) : (
        <>Connect LinkedIn</>
      )}
    </button>
  );
}

export function AppShell() {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const location = useLocation();
  const navigate = useNavigate();
  const { signOut } = useAuth();
  const crumbs = useMemo(() => getCrumbs(location.pathname), [location.pathname]);
  const pageMeta = useMemo(() => getPageTitle(location.pathname), [location.pathname]);

  const closeMobile = () => setIsOpen(false);

  function handleSearchSubmit(event) {
    event.preventDefault();
    const term = searchQuery.trim();
    if (!term) return;
    navigate(`/drafts?search=${encodeURIComponent(term)}`);
  }

  async function handleSignOut() {
    await signOut();
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="flex min-h-screen">
        <aside className="hidden w-72 shrink-0 border-r border-white/[0.06] bg-[#0b0b0e]/85 backdrop-blur-xl lg:block">
          <SidebarContent onSignOut={handleSignOut} />
        </aside>

        {isOpen ? (
          <div
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm lg:hidden"
            onClick={closeMobile}
            role="dialog"
            aria-modal="true"
          >
            <aside
              className="h-full w-72 border-r border-white/[0.06] bg-[#0b0b0e] shadow-panel-lg"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex items-center justify-between border-b border-white/[0.06] p-3">
                <span className="text-sm font-semibold text-zinc-100">Menu</span>
                <button
                  type="button"
                  onClick={closeMobile}
                  className="rounded-md p-1.5 text-text-muted hover:bg-white/5"
                  aria-label="Close navigation"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <SidebarContent onNavigate={closeMobile} onSignOut={handleSignOut} />
            </aside>
          </div>
        ) : null}

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 border-b border-white/[0.06] bg-[#0b0b0e]/80 backdrop-blur-xl">
            <div className="flex flex-col gap-2 px-4 py-3 lg:flex-row lg:items-center lg:gap-4 lg:px-6">
              <div className="flex items-center gap-2">
                <Button
                  size="icon-sm"
                  variant="ghost"
                  className="lg:hidden"
                  onClick={() => setIsOpen(true)}
                  aria-label="Open navigation"
                >
                  <Menu className="h-4 w-4" />
                </Button>
                {pageMeta.eyebrow ? (
                  <Badge tone="brand" size="xs" withDot>
                    {pageMeta.eyebrow}
                  </Badge>
                ) : null}
                <h1 className="text-base font-semibold tracking-tight text-white sm:text-lg">
                  {pageMeta.title}
                </h1>
              </div>

              <div className="flex flex-1 items-center justify-end gap-2">
                <form
                  className="relative hidden max-w-md flex-1 sm:block"
                  onSubmit={handleSearchSubmit}
                  role="search"
                >
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted" />
                  <Input
                    className="pl-9"
                    placeholder="Search drafts…"
                    value={searchQuery}
                    onChange={(event) => setSearchQuery(event.target.value)}
                    aria-label="Search drafts"
                    size="sm"
                  />
                </form>
                <LinkedInConnectionPill />
              </div>
            </div>

            {crumbs.length > 1 ? (
              <div className="border-t border-white/[0.04] px-4 py-2 lg:px-6">
                <nav className="flex flex-wrap items-center gap-1.5 text-xs text-text-muted" aria-label="Breadcrumb">
                  <Link to="/dashboard" className="hover:text-zinc-100">
                    Home
                  </Link>
                  {crumbs.slice(1).map((crumb) => (
                    <span key={crumb.href} className="flex items-center gap-1.5">
                      <ChevronRight className="h-3 w-3" />
                      <Link to={crumb.href} className="hover:text-zinc-100">
                        {crumb.label}
                      </Link>
                    </span>
                  ))}
                </nav>
              </div>
            ) : null}
          </header>

          <main className="min-w-0 flex-1 px-4 py-6 md:px-6 lg:px-8">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
