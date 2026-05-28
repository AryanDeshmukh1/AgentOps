import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { GitPullRequest, ShieldCheck, Rocket, AlertTriangle, Settings, Activity } from 'lucide-react';
import clsx from 'clsx';
import { useWebSocket } from '../hooks/useWebSocket.js';

const NAV = [
  { to: '/pipelines',   label: 'Pipelines',   icon: GitPullRequest },
  { to: '/approvals',   label: 'Approvals',   icon: ShieldCheck },
  { to: '/deployments', label: 'Deployments', icon: Rocket },
  { to: '/incidents',   label: 'Incidents',   icon: AlertTriangle },
  { to: '/settings',    label: 'Settings',    icon: Settings },
];

export default function AppShell() {
  const { status, lastEvent, eventCount } = useWebSocket();
  const location = useLocation();

  return (
    <div className="h-screen w-screen flex bg-slate-950 text-slate-100">
      {/* Sidebar */}
      <aside className="w-60 border-r border-slate-800 flex flex-col">
        <Link to="/" className="px-5 py-5 border-b border-slate-800 flex items-center gap-2">
          <Activity className="w-6 h-6 text-emerald-400" />
          <div>
            <div className="font-bold text-lg tracking-tight">AgentOps</div>
            <div className="text-[10px] text-slate-500 uppercase tracking-widest">multi-agent ci/cd</div>
          </div>
        </Link>

        <nav className="flex-1 py-4 px-2 space-y-1">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => clsx(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
                isActive
                  ? 'bg-slate-800 text-emerald-300'
                  : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200'
              )}
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-slate-800 p-3 text-[11px] text-slate-500">
          v0.5.0 · dev
        </div>
      </aside>

      {/* Main column */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="h-14 border-b border-slate-800 flex items-center justify-between px-6 bg-slate-900/50">
          <h1 className="text-sm font-medium text-slate-300 capitalize">
            {location.pathname.replace('/', '') || 'pipelines'}
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

        {/* Page content */}
        <main className="flex-1 overflow-auto p-6">
          <Outlet context={{ lastEvent, status }} />
        </main>
      </div>
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
