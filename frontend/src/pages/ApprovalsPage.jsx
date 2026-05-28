import { useEffect, useState, useCallback, useRef } from 'react';
import { useOutletContext } from 'react-router-dom';
import { ShieldCheck, RefreshCw, Check, X, Clock, ChevronDown, MessageSquare } from 'lucide-react';
import clsx from 'clsx';
import { Card, Badge, EmptyState, PageHeader } from '../components/ui.jsx';
import { api } from '../utils/apiClient.js';
import { timeAgo, riskBadge } from '../utils/format.js';

const SOFT_AUTO_PROMOTE_MINUTES = 30;
const HARD_EXPIRY_HOURS = 24;

export default function ApprovalsPage() {
  const { lastEvent } = useOutletContext();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [modal, setModal] = useState(null); // { mode: 'approve'|'reject', approval: {...} }
  const [nowTick, setNowTick] = useState(Date.now());

  // Refresh "now" every second so countdowns tick
  useEffect(() => {
    const interval = setInterval(() => setNowTick(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get('/api/approvals/pending');
      setItems(response.data.pending || []);
    } catch (err) {
      setError(err.message);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // React to relevant WebSocket events
  useEffect(() => {
    if (!lastEvent) return;
    if (lastEvent.channel !== 'approvals') return;

    if (lastEvent.type === 'approval.created') {
      // Reload to get the new approval
      load();
    } else if (lastEvent.type === 'approval.transitioned') {
      // Remove from pending (it's no longer pending)
      const id = lastEvent.payload?.approval_id;
      if (id) {
        setItems(prev => prev.filter(a => a.approval_id !== id));
      }
    }
  }, [lastEvent, load]);

  // Optimistic remove on action
  const handleAction = async (approval, mode, comment) => {
    const previous = items;
    setItems(prev => prev.filter(a => a.approval_id !== approval.approval_id));
    setModal(null);

    try {
      const endpoint = `/api/approvals/${encodeURIComponent(approval.pipeline_id)}/${encodeURIComponent(approval.approval_id)}/${mode}`;
      const body = mode === 'approve'
        ? { approved_by: 'aryan', comment }
        : { rejected_by: 'aryan', comment };
      await api.post(endpoint, body);
    } catch (err) {
      // Restore on failure
      setItems(previous);
      alert(`Action failed: ${err.message}`);
    }
  };

  return (
    <>
      <PageHeader
        title="Approvals"
        subtitle="Pending human-in-the-loop decisions with live countdowns"
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
            icon={ShieldCheck}
            title="No pending approvals"
            hint="Approval requests will appear here when PRs are flagged for human review"
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {items.map(approval => (
            <ApprovalCard
              key={approval.approval_id}
              approval={approval}
              nowTick={nowTick}
              onApprove={() => setModal({ mode: 'approve', approval })}
              onReject={() => setModal({ mode: 'reject', approval })}
            />
          ))}
        </div>
      )}

      {modal && (
        <ActionModal
          mode={modal.mode}
          approval={modal.approval}
          onClose={() => setModal(null)}
          onConfirm={(comment) => handleAction(modal.approval, modal.mode, comment)}
        />
      )}
    </>
  );
}

// ─── Approval card ───────────────────────────────────────────────────────────

function ApprovalCard({ approval, nowTick, onApprove, onReject }) {
  const [expanded, setExpanded] = useState(false);
  const rk = riskBadge(approval.risk_level);

  // Compute deadline + countdown
  const createdMs = new Date(approval.created_at).getTime();
  const deadline = approval.risk_level === 'soft'
    ? createdMs + SOFT_AUTO_PROMOTE_MINUTES * 60 * 1000
    : createdMs + HARD_EXPIRY_HOURS * 3600 * 1000;
  const remaining = deadline - nowTick;
  const countdown = formatCountdown(remaining);
  const urgency = remaining < 5 * 60 * 1000 ? 'danger' : remaining < 15 * 60 * 1000 ? 'warning' : 'info';

  return (
    <Card>
      <div className="p-4">
        <div className="flex items-start justify-between gap-4">
          {/* Left: metadata */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <Badge variant={rk.variant}>{rk.label}</Badge>
              <span className="text-xs text-slate-500 font-mono">{approval.approval_id}</span>
            </div>
            <div className="text-sm text-slate-200 font-medium">
              {approval.reason || 'Approval required'}
            </div>
            <div className="text-xs text-slate-500 mt-1 font-mono">
              pipeline: {approval.pipeline_id}
            </div>
            <div className="text-xs text-slate-500 mt-0.5">
              created {timeAgo(approval.created_at)}
            </div>

            {approval.critical_files?.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {approval.critical_files.slice(0, 5).map((f, i) => (
                  <span key={i} className="text-[10px] font-mono text-amber-300 bg-amber-900/20 border border-amber-900 px-1.5 py-0.5 rounded">
                    {f}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Middle: countdown */}
          <div className="flex flex-col items-center gap-1 min-w-[140px]">
            <Badge variant={urgency}>
              <Clock className="w-3 h-3 mr-1" />
              {countdown}
            </Badge>
            <div className="text-[10px] text-slate-500 uppercase tracking-wider">
              {approval.risk_level === 'soft' ? 'to auto-promote' : 'to expire'}
            </div>
          </div>

          {/* Right: actions */}
          <div className="flex flex-col gap-2 min-w-[120px]">
            <button
              onClick={onApprove}
              className="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition-colors"
            >
              <Check className="w-3.5 h-3.5" />
              Approve
            </button>
            <button
              onClick={onReject}
              className="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md bg-red-600/20 hover:bg-red-600/30 text-red-300 text-xs font-medium border border-red-900 transition-colors"
            >
              <X className="w-3.5 h-3.5" />
              Reject
            </button>
          </div>
        </div>

        {/* Audit trail expander */}
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-3 flex items-center gap-1 text-[11px] text-slate-500 hover:text-slate-300 transition-colors"
        >
          <ChevronDown className={clsx('w-3 h-3 transition-transform', expanded && 'rotate-180')} />
          {expanded ? 'Hide' : 'Show'} audit trail
        </button>

        {expanded && (
          <AuditTrail approval={approval} />
        )}
      </div>
    </Card>
  );
}

// ─── Audit trail ─────────────────────────────────────────────────────────────

function AuditTrail({ approval }) {
  const [events, setEvents] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const response = await api.get(
          `/api/approvals/${encodeURIComponent(approval.pipeline_id)}/${encodeURIComponent(approval.approval_id)}`
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
  }, [approval.pipeline_id, approval.approval_id]);

  if (loading) {
    return <div className="mt-3 text-xs text-slate-500">Loading audit trail…</div>;
  }
  if (!events || events.length === 0) {
    return <div className="mt-3 text-xs text-slate-500">No events yet (approval was just created).</div>;
  }

  return (
    <div className="mt-3 border-t border-slate-800 pt-3 space-y-2">
      {events.map((e, i) => (
        <div key={i} className="flex items-center gap-3 text-xs">
          <span className="text-slate-500 font-mono w-32 shrink-0">{timeAgo(e.event_timestamp)}</span>
          <span className="text-slate-400">{e.from_state} → <span className="text-slate-200">{e.to_state}</span></span>
          <span className="text-slate-500 ml-auto">{e.actor}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Action modal ────────────────────────────────────────────────────────────

function ActionModal({ mode, approval, onClose, onConfirm }) {
  const [comment, setComment] = useState('');
  const isApprove = mode === 'approve';

  // Close on Escape
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-slate-900 border border-slate-700 rounded-lg w-full max-w-md mx-4 shadow-xl"
      >
        <div className="px-5 py-4 border-b border-slate-800">
          <h3 className="text-base font-semibold text-slate-100">
            {isApprove ? 'Approve this PR' : 'Reject this PR'}
          </h3>
          <p className="text-xs text-slate-500 mt-1 font-mono">
            {approval.approval_id}
          </p>
        </div>

        <div className="px-5 py-4 space-y-4">
          <div className="text-sm text-slate-300">{approval.reason}</div>

          <div>
            <label className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-slate-500 mb-1.5">
              <MessageSquare className="w-3 h-3" />
              Comment (optional)
            </label>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder={isApprove ? "LGTM, deploying" : "Why reject?"}
              rows={3}
              className="w-full px-3 py-2 text-sm bg-slate-950 border border-slate-700 rounded text-slate-200 focus:outline-none focus:border-emerald-500 resize-none"
              autoFocus
            />
          </div>
        </div>

        <div className="px-5 py-3 border-t border-slate-800 flex items-center justify-end gap-2">
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded-md text-sm text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm(comment)}
            className={clsx(
              'flex items-center gap-1.5 px-4 py-1.5 rounded-md text-sm font-medium text-white transition-colors',
              isApprove
                ? 'bg-emerald-600 hover:bg-emerald-500'
                : 'bg-red-600 hover:bg-red-500'
            )}
          >
            {isApprove ? <Check className="w-3.5 h-3.5" /> : <X className="w-3.5 h-3.5" />}
            Confirm {isApprove ? 'Approve' : 'Reject'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatCountdown(ms) {
  if (ms <= 0) return 'expired';

  const totalSec = Math.floor(ms / 1000);
  const hours = Math.floor(totalSec / 3600);
  const mins = Math.floor((totalSec % 3600) / 60);
  const secs = totalSec % 60;

  if (hours >= 1) return `${hours}h ${String(mins).padStart(2, '0')}m`;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}
