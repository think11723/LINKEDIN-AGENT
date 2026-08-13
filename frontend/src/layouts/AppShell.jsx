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
  UserRound,
  Menu,
  X,
  LogOut,
  Sparkles,
  Search,
} from 'lucide-react';

import { cn } from '../utils/cn.js';
import { useAuth } from '../context/AuthContext.jsx';
import { Button } from '../components/ui/Button.jsx';
import { Input } from '../components/ui/Input.jsx';

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/create', label: 'Create Post', icon: CirclePlus },
  { to: '/drafts', label: 'Drafts', icon: NotebookPen },
  { to: '/approval', label: 'Approval', icon: FileCheck2 },
  { to: '/scheduled-posts', label: 'Scheduled Posts', icon: CalendarClock },
  { to: '/published-posts', label: 'Published Posts', icon: Newspaper },
  { to: '/profile', label: 'Profile', icon: UserRound },
  { to: '/settings', label: 'Settings', icon: Settings },
];

const titleMap = {
  dashboard: 'Dashboard',
  create: 'Create Post',
  drafts: 'Drafts',
  'draft-viewer': 'Draft Details',
  approval: 'Approval Queue',
  'scheduled-posts': 'Scheduled Posts',
  'published-posts': 'Published Posts',
  profile: 'Profile',
  settings: 'Settings',
};

function getCrumbs(pathname) {
  // /drafts/:id has no titleMap entry for the trailing id; map it to
  // 'Draft Details' so the breadcrumb stays readable.
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
      label = titleMap[segment] ?? segment.replace(/-/g, ' ');
    }
    crumbs.push({ href: current, label });
  }
  return crumbs;
}

function NavItem({ to, label, Icon, onNavigate }) {
  return (
    <NavLink
      to={to}
      end={to === '/dashboard'}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition',
          isActive
            ? 'bg-violet-500/15 text-violet-100 ring-1 ring-violet-400/40'
            : 'text-zinc-300 hover:bg-white/5 hover:text-white',
        )
      }
    >
      <Icon className="h-4 w-4" />
      <span>{label}</span>
    </NavLink>
  );
}

function SidebarContent({ onNavigate, onSignOut }) {
  const { user } = useAuth();
  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <Link
        to="/dashboard"
        onClick={onNavigate}
        className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/5 p-3"
      >
        <span className="rounded-lg bg-violet-500/20 p-2 text-violet-300">
          <Sparkles className="h-4 w-4" />
        </span>
        <div>
          <div className="text-sm font-semibold text-zinc-50">LinkedIn AI Studio</div>
          <div className="text-xs text-zinc-400">Content operations</div>
        </div>
      </Link>

      <nav className="space-y-1">
        {navItems.map((item) => (
          <NavItem key={item.to} to={item.to} label={item.label} Icon={item.icon} onNavigate={onNavigate} />
        ))}
      </nav>

      <div className="mt-auto space-y-3">
        {user ? (
          <div className="rounded-2xl border border-white/10 bg-white/5 p-3 text-xs text-zinc-300">
            <div className="font-medium text-zinc-100">{user.displayName || user.email || 'Signed in'}</div>
            <div className="mt-1 truncate text-zinc-500">{user.email}</div>
          </div>
        ) : null}
        <Button variant="outline" size="sm" className="w-full" onClick={onSignOut}>
          <LogOut className="h-4 w-4" /> Sign out
        </Button>
      </div>
    </div>
  );
}

export function AppShell() {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const location = useLocation();
  const navigate = useNavigate();
  const { signOut } = useAuth();
  const crumbs = useMemo(() => getCrumbs(location.pathname), [location.pathname]);

  const closeMobile = () => setIsOpen(false);

  function handleSearchSubmit(event) {
    event.preventDefault();
    const term = searchQuery.trim();
    if (!term) return;
    // C4 - route the user to the drafts page with the search term
    // encoded as a query string. DraftsPage reads ?search=... and
    // applies it via api.listDrafts({ search: term }).
    navigate(`/drafts?search=${encodeURIComponent(term)}`);
  }

  async function handleSignOut() {
    await signOut();
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-50">
      <div className="flex min-h-screen">
        <aside className="hidden w-72 shrink-0 border-r border-white/10 bg-zinc-950/80 lg:block">
          <SidebarContent onSignOut={handleSignOut} />
        </aside>

        {isOpen ? (
          <div className="fixed inset-0 z-40 bg-black/60 lg:hidden" onClick={closeMobile}>
            <aside
              className="h-full w-72 border-r border-white/10 bg-zinc-950"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex items-center justify-between border-b border-white/5 p-3">
                <span className="text-sm font-semibold">Menu</span>
                <button
                  type="button"
                  onClick={closeMobile}
                  className="rounded-md p-1.5 text-zinc-400 hover:bg-white/5"
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
          <header className="sticky top-0 z-30 border-b border-white/10 bg-zinc-950/85 backdrop-blur">
            <div className="flex items-center gap-3 px-4 py-3 lg:px-6">
              <Button
                size="icon"
                variant="ghost"
                className="lg:hidden"
                onClick={() => setIsOpen(true)}
                aria-label="Open navigation"
              >
                <Menu className="h-4 w-4" />
              </Button>

              <div className="flex items-center gap-2 text-sm text-zinc-400">
                <span className="hidden md:inline">Workspace</span>
                <span className="text-zinc-600">/</span>
                <span className="text-zinc-100">
                  {(() => {
                    const segments = location.pathname.split('/').filter(Boolean);
                    const top = segments[0] || '';
                    if (segments.length >= 2 && top === 'drafts') return 'Draft Details';
                    return titleMap[top] ?? 'Home';
                  })()}
                </span>
              </div>

              <div className="ml-auto flex flex-1 items-center justify-end gap-2">
                <form
                  className="relative max-w-md flex-1 block"
                  onSubmit={handleSearchSubmit}
                  role="search"
                >
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
                  <Input
                    className="pl-9"
                    placeholder="Quick search"
                    value={searchQuery}
                    onChange={(event) => setSearchQuery(event.target.value)}
                    aria-label="Search drafts"
                  />
                </form>
              </div>
            </div>

            <div className="border-t border-white/5 px-4 py-3 lg:px-6">
              <nav className="flex flex-wrap items-center gap-2 text-sm text-zinc-400">
                <Link to="/dashboard" className="hover:text-zinc-100">
                  Home
                </Link>
                {crumbs.map((crumb, index) => (
                  <div key={crumb.href} className="flex items-center gap-2">
                    <span className="text-zinc-600">/</span>
                    <Link
                      to={crumb.href}
                      className={cn(
                        'hover:text-zinc-100',
                        index === crumbs.length - 1 && 'text-zinc-100',
                      )}
                    >
                      {crumb.label}
                    </Link>
                  </div>
                ))}
              </nav>
            </div>
          </header>

          <main className="min-w-0 flex-1 px-4 py-6 md:px-6 lg:px-8">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}