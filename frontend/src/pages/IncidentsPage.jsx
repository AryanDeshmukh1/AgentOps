import { useEffect, useState, useCallback } from 'react';
import { useOutletContext } from 'react-router-dom';
import {
  AlertTriangle, RefreshCw, Sparkles, Eye, CheckCircle2, Clock,
  TrendingDown, TrendingUp, Activity, FileText, Lightbulb,
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer,
} from 'recharts';
import clsx from 'clsx';
import { Card, CardHeader, CardBody, Badge, EmptyState, PageHeader } from '../components/ui.jsx';
import { api } from '../utils/apiClient.js';
import { timeAgo } from '../utils/format.js';

const SEVERITY_META = {
  critical: { variant: 'danger',  label: 'CRITICAL',  rank: 0 },
  high:     { variant: 'danger',  label: 'HIGH',      rank: 1 },
  warning:  { variant: 'warning', label: 'WARNING',   rank: 2 },
  info:     { variant: 'info',    label: 'INFO',      rank: 3 },
};

const STATUS_META = {
  open:         { variant: 'danger',  label: 'open' },
  acknowledged: { variant: 'warning', label: 'acknowledged' },
  resolved:     { variant: 'success', label: 'resolved' },
};

const CONFIDENCE_META = {
  high:    { variant: 'success', label: 'high confidence' },
  medium:  { variant: 'warning', label: 'medium confidence' },
  low:     { variant: 'muted',   label: 'low confidence' },
  unknown: { variant: 'muted',   label: 'unknown' },
};

const METRIC_META = {
  error_rate_pct:     { label: 'Error Rate',     unit: '%',  color: '#ef4444' },
  latency_p95_ms:     { label: 'Latency (p95)',  unit: 'ms', color: '#f59e0b' },
  request_volume_rpm: { label: 'Request Volume', unit: 'rpm', color: '#3b82f6' },
};

export default function IncidentsPage() {
  const { lastEvent } = useOutletContext();
  const [incidents, setIncidents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get('/api/incidents');
      const list = response.data.incidents || [];
      setIncidents(list);
      if (!selectedId && list.length > 0) {
        setSelectedId(list[0].incident_id);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [selectedId]);

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // React to incident events
  useEffect(() => {
    if (!lastEvent) return;
    if (lastEvent.channel !== 'incidents') return;

    if (lastEvent.type === 'incident.fired') {
      // New incident — reload to get full record
      load();
    } else if (lastEvent.type === 'incident.root_cause_attached') {
      // Patch matching incident with new AI fields
      const id = lastEvent.payload?.incident_id;
      if (!id) return;
      setIncidents(prev => prev.map(i =>
        i.incident_id === id
          ? {
              ...i,
              root_cause: lastEvent.payload.root_cause,
              suggested_fix: lastEvent.payload.suggested_fix,
              ai_confidence: lastEvent.payload.ai_confidence,
            }
          : i
      ));
    }
  }, [lastEvent, load]);

  const selected = incidents.find(i => i.incident_id === selectedId);

  return (
    <>
      <PageHeader
        title="Incidents"
        subtitle="Anomaly detection with AI-generated root cause analysis"
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
      ) : incidents.length === 0 && !loading ? (
        <Card>
          <EmptyState
            icon={AlertTriangle}
            title="No incidents detected"
            hint="Anomalies will appear here when post-deploy metrics drift beyond baseline"
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1 space-y-2">
            <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-2 px-1">
              {incidents.length} incident{incidents.length !== 1 ? 's' : ''}
            </div>
            {incidents.map(inc => (
              <IncidentListItem
                key={inc.incident_id}
                incident={inc}
                isSelected={inc.incident_id === selectedId}
                onClick={() => setSelectedId(inc.incident_id)}
              />
            ))}
          </div>

          <div className="lg:col-span-2">
            {selected ? (
              <IncidentDetail incident={selected} onUpdate={load} />
            ) : (
              <Card><CardBody>
                <div className="text-sm text-slate-400">Select an incident from the list</div>
              </CardBody></Card>
            )}
          </div>
        </div>
      )}
    </>
  );
}

// ─── List item ───────────────────────────────────────────────────────────────

function IncidentListItem({ incident, isSelected, onClick }) {
  const sev = SEVERITY_META[incident.severity] || SEVERITY_META.warning;
  const st = STATUS_META[incident.status] || STATUS_META.open;
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
        <Badge variant={sev.variant}>{sev.label}</Badge>
        <Badge variant={st.variant}>{st.label}</Badge>
      </div>
      <div className="text-xs text-slate-300 line-clamp-2 leading-tight">{incident.summary}</div>
      <div className="flex items-center justify-between mt-2">
        <span className="text-[10px] text-slate-500 font-mono">
          |z|={incident.max_abs_z?.toFixed(2)}
        </span>
        <span className="text-[10px] text-slate-500">{timeAgo(incident.created_at)}</span>
      </div>
    </button>
  );
}

// ─── Detail panel ────────────────────────────────────────────────────────────

function IncidentDetail({ incident, onUpdate }) {
  const [metrics, setMetrics] = useState([]);
  const [metricsLoading, setMetricsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setMetricsLoading(true);
      try {
        const response = await api.get(
          `/api/incidents/${encodeURIComponent(incident.deployment_id)}/${encodeURIComponent(incident.incident_id)}`
        );
        if (!cancelled) setMetrics(response.data.metrics || []);
      } catch {
        if (!cancelled) setMetrics([]);
      } finally {
        if (!cancelled) setMetricsLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [incident.deployment_id, incident.incident_id]);

  const handleAction = async (action) => {
    try {
      await api.post(
        `/api/incidents/${encodeURIComponent(incident.deployment_id)}/${encodeURIComponent(incident.incident_id)}/${action}`,
        { actor: 'aryan' }
      );
      onUpdate();
    } catch (err) {
      alert(`Action failed: ${err.message}`);
    }
  };

  const sev = SEVERITY_META[incident.severity] || SEVERITY_META.warning;
  const st = STATUS_META[incident.status] || STATUS_META.open;
  const hasAI = !!incident.root_cause;
  const isOpen = incident.status === 'open';
  const isAcknowledged = incident.status === 'acknowledged';

  return (
    <div className="space-y-4">
      {/* Header card */}
      <Card>
        <CardBody>
          <div className="flex items-start justify-between gap-4 mb-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-2">
                <Badge variant={sev.variant}>{sev.label}</Badge>
                <Badge variant={st.variant}>{st.label}</Badge>
                <span className="text-[10px] text-slate-500 font-mono">|z|={incident.max_abs_z?.toFixed(2)}</span>
              </div>
              <div className="text-sm text-slate-200 font-mono leading-relaxed">{incident.summary}</div>
              <div className="text-[10px] text-slate-500 mt-2 font-mono">
                incident: {incident.incident_id}
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5 font-mono">
                deployment: {incident.deployment_id} · fired {timeAgo(incident.created_at)}
              </div>
            </div>
            <div className="flex flex-col gap-2 min-w-[120px]">
              {isOpen && (
                <button
                  onClick={() => handleAction('acknowledge')}
                  className="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 text-xs font-medium border border-amber-900 transition-colors"
                >
                  <Eye className="w-3.5 h-3.5" /> Acknowledge
                </button>
              )}
              {(isOpen || isAcknowledged) && (
                <button
                  onClick={() => handleAction('resolve')}
                  className="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition-colors"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" /> Resolve
                </button>
              )}
            </div>
          </div>

          {/* Anomalous metrics row */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-4">
            {incident.all_metrics?.map(m => (
              <MetricSummaryCard key={m.name} metric={m} />
            ))}
          </div>
        </CardBody>
      </Card>

      {/* AI Analysis panel */}
      <AIPanel incident={incident} />

      {/* Metric chart */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Metrics around anomaly</span>
            <span className="text-[10px] text-slate-500">
              {metricsLoading ? 'loading…' : `${metrics.length} samples`}
            </span>
          </div>
        </CardHeader>
        <CardBody>
          {metricsLoading ? (
            <div className="text-xs text-slate-500">Loading metric window…</div>
          ) : metrics.length === 0 ? (
            <div className="text-xs text-slate-500">No metrics available for this window.</div>
          ) : (
            <div className="space-y-4">
              {['error_rate_pct', 'latency_p95_ms', 'request_volume_rpm'].map(metricKey => (
                <MetricChart
                  key={metricKey}
                  metricKey={metricKey}
                  metrics={metrics}
                  firedAt={incident.created_at}
                  baseline={incident.baseline_snapshot?.metrics?.[metricKey]}
                />
              ))}
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}

// ─── Metric summary card ─────────────────────────────────────────────────────

function MetricSummaryCard({ metric }) {
  const meta = METRIC_META[metric.name] || { label: metric.name, unit: '', color: '#94a3b8' };
  const Icon = metric.direction === 'down' ? TrendingDown : TrendingUp;
  return (
    <div className={clsx(
      'p-3 rounded border',
      metric.is_anomalous ? 'bg-red-950/30 border-red-900' : 'bg-slate-900/40 border-slate-800',
    )}>
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-slate-500 mb-1">
        <Icon className="w-3 h-3" />
        {meta.label}
      </div>
      <div className="text-base font-mono font-bold text-slate-200">
        {metric.current_value?.toFixed(2)}<span className="text-xs text-slate-500 ml-0.5">{meta.unit}</span>
      </div>
      <div className="text-[10px] text-slate-500 mt-0.5">
        baseline {metric.baseline_mean?.toFixed(2)} · z={metric.z_score?.toFixed(2)}
      </div>
    </div>
  );
}

// ─── AI Panel ────────────────────────────────────────────────────────────────

function AIPanel({ incident }) {
  const hasAI = !!incident.root_cause;
  const conf = CONFIDENCE_META[incident.ai_confidence] || CONFIDENCE_META.unknown;

  if (!hasAI) {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-violet-400" />
            <span className="text-sm font-medium">AI Analysis</span>
            <Badge variant="muted">pending</Badge>
          </div>
        </CardHeader>
        <CardBody>
          <div className="text-sm text-slate-500">
            Root cause analysis hasn't completed for this incident yet.
            <div className="text-xs text-slate-600 mt-1">
              Gemini analysis usually runs within 15 seconds of the incident firing.
            </div>
          </div>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card className="border-violet-900/40 bg-gradient-to-br from-violet-950/20 to-transparent">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-violet-400" />
            <span className="text-sm font-medium">AI Analysis</span>
            <Badge variant={conf.variant}>{conf.label}</Badge>
          </div>
          {incident.ai_analyzed_at && (
            <span className="text-[10px] text-slate-500">
              analyzed {timeAgo(incident.ai_analyzed_at)}
            </span>
          )}
        </div>
      </CardHeader>
      <CardBody className="space-y-4">
        {/* Hypothesis */}
        <div>
          <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-violet-400 mb-1.5">
            <FileText className="w-3 h-3" />
            Root cause hypothesis
          </div>
          <p className="text-sm text-slate-200 leading-relaxed">{incident.root_cause}</p>
        </div>

        {/* Suggested fix */}
        {incident.suggested_fix && (
          <div>
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-emerald-400 mb-1.5">
              <Lightbulb className="w-3 h-3" />
              Suggested fix
            </div>
            <p className="text-sm text-emerald-200 leading-relaxed">{incident.suggested_fix}</p>
          </div>
        )}

        {/* Investigation hints */}
        {Array.isArray(incident.investigation_hints) && incident.investigation_hints.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-sky-400 mb-1.5">
              <Activity className="w-3 h-3" />
              Investigation checklist
            </div>
            <ul className="space-y-1.5">
              {incident.investigation_hints.map((hint, i) => (
                <li key={i} className="flex items-start gap-2 text-xs text-slate-300">
                  <input type="checkbox" className="mt-0.5 accent-violet-500 shrink-0" />
                  <span className="leading-relaxed">{hint}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

// ─── Metric chart ────────────────────────────────────────────────────────────

function MetricChart({ metricKey, metrics, firedAt, baseline }) {
  const meta = METRIC_META[metricKey];
  if (!meta) return null;

  const data = metrics.map(m => ({
    ts: new Date(m.metric_timestamp).getTime(),
    value: m[metricKey],
    label: new Date(m.metric_timestamp).toLocaleTimeString(),
  }));

  const firedTs = new Date(firedAt).getTime();
  const baselineMean = baseline?.mean;
  const upperBound = baselineMean !== undefined && baseline?.stddev !== undefined
    ? baselineMean + 3 * baseline.stddev
    : null;

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-slate-300">{meta.label}</span>
        {baselineMean !== undefined && (
          <span className="text-[10px] text-slate-500 font-mono">
            baseline {baselineMean.toFixed(2)} ± {baseline.stddev?.toFixed(2)}
          </span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={140}>
        <AreaChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id={`grad-${metricKey}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={meta.color} stopOpacity={0.4} />
              <stop offset="100%" stopColor={meta.color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="ts"
            type="number"
            domain={['dataMin', 'dataMax']}
            tick={{ fill: '#64748b', fontSize: 10 }}
            tickFormatter={(t) => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            stroke="#334155"
          />
          <YAxis
            tick={{ fill: '#64748b', fontSize: 10 }}
            stroke="#334155"
          />
          <Tooltip
            contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', fontSize: 11 }}
            labelFormatter={(t) => new Date(t).toLocaleString()}
            formatter={(v) => [v?.toFixed(2) + ' ' + meta.unit, meta.label]}
          />
          {baselineMean !== undefined && (
            <ReferenceLine
              y={baselineMean}
              stroke="#64748b"
              strokeDasharray="3 3"
              strokeWidth={1}
            />
          )}
          {upperBound !== null && (
            <ReferenceLine
              y={upperBound}
              stroke="#ef4444"
              strokeDasharray="2 2"
              strokeWidth={1}
              opacity={0.5}
            />
          )}
          <ReferenceLine
            x={firedTs}
            stroke="#ef4444"
            strokeWidth={2}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke={meta.color}
            strokeWidth={2}
            fill={`url(#grad-${metricKey})`}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
