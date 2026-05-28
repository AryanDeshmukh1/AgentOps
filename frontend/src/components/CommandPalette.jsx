import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, GitPullRequest, ShieldCheck, Rocket, AlertTriangle, Settings, RefreshCw } from 'lucide-react';
import clsx from 'clsx';

const ACTIONS = [
  { id: 'nav-pipelines',   label: 'Go to Pipelines',   path: '/pipelines',   icon: GitPullRequest, keywords: 'pipelines list pr' },
  { id: 'nav-approvals',   label: 'Go to Approvals',   path: '/approvals',   icon: ShieldCheck, keywords: 'approvals approve reject' },
  { id: 'nav-deployments', label: 'Go to Deployments', path: '/deployments', icon: Rocket, keywords: 'deployments deploy traffic' },
  { id: 'nav-incidents',   label: 'Go to Incidents',   path: '/incidents',   icon: AlertTriangle, keywords: 'incidents anomaly metric' },
  { id: 'nav-settings',    label: 'Go to Settings',    path: '/settings',    icon: Settings, keywords: 'settings config env' },
  { id: 'action-reload',   label: 'Reload page',       action: 'reload',      icon: RefreshCw, keywords: 'refresh reload' },
];

export default function CommandPalette({ open, onClose }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [selectedIdx, setSelectedIdx] = useState(0);
  const inputRef = useRef(null);

  useEffect(() => {
    if (open) {
      setQuery('');
      setSelectedIdx(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  const filtered = ACTIONS.filter(a => {
    if (!query) return true;
    const q = query.toLowerCase();
    return a.label.toLowerCase().includes(q) || a.keywords.includes(q);
  });

  // Reset selection when filter changes
  useEffect(() => {
    setSelectedIdx(0);
  }, [query]);

  const execute = (action) => {
    onClose();
    if (action.path) navigate(action.path);
    else if (action.action === 'reload') window.location.reload();
  };

  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (e.key === 'Escape') { onClose(); return; }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIdx(i => Math.min(i + 1, filtered.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIdx(i => Math.max(i - 1, 0));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (filtered[selectedIdx]) execute(filtered[selectedIdx]);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, filtered, selectedIdx]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-start justify-center pt-24 z-50"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-slate-900 border border-slate-700 rounded-lg w-full max-w-lg mx-4 shadow-2xl overflow-hidden"
      >
        <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-800">
          <Search className="w-4 h-4 text-slate-500" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search actions..."
            className="flex-1 bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none"
          />
          <kbd className="text-[10px] font-mono text-slate-500 px-1.5 py-0.5 border border-slate-700 rounded">esc</kbd>
        </div>

        <div className="max-h-80 overflow-y-auto p-1">
          {filtered.length === 0 ? (
            <div className="px-3 py-6 text-center text-xs text-slate-500">No matches</div>
          ) : (
            filtered.map((action, i) => {
              const Icon = action.icon;
              return (
                <button
                  key={action.id}
                  onClick={() => execute(action)}
                  onMouseEnter={() => setSelectedIdx(i)}
                  className={clsx(
                    'w-full flex items-center gap-3 px-3 py-2 rounded text-left text-sm',
                    i === selectedIdx ? 'bg-slate-800 text-slate-100' : 'text-slate-300',
                  )}
                >
                  <Icon className="w-4 h-4 text-slate-500" />
                  <span className="flex-1">{action.label}</span>
                  {action.path && <span className="text-[10px] text-slate-500 font-mono">{action.path}</span>}
                </button>
              );
            })
          )}
        </div>

        <div className="px-4 py-2 border-t border-slate-800 flex items-center justify-between text-[10px] text-slate-500 font-mono">
          <span>↑↓ navigate · ↵ select · esc close</span>
          <span>{filtered.length} action{filtered.length !== 1 ? 's' : ''}</span>
        </div>
      </div>
    </div>
  );
}