import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { GitPullRequest, ShieldCheck, Rocket, AlertTriangle, Settings, Activity, Command } from 'lucide-react';
import clsx from 'clsx';
import { useWebSocket } from '../hooks/useWebSocket.js';
import { ToastProvider, useToast } from './Toast.jsx';
import CommandPalette from './CommandPalette.jsx';

const NAV = [
  { to: '/pipelines',   label: 'Pipelines',   icon: GitPullRequest, shortcut: 'P' },
  { to: '/approvals',   label: 'Approvals',   icon: ShieldCheck,    shortcut: 'A' },
  { to: '/deployments', label: 'Deployments', icon: Rocket,         shortcut: 'D' },
  { to: '/incidents',   label: 'Incidents',   icon: AlertTriangle,  shortcut: 'I' },
  { to: '/settings',    label: 'Settings',    icon: Settings,       shortcut: ',' },
];

export default function AppShell() {
  return (
    <ToastProvider>
      <ShellInner />
    </ToastProvider>
  );
}

function ShellInner() {
  const { status, lastEvent, eventCount } = useWebSocket();
  const location = useLocation();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [gPressed, setGPressed] = useState(false);

  // Toast on important live events
  useEffect(() => {
    if (!lastEvent) return;
    const { channel, type, payload } = lastEvent;

    if (channel === 'incidents' && type === 'incident.fired') {
      toast({
        title: 'Incident fired',
        message: `${payload?.severity?.toUpperCase()} · ${payload?.summary?.slice(0, 80)}`,
        variant: 'danger',
        duration: 8000,
      });
    } else if (channel === 'incidents' && type === 'incident.root_cause_attached') {
      toast({
        title: 'AI root cause attached',
        message: `${payload?.ai_confidence} confidence`,
        variant: 'info',
      });
    } else if (channel === 'deployments' && type === 'deployment.transitioned' && payload?.to_state === 'promoted') {
      toast({
        title: 'Deployment promoted',
        message: payload?.deployment_id?.slice(0, 40),
        variant: 'success',
      });
    } else if (channel === 'deployments' && type === 'deployment.rolled_back') {
      toast({
        title: 'Deployment rolled back',
        message: payload?.reason?.slice(0, 80),
        variant: 'warning',
      });
    } else if (channel === 'pipelines' && type === 'pipeline.completed') {
      const isBlock = payload?.decision === 'BLOCK';
      toast({
        title: `Pipeline ${payload?.decision?.toLowerCase()}`,
        message: payload?.pipeline_id?.slice(0, 40),
        variant: isBlock ? 'warning' : 'success',
        duration: 3500,
      });
    } else if (channel === 'approvals' && type === 'approval.created') {
      toast({
        title: 'Approval requested',
        message: `${payload?.risk_level?.toUpperCase()} · ${payload?.reason?.slice(0, 80)}`,
        variant: 'warning',
      });
    }
  }, [lastEvent, toast]);

  // Keyboard shortcuts: cmd/ctrl+K for palette, g+<letter> for nav
  useEffect(() => {
    const handler = (e) => {
      const target = e.target;
      const isTyping = target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable;

      // cmd/ctrl + K
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPaletteOpen(o => !o);
        return;
      }

      if (isTyping) return;

      // g+<letter> sequence
      if (e.key === 'g' && !gPressed) {
        setGPressed(true);
        setTimeout(() => setGPressed(false), 1000);
        return;
      }

      if (gPressed) {
        setGPressed(false);
        const match = NAV.find(n => n.shortcut.toLowerCase() === e.key.toLowerCase());
        if (match) {
          e.preventDefault();
          navigate(match.to);
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [gPressed, navigate]);

  return (
    <div className="h-screen w-screen flex bg-slate-950 text-slate-100">
      <aside className="w-60 border-r border-slate-800 flex flex-col">
        <Link to="/" className="px-5 py-5 border-b border-slate-800 flex items-center gap-2">
          <Activity className="w-6 h-6 text-emerald-400" />
          <div>
            <div className="font-bold text-lg tracking-tight">AgentOps</div>
            <div className="text-[10px] text-slate-500 uppercase tracking-widest">multi-agent ci/cd</div>
          </div>
        </Link>

        <nav className="flex-1 py-4 px-2 space-y-1">
          {NAV.map(({ to, label, icon: Icon, shortcut }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => clsx(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors group',
                isActive
                  ? 'bg-slate-800 text-emerald-300'
                  : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200'
              )}
            >
              <Icon className="w-4 h-4" />
              <span className="flex-1">{label}</span>
              <kbd className="text-[9px] font-mono text-slate-600 group-hover:text-slate-500">g {shortcut}</kbd>
            </NavLink>
          ))}
        </nav>

        <button
          onClick={() => setPaletteOpen(true)}
          className="mx-2 mb-2 flex items-center gap-2 px-3 py-2 rounded-md text-xs text-slate-500 hover:text-slate-300 hover:bg-slate-900 border border-slate-800 transition-colors"
        >
          <Command className="w-3.5 h-3.5" />
          <span>Quick actions</span>
          <kbd className="ml-auto text-[9px] font-mono text-slate-600">⌘K</kbd>
        </button>

        <div className="border-t border-slate-800 p-3 text-[11px] text-slate-500">
          v0.5.0 · dev
        </div>
      </aside>

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-14 border-b border-slate-800 flex items-center justify-between px-6 bg-slate-900/50">
          <h1 className="text-sm font-medium text-slate-300 capitalize">
            {location.pathname.split('/')[1] || 'pipelines'}
          </h1>

          <div className="flex items-center gap-4">
            {lastEvent && (
              <div className="text-[11px] text-slate-500 font-mono">
                last event: {lastEvent.channel}.{lastEvent.type} · {eventCount} total
              </div>
            )}
            <ConnectionPill status={status} />
          </div>
        </header>

        <main className="flex-1 overflow-auto p-6">
          <Outlet context={{ lastEvent, status }} />
        </main>
      </div>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}

function ConnectionPill({ status }) {
  const config = {
    connected:    { color: 'bg-emerald-500', text: 'text-emerald-300', label: 'live' },
    connecting:   { color: 'bg-amber-500',   text: 'text-amber-300',   label: 'connecting' },
    disconnected: { color: 'bg-red-500',     text: 'text-red-300',     label: 'offline' },
  }[status] || { color: 'bg-slate-500', text: 'text-slate-300', label: status };

  return (
    <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-slate-800/60 border border-slate-700">
      <span className={clsx('w-2 h-2 rounded-full', config.color, status === 'connected' && 'animate-pulse')} />
      <span className={clsx('text-[11px] font-mono', config.text)}>{config.label}</span>
    </div>
  );
}