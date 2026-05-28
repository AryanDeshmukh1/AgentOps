import { useEffect, useState, useCallback, useRef } from 'react';
import { useSearchParams, useNavigate, useOutletContext } from 'react-router-dom';
import { GitPullRequest, RefreshCw, ChevronLeft, ChevronRight, Filter, X } from 'lucide-react';
import clsx from 'clsx';
import { Card, Badge, EmptyState, PageHeader } from '../components/ui.jsx';
import { listPaginated } from '../utils/apiClient.js';
import { timeAgo, decisionBadge, statusBadge, riskBadge } from '../utils/format.js';

const STATUS_OPTIONS = ['', 'running', 'complete', 'blocked', 'awaiting_approval', 'failed'];
const RISK_OPTIONS = ['', 'auto', 'soft', 'hard'];

export default function PipelinesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { lastEvent } = useOutletContext();

  const status = searchParams.get('status') || '';
  const repo = searchParams.get('repo') || '';
  const risk = searchParams.get('risk_level') || '';

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [nextCursor, setNextCursor] = useState(null);
  const [flashedIds, setFlashedIds] = useState(new Set());

  // Cursor history stack so Prev works without backend round-trip
  const cursorStack = useRef([]);

  // Build query params from filters + current cursor
  const buildParams = useCallback((cursor) => {
    const p = { limit: 20 };
    if (status) p.status = status;
    if (repo) p.repo = repo;
    if (risk) p.risk_level = risk;
    if (cursor) p.cursor = cursor;
    return p;
  }, [status, repo, risk]);

  const load = useCallback(async (cursor = null, isInitial = false) => {
    setLoading(true);
    setError(null);
    try {
      const data = await listPaginated('/api/pipelines', buildParams(cursor));
      setItems(data.items || []);
      setNextCursor(data.next_cursor || null);
      if (isInitial) cursorStack.current = [];
    } catch (err) {
      setError(err.message);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [buildParams]);

  // Initial load + reload on filter change
  useEffect(() => {
    load(null, true);
  }, [status, repo, risk, load]);

  // Flash matching row when a relevant event arrives
  useEffect(() => {
    if (!lastEvent) return;
    if (lastEvent.channel !== 'pipelines') return;
    const id = lastEvent.payload?.pipeline_id;
    if (!id) return;
    setFlashedIds(prev => new Set(prev).add(id));
    const timeout = setTimeout(() => {
      setFlashedIds(prev => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }, 2500);
    return () => clearTimeout(timeout);
  }, [lastEvent]);

  const handleFilterChange = (key, value) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next);
  };

  const clearFilters = () => setSearchParams({});

  const handleNext = () => {
    if (!nextCursor) return;
    cursorStack.current.push(nextCursor);
    load(nextCursor);
  };

  const handlePrev = () => {
    if (cursorStack.current.length === 0) return;
    cursorStack.current.pop();
    const prev = cursorStack.current[cursorStack.current.length - 1] || null;
    load(prev);
  };

  const hasFilters = status || repo || risk;
  const hasPrev = cursorStack.current.length > 0;

  return (
    <>
      <PageHeader
        title="Pipelines"
        subtitle="Every pull request that has flowed through the agent system"
      >
        <button
          onClick={() => load(null, true)}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-sm text-slate-200 disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={clsx('w-3.5 h-3.5', loading && 'animate-spin')} />
          Refresh
        </button>
      </PageHeader>

      <Card className="mb-4">
        <div className="px-4 py-3 flex flex-wrap items-center gap-3">
          <Filter className="w-4 h-4 text-slate-500" />
          <FilterSelect
            label="status"
            value={status}
            options={STATUS_OPTIONS}
            onChange={(v) => handleFilterChange('status', v)}
          />
          <FilterSelect
            label="risk"
            value={risk}
            options={RISK_OPTIONS}
            onChange={(v) => handleFilterChange('risk_level', v)}
          />
          <input
            type="text"
            placeholder="repo (owner/name)"
            value={repo}
            onChange={(e) => handleFilterChange('repo', e.target.value)}
            className="px-2 py-1 text-xs bg-slate-900 border border-slate-700 rounded text-slate-200 focus:outline-none focus:border-emerald-500 w-56"
          />
          {hasFilters && (
            <button
              onClick={clearFilters}
              className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-300"
            >
              <X className="w-3 h-3" />
              clear
            </button>
          )}
          <div className="ml-auto text-xs text-slate-500">
            {loading ? 'loading…' : `${items.length} on this page`}
          </div>
        </div>
      </Card>

      <Card>
        {error ? (
          <div className="p-6 text-sm text-red-400 font-mono">Error: {error}</div>
        ) : items.length === 0 && !loading ? (
          <EmptyState
            icon={GitPullRequest}
            title="No pipelines match"
            hint={hasFilters ? "Try clearing filters or pushing a new PR" : "Push a PR to see one appear here"}
          />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-800">
                <th className="text-left px-4 py-2 font-medium">PR</th>
                <th className="text-left px-4 py-2 font-medium">Repo</th>
                <th className="text-left px-4 py-2 font-medium">Decision</th>
                <th className="text-left px-4 py-2 font-medium">Status</th>
                <th className="text-left px-4 py-2 font-medium">Risk</th>
                <th className="text-right px-4 py-2 font-medium">Score</th>
                <th className="text-right px-4 py-2 font-medium">Findings</th>
                <th className="text-right px-4 py-2 font-medium">When</th>
              </tr>
            </thead>
            <tbody>
              {items.map((p) => (
                <PipelineRow
                  key={p.pipeline_id}
                  pipeline={p}
                  flashed={flashedIds.has(p.pipeline_id)}
                 onClick={() => navigate(`/pipelines/${encodeURIComponent(p.pipeline_id)}`, { state: { pipeline: p } })}
                />
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Pagination */}
      <div className="flex items-center justify-between mt-4">
        <div className="text-xs text-slate-500 font-mono">
          {hasPrev && `page ${cursorStack.current.length + 1}`}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handlePrev}
            disabled={!hasPrev || loading}
            className="flex items-center gap-1 px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
            Prev
          </button>
          <button
            onClick={handleNext}
            disabled={!nextCursor || loading}
            className="flex items-center gap-1 px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          >
            Next
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </>
  );
}

function FilterSelect({ label, value, options, onChange }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[10px] uppercase tracking-wider text-slate-500">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="px-2 py-1 text-xs bg-slate-900 border border-slate-700 rounded text-slate-200 focus:outline-none focus:border-emerald-500"
      >
        {options.map(opt => (
          <option key={opt} value={opt}>{opt || 'all'}</option>
        ))}
      </select>
    </div>
  );
}

function PipelineRow({ pipeline, flashed, onClick }) {
  const dec = decisionBadge(pipeline.decision);
  const st = statusBadge(pipeline.status);
  const rk = riskBadge(pipeline.risk_level);

  return (
    <tr
      onClick={onClick}
      className={clsx(
        'border-b border-slate-800 last:border-0 hover:bg-slate-800/40 cursor-pointer transition-colors',
        flashed && 'animate-pulse bg-emerald-900/20',
      )}
    >
      <td className="px-4 py-3">
        <div className="flex flex-col">
          <span className="font-medium text-slate-200">#{pipeline.pr_number} {pipeline.pr_title}</span>
          <span className="text-[10px] text-slate-500 font-mono">{pipeline.pr_author}</span>
        </div>
      </td>
      <td className="px-4 py-3 text-slate-400 text-xs font-mono">{pipeline.repo}</td>
      <td className="px-4 py-3"><Badge variant={dec.variant}>{dec.label}</Badge></td>
      <td className="px-4 py-3"><Badge variant={st.variant}>{st.label}</Badge></td>
      <td className="px-4 py-3"><Badge variant={rk.variant}>{rk.label}</Badge></td>
      <td className="px-4 py-3 text-right font-mono text-slate-300">{pipeline.review_score ?? '—'}</td>
      <td className="px-4 py-3 text-right font-mono text-slate-400">{pipeline.total_findings ?? '—'}</td>
      <td className="px-4 py-3 text-right text-xs text-slate-500">{timeAgo(pipeline.created_at)}</td>
    </tr>
  );
}
