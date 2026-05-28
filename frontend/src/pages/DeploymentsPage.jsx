import { useEffect, useState, useCallback, useRef } from 'react';
import { useOutletContext } from 'react-router-dom';
import {
  Rocket, RefreshCw, ChevronDown, RotateCcw, GitCommit,
  CheckCircle2, XCircle, AlertCircle, Clock, Activity,
} from 'lucide-react';
import clsx from 'clsx';
import { Card, CardHeader, CardBody, Badge, EmptyState, PageHeader } from '../components/ui.jsx';
import { api } from '../utils/apiClient.js';
import { timeAgo } from '../utils/format.js';

// Deployment state machine — order matters for the stepper
const STATE_FLOW = [
  'pending',
  'provisioning',
  'smoke_test',
  'ready_for_traffic_shift',
  'traffic_shifting',
  'monitoring',
  'promoted',
];
const TERMINAL_FAILURE = ['failed', 'rolled_back'];

const STATE_META = {
  pending:                  { label: 'Pending',       variant: 'muted' },
  provisioning:             { label: 'Provisioning',  variant: 'info' },
  smoke_test:               { label: 'Smoke Test',    variant: 'info' },
  ready_for_traffic_shift:  { label: 'Ready',         variant: 'info' },
  traffic_shifting:         { label: 'Shifting',      variant: 'warning' },
  monitoring:               { label: 'Monitoring',    variant: 'warning' },
  promoted:                 { label: 'Promoted',      variant: 'success' },
  failed:                   { label: 'Failed',        variant: 'danger' },
  rolled_back:              { label: 'Rolled Back',   variant: 'danger' },
};

export default function DeploymentsPage() {
  const { lastEvent } = useOutletContext();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [confirmRollback, setConfirmRollback] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get('/api/deployments');
      const list = response.data.deployments || [];
      setItems(list);
      if (!selectedId && list.length > 0) {
        setSelectedId(list[0].deployment_id);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [selectedId]);

  useEffect(() => { load(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps

  // React to deployment events on the WebSocket
  useEffect(() => {
    if (!lastEvent) return;
    if (lastEvent.channel !== 'deployments') return;
    const id = lastEvent.payload?.deployment_id;
    if (!id) return;

    // Optimistically patch the matching deployment with the event's data
    setItems(prev => prev.map(d => {
      if (d.deployment_id !== id) return d;
      const next = { ...d, last_updated_at: lastEvent.ts };
      if (lastEvent.type === 'deployment.traffic_shifted') {
        next.traffic_split = {
          blue: lastEvent.payload.blue_percent,
          green: lastEvent.payload.green_percent,
        };
      } else if (lastEvent.type === 'deployment.transitioned') {
        next.status = lastEvent.payload.to_state;
        next.last_comment = lastEvent.payload.comment;
      } else if (lastEvent.type === 'deployment.rolled_back') {
        next.status = 'rolled_back';
        next.traffic_split = { blue: 100, green: 0 };
      }
      return next;
    }));
  }, [lastEvent]);

  const selected = items.find(d => d.deployment_id === selectedId);

  const handleRollback = async (deployment) => {
    setConfirmRollback(null);
    const previous = items;
    // Optimistic update
    setItems(prev => prev.map(d =>
      d.deployment_id === deployment.deployment_id
        ? { ...d, status: 'rolled_back', traffic_split: { blue: 100, green: 0 } }
        : d
    ));

    try {
      await api.post(
        `/api/deployments/${encodeURIComponent(deployment.pipeline_id)}/${encodeURIComponent(deployment.deployment_id)}/rollback`,
        { triggered_by: 'aryan', reason: 'Manual rollback from dashboard' }
      );
    } catch (err) {
      setItems(previous);
      alert(`Rollback failed: ${err.message}`);
    }
  };

  return (
    <>
      <PageHeader
        title="Deployments"
        subtitle="Live blue/green traffic shifting with rollback controls"
      >
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-sm text-slate-200 disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={clsx('w-3.5 h-3.5', loading && 'animate-spin')} />
          Refresh
        </button>
      </PageHeader>

      {error ? (
        <Card><div className="p-6 text-sm text-red-400 font-mono">Error: {error}</div></Card>
      ) : items.length === 0 && !loading ? (
        <Card>
          <EmptyState
            icon={Rocket}
            title="No deployments yet"
            hint="Deployments will appear here as DeployAgent runs"
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: deployment list */}
          <div className="lg:col-span-1 space-y-2">
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-2 px-1">
              Recent deployments
            </div>
            {items.map(d => (
              <DeploymentListItem
                key={d.deployment_id}
                deployment={d}
                isSelected={d.deployment_id === selectedId}
                onClick={() => setSelectedId(d.deployment_id)}
              />
            ))}
          </div>

          {/* Right: selected deployment detail */}
          <div className="lg:col-span-2">
            {selected ? (
              <DeploymentDetail
                deployment={selected}
                onRollback={() => setConfirmRollback(selected)}
              />
            ) : (
              <Card><CardBody>
                <div className="text-sm text-slate-400">Select a deployment from the list</div>
              </CardBody></Card>
            )}
          </div>
        </div>
      )}

      {confirmRollback && (
        <RollbackModal
          deployment={confirmRollback}
          onCancel={() => setConfirmRollback(null)}
          onConfirm={() => handleRollback(confirmRollback)}
        />
      )}
    </>
  );
}

// ─── List item ───────────────────────────────────────────────────────────────

function DeploymentListItem({ deployment, isSelected, onClick }) {
  const meta = STATE_META[deployment.status] || { label: deployment.status, variant: 'default' };
  return (
    <button
      onClick={onClick}
      className={clsx(
        'w-full text-left p-3 rounded-md border transition-colors',
        isSelected
          ? 'bg-slate-800 border-emerald-700'
          : 'bg-slate-900/40 border-slate-800 hover:bg-slate-800/60',
      )}
    >
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <span className="text-xs font-mono text-slate-400 truncate">
          {deployment.repo} #{deployment.pr_number}
        </span>
        <Badge variant={meta.variant}>{meta.label}</Badge>
      </div>
      <div className="text-[11px] text-slate-500 truncate">
        {deployment.deployment_id}
      </div>
      <div className="flex items-center justify-between mt-1.5">
        <MiniTrafficBar split={deployment.traffic_split || { blue: 100, green: 0 }} />
        <span className="text-[10px] text-slate-500 ml-2">{timeAgo(deployment.last_updated_at)}</span>
      </div>
    </button>
  );
}

function MiniTrafficBar({ split }) {
  return (
    <div className="flex-1 flex h-1.5 rounded-full overflow-hidden bg-slate-800">
      <div className="bg-sky-500 transition-all duration-700" style={{ width: `${split.blue}%` }} />
      <div className="bg-emerald-500 transition-all duration-700" style={{ width: `${split.green}%` }} />
    </div>
  );
}

// ─── Detail panel ────────────────────────────────────────────────────────────

function DeploymentDetail({ deployment, onRollback }) {
  const isPromoted = deployment.status === 'promoted';
  const isTerminal = ['promoted', 'failed', 'rolled_back'].includes(deployment.status);
  const meta = STATE_META[deployment.status] || { label: deployment.status, variant: 'default' };

  return (
    <div className="space-y-4">
      <Card>
        <CardBody>
          <div className="flex items-start justify-between gap-4 mb-4">
            <div className="flex-1 min-w-0">
              <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">deployment</div>
              <code className="text-xs text-slate-300 font-mono">{deployment.deployment_id}</code>
              <div className="flex items-center gap-3 mt-3 text-xs text-slate-400 flex-wrap">
                <span>{deployment.repo} <span className="text-slate-500">#{deployment.pr_number}</span></span>
                <span className="flex items-center gap-1"><GitCommit className="w-3 h-3" /> {deployment.head_sha?.slice(0, 7)}</span>
                <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {timeAgo(deployment.last_updated_at)}</span>
              </div>
            </div>
            <div className="flex flex-col items-end gap-2">
              <Badge variant={meta.variant}>{meta.label}</Badge>
              {isPromoted && (
                <button
                  onClick={onRollback}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-red-600/20 hover:bg-red-600/30 text-red-300 text-xs font-medium border border-red-900 transition-colors"
                >
                  <RotateCcw className="w-3 h-3" />
                  Rollback
                </button>
              )}
            </div>
          </div>

          {/* State machine stepper */}
          <StateStepper status={deployment.status} />

          {deployment.last_comment && (
            <div className="mt-4 px-3 py-2 bg-slate-950 border border-slate-800 rounded text-xs text-slate-400">
              <span className="text-[10px] uppercase tracking-wider text-slate-500 mr-2">last update</span>
              {deployment.last_comment}
            </div>
          )}
        </CardBody>
      </Card>

      {/* Big traffic split visualization */}
      <Card>
        <CardHeader>
          <div className="text-sm font-medium">Traffic split</div>
        </CardHeader>
        <CardBody>
          <BigTrafficViz split={deployment.traffic_split || { blue: 100, green: 0 }} status={deployment.status} />
        </CardBody>
      </Card>

      {/* Events */}
      <DeploymentEvents
        pipelineId={deployment.pipeline_id}
        deploymentId={deployment.deployment_id}
        lastUpdate={deployment.last_updated_at}
      />
    </div>
  );
}

// ─── State machine stepper ───────────────────────────────────────────────────

function StateStepper({ status }) {
  const isFailure = TERMINAL_FAILURE.includes(status);
  const currentIdx = STATE_FLOW.indexOf(status);

  return (
    <div className="flex items-center gap-0.5 overflow-x-auto">
      {STATE_FLOW.map((state, i) => {
        const isCurrent = state === status;
        const isPast = !isFailure && currentIdx > i;
        const meta = STATE_META[state];
        return (
          <div key={state} className="flex items-center gap-0.5 flex-1 min-w-0">
            <div className={clsx(
              'flex-1 px-2 py-1.5 rounded text-center text-[10px] font-medium uppercase tracking-wider',
              isCurrent && 'bg-emerald-900/40 text-emerald-300 border border-emerald-700',
              isPast && 'bg-slate-800/60 text-slate-400',
              !isCurrent && !isPast && 'bg-slate-900/40 text-slate-600',
            )}>
              {meta.label}
            </div>
            {i < STATE_FLOW.length - 1 && (
              <div className={clsx(
                'w-2 h-px',
                isPast ? 'bg-slate-600' : 'bg-slate-800',
              )} />
            )}
          </div>
        );
      })}
      {isFailure && (
        <>
          <div className="w-2 h-px bg-red-700" />
          <div className="px-3 py-1.5 rounded text-[10px] font-medium uppercase tracking-wider bg-red-900/40 text-red-300 border border-red-700">
            {STATE_META[status].label}
          </div>
        </>
      )}
    </div>
  );
}

// ─── Big traffic viz ─────────────────────────────────────────────────────────

function BigTrafficViz({ split, status }) {
  const isShifting = status === 'traffic_shifting' || status === 'monitoring';
  return (
    <div className="space-y-3">
      <TrafficLane
        label="BLUE"
        sublabel="current"
        percent={split.blue}
        color="sky"
        pulse={isShifting && split.blue > 0}
      />
      <TrafficLane
        label="GREEN"
        sublabel="new"
        percent={split.green}
        color="emerald"
        pulse={isShifting && split.green > 0}
      />
    </div>
  );
}

function TrafficLane({ label, sublabel, percent, color, pulse }) {
  const colorMap = {
    sky: { bar: 'bg-sky-500', text: 'text-sky-300', glow: 'shadow-sky-500/30' },
    emerald: { bar: 'bg-emerald-500', text: 'text-emerald-300', glow: 'shadow-emerald-500/30' },
  };
  const c = colorMap[color];

  return (
    <div>
      <div className="flex items-baseline justify-between mb-1.5">
        <div className="flex items-baseline gap-2">
          <span className={clsx('text-sm font-bold tracking-wider', c.text)}>{label}</span>
          <span className="text-[10px] uppercase tracking-wider text-slate-500">{sublabel}</span>
        </div>
        <span className={clsx('text-2xl font-mono font-bold tabular-nums', c.text)}>
          {percent}<span className="text-sm text-slate-500">%</span>
        </span>
      </div>
      <div className="relative h-8 bg-slate-950 rounded border border-slate-800 overflow-hidden">
        <div
          className={clsx(
            c.bar,
            'h-full transition-all ease-out',
            pulse && 'animate-pulse',
          )}
          style={{
            width: `${percent}%`,
            transitionDuration: '900ms',
          }}
        />
      </div>
    </div>
  );
}

// ─── Events list ─────────────────────────────────────────────────────────────

function DeploymentEvents({ pipelineId, deploymentId, lastUpdate }) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const response = await api.get(
          `/api/deployments/${encodeURIComponent(pipelineId)}/${encodeURIComponent(deploymentId)}/events`
        );
        if (!cancelled) setEvents(response.data.events || []);
      } catch {
        if (!cancelled) setEvents([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [pipelineId, deploymentId, lastUpdate]);

  return (
    <Card>
      <CardHeader>
        <div className="text-sm font-medium">Audit trail</div>
      </CardHeader>
      <CardBody className="p-0">
        {loading ? (
          <div className="p-4 text-xs text-slate-500">Loading events…</div>
        ) : events.length === 0 ? (
          <div className="p-4 text-xs text-slate-500">No events recorded.</div>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-800">
                <th className="text-left px-4 py-2 font-medium">Transition</th>
                <th className="text-left px-4 py-2 font-medium">Comment</th>
                <th className="text-left px-4 py-2 font-medium">Actor</th>
                <th className="text-right px-4 py-2 font-medium">When</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e, i) => (
                <tr key={i} className="border-b border-slate-800 last:border-0">
                  <td className="px-4 py-2 font-mono text-slate-300">
                    {e.from_state} → <span className="text-emerald-300">{e.to_state}</span>
                  </td>
                  <td className="px-4 py-2 text-slate-400 max-w-md truncate">{e.comment || '—'}</td>
                  <td className="px-4 py-2 text-slate-500">{e.actor}</td>
                  <td className="px-4 py-2 text-right text-slate-500">{timeAgo(e.event_timestamp)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </CardBody>
    </Card>
  );
}

// ─── Rollback modal ──────────────────────────────────────────────────────────

function RollbackModal({ deployment, onCancel, onConfirm }) {
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onCancel(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onCancel]);

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onCancel}>
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-slate-900 border border-slate-700 rounded-lg w-full max-w-md mx-4 shadow-xl"
      >
        <div className="px-5 py-4 border-b border-slate-800 flex items-center gap-2">
          <AlertCircle className="w-5 h-5 text-red-400" />
          <h3 className="text-base font-semibold text-slate-100">Confirm rollback</h3>
        </div>
        <div className="px-5 py-4 space-y-3">
          <p className="text-sm text-slate-300">
            This will revert traffic to <span className="text-sky-300 font-semibold">100% blue</span> immediately.
          </p>
          <p className="text-xs text-slate-500 font-mono">{deployment.deployment_id}</p>
          <p className="text-xs text-amber-300">This action is logged and cannot be undone via the UI.</p>
        </div>
        <div className="px-5 py-3 border-t border-slate-800 flex items-center justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-3 py-1.5 rounded-md text-sm text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-md bg-red-600 hover:bg-red-500 text-white text-sm font-medium transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Rollback
          </button>
        </div>
      </div>
    </div>
  );
}

