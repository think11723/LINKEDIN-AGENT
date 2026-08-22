import { useState, useEffect } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
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
  Bell,
  ChevronDown,
  CheckCircle2,
  Activity,
  TrendingUp,
  Globe,
  Briefcase,
  Target,
} from 'lucide-react';

import { cn } from '../utils/cn.js';
import { useAuth } from '../context/AuthContext.jsx';
import { useApi } from '../services/api/backend.js';
import { Button } from '../components/ui/Button.jsx';
import { Input } from '../components/ui/Input.jsx';
import { Badge } from '../components/ui/Badge.jsx';
import { Spinner } from '../components/ui/Feedback.jsx';
import { ConfirmDialog } from '../components/ConfirmDialog.jsx';

// ----------------------------------------------------------------
// Sidebar navigation
// ----------------------------------------------------------------

const NAV_PRIMARY = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/create', label: 'Create Post', icon: CirclePlus, accent: true },
  { to: '/drafts', label: 'Drafts', icon: NotebookPen },
  { to: '/approval', label: 'Approval', icon: FileCheck2 },
  { to: '/resume', label: 'Resume Studio', icon: Briefcase },
  { to: '/job-tracker', label: 'Job Tracker', icon: Target },
];

const NAV_PUBLISHING = [
  { to: '/scheduled-posts', label: 'Scheduled', icon: CalendarClock },
  { to: '/published-posts', label: 'Published', icon: Newspaper },
];

const NAV_ACCOUNT = [
  { to: '/settings', label: 'Settings', icon: Settings },
  { to: '/profile', label: 'Profile', icon: UserRound },
];

function NavItem({ to, label, Icon, accent, onNavigate, collapsed }) {
  return (
    <NavLink
      to={to}
      end={to === '/dashboard'}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          'nav-item',
          isActive && 'nav-item-active',
          accent && !isActive && 'text-zinc-300',
          collapsed && 'justify-center px-2'
        )
      }
    >
      <Icon className="h-4 w-4 shrink-0" />
      {!collapsed ? <span className="truncate">{label}</span> : null}
      {!collapsed && accent ? (
        <span className="ml-auto inline-flex h-1.5 w-1.5 rounded-full bg-gradient-brand shadow-glow-brand" />
      ) : null}
    </NavLink>
  );
}

function NavGroup({ label, items, collapsed, onNavigate }) {
  return (
    <div className="space-y-1">
      {!collapsed && label ? (
        <div className="px-3 pt-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-text-muted">
          {label}
        </div>
      ) : null}
      <div className="space-y-1">
        {items.map((item) => (
          <NavItem
            key={item.to}
            to={item.to}
            label={item.label}
            Icon={item.icon}
            accent={item.accent}
            onNavigate={onNavigate}
            collapsed={collapsed}
          />
        ))}
      </div>
    </div>
  );
}

// ----------------------------------------------------------------
// Sidebar
// ----------------------------------------------------------------

function Sidebar({ collapsed, onToggle, onNavigate, onSignOut }) {
  const { user } = useAuth();
  return (
    <aside
      className={cn(
        'flex h-full flex-col border-r border-white/[0.06] bg-[#070B14]/80 backdrop-blur-2xl transition-all duration-300',
        collapsed ? 'w-[72px]' : 'w-[260px]'
      )}
    >
      <div className="flex h-16 items-center px-4">
        <Link
          to="/dashboard"
          onClick={onNavigate}
          className="flex items-center gap-3"
          aria-label="LinkedIn AI Studio"
        >
          <span className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-brand shadow-glow-brand">
            <Sparkles className="h-4 w-4 text-white" />
          </span>
          {!collapsed ? (
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-white">
                LinkedIn AI Studio
              </div>
              <div className="truncate text-[10px] uppercase tracking-[0.14em] text-text-muted">
                AI Powered Content Engine
              </div>
            </div>
          ) : null}
        </Link>
        <button
          type="button"
          onClick={onToggle}
          className="ml-auto hidden h-8 w-8 items-center justify-center rounded-lg text-text-muted transition hover:bg-white/[0.04] hover:text-zinc-100 lg:flex"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <ChevronDown
            className={cn(
              'h-4 w-4 transition-transform',
              collapsed ? 'rotate-90' : '-rotate-90'
            )}
          />
        </button>
      </div>

      <nav className="flex-1 space-y-2 overflow-y-auto px-3 pb-4 scrollbar-thin">
        <NavGroup
          label="Workspace"
          items={NAV_PRIMARY}
          collapsed={collapsed}
          onNavigate={onNavigate}
        />
        <NavGroup
          label="Publishing"
          items={NAV_PUBLISHING}
          collapsed={collapsed}
          onNavigate={onNavigate}
        />
        <NavGroup
          label="Account"
          items={NAV_ACCOUNT}
          collapsed={collapsed}
          onNavigate={onNavigate}
        />
      </nav>

      {user ? (
        <div className="border-t border-white/[0.06] p-3">
          {!collapsed ? (
            <div className="glass-inset mb-2 flex items-center gap-3 rounded-2xl p-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-brand text-sm font-semibold text-white">
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
          ) : null}
          <Button
            variant="ghost"
            size="sm"
            onClick={onSignOut}
            className={cn('w-full', collapsed && 'justify-center px-0')}
            leftIcon={<LogOut className="h-3.5 w-3.5" />}
          >
            {!collapsed ? 'Sign out' : null}
          </Button>
        </div>
      ) : null}
    </aside>
  );
}

// ----------------------------------------------------------------
// Topbar
// ----------------------------------------------------------------

function Topbar({ onOpenMobileNav }) {
  const api = useApi();
  const navigate = useNavigate();
  const location = useLocation();
  const [linkedin, setLinkedin] = useState({ loading: true, connected: false });
  const [searchValue, setSearchValue] = useState('');

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await api.getLinkedInStatus();
        if (!cancelled) {
          setLinkedin({ loading: false, connected: Boolean(data?.connected) });
        }
      } catch {
        if (!cancelled) setLinkedin({ loading: false, connected: false });
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [api]);

  function handleSearchSubmit(e) {
    e.preventDefault();
    const term = searchValue.trim();
    if (!term) return;
    navigate(`/drafts?search=${encodeURIComponent(term)}`);
  }

  return (
    <header className="sticky top-0 z-30 border-b border-white/[0.06] bg-[#070B14]/80 backdrop-blur-2xl">
      <div className="flex h-16 items-center gap-3 px-4 lg:px-6">
        <Button
          variant="ghost"
          size="icon-sm"
          className="lg:hidden"
          onClick={onOpenMobileNav}
          aria-label="Open navigation"
        >
          <Menu className="h-4 w-4" />
        </Button>

        <form
          onSubmit={handleSearchSubmit}
          role="search"
          className="relative ml-1 hidden max-w-md flex-1 sm:block"
        >
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-text-muted" />
          <Input
            className="pl-9 h-9"
            placeholder="Search drafts…"
            value={searchValue}
            onChange={(e) => setSearchValue(e.target.value)}
            aria-label="Search drafts"
          />
          <kbd className="pointer-events-none absolute right-2 top-1/2 hidden -translate-y-1/2 rounded-md border border-white/[0.08] bg-white/[0.04] px-1.5 py-0.5 text-[10px] font-mono text-text-muted sm:inline">
            /
          </kbd>
        </form>

        <div className="ml-auto flex items-center gap-2">
          <Badge
            tone={linkedin.connected ? 'success' : 'neutral'}
            size="sm"
            withDot
            className="hidden md:inline-flex"
          >
            {linkedin.loading ? (
              <span className="inline-flex items-center gap-1.5">
                <Spinner size="xs" /> LinkedIn
              </span>
            ) : linkedin.connected ? (
              <>
                <CheckCircle2 className="h-3 w-3" /> LinkedIn
              </>
            ) : (
              <>LinkedIn</>
            )}
          </Badge>
          <Badge tone="info" size="sm" withDot className="hidden md:inline-flex">
            <Sparkles className="h-3 w-3" /> AI
          </Badge>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Notifications"
            className="hidden md:inline-flex"
          >
            <Bell className="h-4 w-4" />
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => navigate('/create')}
            leftIcon={<Sparkles className="h-3.5 w-3.5" />}
            className="hidden sm:inline-flex"
          >
            New Post
          </Button>
        </div>
      </div>
    </header>
  );
}

// ----------------------------------------------------------------
// AppShell
// ----------------------------------------------------------------

export function AppShell() {
  const { signOut } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const closeMobile = () => setMobileOpen(false);

  // Lock body scroll while the mobile drawer is open.
  useEffect(() => {
    document.body.style.overflow = mobileOpen ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [mobileOpen]);

  // Close the drawer on route change.
  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  async function handleSignOut() {
    await signOut();
  }

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background text-foreground">
      {/* Desktop sidebar */}
      <div className="hidden lg:block">
        <Sidebar
          collapsed={collapsed}
          onToggle={() => setCollapsed((c) => !c)}
          onNavigate={closeMobile}
          onSignOut={() => setConfirmOpen(true)}
        />
      </div>

      {/* Mobile sidebar (drawer) */}
      <AnimatePresence>
        {mobileOpen ? (
          <>
            <motion.div
              key="backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18 }}
              className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm lg:hidden"
              onClick={closeMobile}
              role="presentation"
            />
            <motion.aside
              key="drawer"
              initial={{ x: -300, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: -300, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 300, damping: 30 }}
              className="fixed inset-y-0 left-0 z-50 w-[280px] lg:hidden"
              role="dialog"
              aria-modal="true"
              aria-label="Navigation"
            >
              <Sidebar
                collapsed={false}
                onToggle={() => {}}
                onNavigate={closeMobile}
                onSignOut={() => setConfirmOpen(true)}
              />
              <button
                type="button"
                onClick={closeMobile}
                className="absolute right-3 top-3 inline-flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.04] text-text-secondary"
                aria-label="Close navigation"
              >
                <X className="h-4 w-4" />
              </button>
            </motion.aside>
          </>
        ) : null}
      </AnimatePresence>

      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onOpenMobileNav={() => setMobileOpen(true)} />
        <main className="min-w-0 flex-1 overflow-y-auto">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
              className="min-h-full"
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        title="Sign out?"
        description="You will be returned to the login screen. Any unsaved drafts remain in the database."
        confirmLabel="Sign out"
        danger
        confirming={false}
        onConfirm={async () => {
          setConfirmOpen(false);
          await handleSignOut();
          navigate('/login');
        }}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}
