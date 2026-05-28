import { useEffect, useState } from 'react';
import { useParams, useLocation, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft, GitPullRequest, GitCommit, User, Calendar,
  Search, FlaskConical, ShieldCheck, Rocket, AlertTriangle, ChevronDown,
} from 'lucide-react';
import clsx from 'clsx';
import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer,
} from 'recharts';
import { Card, CardHeader, CardBody, Badge, EmptyState, PageHeader } from '../components/ui.jsx';
import { api } from '../utils/apiClient.js';
import { timeAgo, decisionBadge, statusBadge, riskBadge } from '../utils/format.js';

const AGENT_META = {
  ReviewAgent:   { icon: Search,        label: 'Review',   color: 'text-sky-400' },
  TestAgent:     { icon: FlaskConical,  label: 'Test',     color: 'text-amber-400' },
  ApprovalGate:  { icon: ShieldCheck,   label: 'Approval', color: 'text-violet-400' },
  DeployAgent:   { icon: Rocket,        label: 'Deploy',   color: 'text-emerald-400' },
  IncidentAgent: { icon: AlertTriangle, label: 'Incident', color: 'text-red-400' },
};

const SEVERITY_META = {
  critical: { variant: 'danger',  rank: 0 },
  high:     { variant: 'warning', rank: 1 },
  medium:   { variant: 'info',    rank: 2 },
  low:      { variant: 'muted',   rank: 3 },
};

export default function PipelineDetailPage() {
  const { id } = useParams();
  const location = useLocation();
  const navigate = useNavigate();

  // Pipeline metadata may have been passed via list-page navigation
  const pipeline = location.state?.pipeline;

  const [decisions, setDecisions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const response = await api.get(`/api/pipelines/${encodeURIComponent(id)}/decisions`);
        if (!cancelled) setDecisions(response.data.decisions || []);
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [id]);

  // Sort decisions by timestamp for the timeline
  const orderedDecisions = [...decisions].sort(
    (a, b) => new Date(a.timestamp) - new Date(b.timestamp)
  );

  const reviewDecision = decisions.find(d => d.agent_name === 'ReviewAgent');
  const findings = reviewDecision?.report?.findings || [];
  const scores = reviewDecision?.report?.scores || null;

  return (
    <>
      <button
        onClick={() => navigate('/pipelines')}
        className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 mb-4 transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        Back to pipelines
      </button>

      {/* Hero */}
      <PipelineHero pipeline={pipeline} pipelineId={id} />

      {loading ? (
        <Card className="mt-6"><CardBody>
          <div className="text-sm text-slate-400">Loading agent decisions…</div>
        </CardBody></Card>
      ) : error ? (
        <Card className="mt-6"><CardBody>
          <div className="text-sm text-red-400 font-mono">Error: {error}</div>
        </CardBody></Card>
      ) : decisions.length === 0 ? (
        <Card className="mt-6"><CardBody>
          <EmptyState
            icon={GitPullRequest}
            title="No agent decisions found"
            hint="This pipeline may still be running"
          />
        </CardBody></Card>
      ) : (
        <>
          {/* Agent timeline */}
          <div className="mt-6">
            <AgentTimeline decisions={orderedDecisions} />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
            {/* Score radar */}
            {scores && (
              <Card className="lg:col-span-1">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Score breakdown</span>
                    <Badge variant={scores.overall >= 80 ? 'success' : scores.overall >= 60 ? 'warning' : 'danger'}>
                      overall {scores.overall}
                    </Badge>
                  </div>
                </CardHeader>
                <CardBody>
                  <ScoreRadar scores={scores} />
                </CardBody>
              </Card>
            )}

            {/* Findings */}
            <Card className={clsx(scores ? 'lg:col-span-2' : 'lg:col-span-3')}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Findings</span>
                  <FindingsCounts findings={findings} />
                </div>
              </CardHeader>
              <CardBody className="p-0">
                {findings.length === 0 ? (
                  <div className="p-6 text-sm text-slate-500">No findings reported.</div>
                ) : (
                  <FindingsList findings={findings} />
                )}
              </CardBody>
            </Card>
          </div>

          {/* Audit trail */}
          <Card className="mt-6">
            <CardHeader>
              <div className="text-sm font-medium">Agent audit trail</div>
            </CardHeader>
            <CardBody className="p-0">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-800">
                    <th className="text-left px-4 py-2 font-medium">Agent</th>
                    <th className="text-left px-4 py-2 font-medium">Decision</th>
                    <th className="text-right px-4 py-2 font-medium">Duration</th>
                    <th className="text-right px-4 py-2 font-medium">When</th>
                  </tr>
                </thead>
                <tbody>
                  {orderedDecisions.map((d, i) => {
                    const meta = AGENT_META[d.agent_name] || { icon: GitCommit, label: d.agent_name, color: 'text-slate-400' };
                    const Icon = meta.icon;
                    const dec = decisionBadge(d.report?.decision);
                    return (
                      <tr key={i} className="border-b border-slate-800 last:border-0">
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <Icon className={clsx('w-4 h-4', meta.color)} />
                            <span className="text-slate-200">{d.agent_name}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3"><Badge variant={dec.variant}>{dec.label}</Badge></td>
                        <td className="px-4 py-3 text-right font-mono text-slate-400 text-xs">
                          {d.report?.duration_ms ? `${d.report.duration_ms}ms` : '—'}
                        </td>
                        <td className="px-4 py-3 text-right text-xs text-slate-500">{timeAgo(d.timestamp)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </CardBody>
          </Card>
        </>
      )}
    </>
  );
}

// ─── Hero ────────────────────────────────────────────────────────────────────

function PipelineHero({ pipeline, pipelineId }) {
  if (!pipeline) {
    return (
      <Card>
        <CardBody>
          <div className="text-sm text-slate-400">Pipeline metadata not available — open this from the list to populate it.</div>
          <code className="text-xs text-slate-600 mt-1 block">{pipelineId}</code>
        </CardBody>
      </Card>
    );
  }
  const dec = decisionBadge(pipeline.decision);
  const st = statusBadge(pipeline.status);
  const rk = riskBadge(pipeline.risk_level);

  return (
    <Card>
      <CardBody>
        <div className="flex items-start justify-between gap-6">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 text-xs text-slate-500 font-mono mb-1">
              <GitPullRequest className="w-3.5 h-3.5" />
              <span>PR #{pipeline.pr_number}</span>
              <span>·</span>
              <span>{pipeline.repo}</span>
            </div>
            <h2 className="text-xl font-semibold text-slate-100">{pipeline.pr_title}</h2>
            <div className="flex items-center gap-4 mt-3 text-xs text-slate-400 flex-wrap">
              <span className="flex items-center gap-1"><User className="w-3 h-3" /> {pipeline.pr_author}</span>
              <span className="flex items-center gap-1"><GitCommit className="w-3 h-3" /> {pipeline.head_sha?.slice(0, 7)}</span>
              <span className="flex items-center gap-1"><Calendar className="w-3 h-3" /> {timeAgo(pipeline.created_at)}</span>
            </div>
          </div>
          <div className="flex flex-col items-end gap-2">
            <Badge variant={dec.variant}>{dec.label}</Badge>
            <Badge variant={st.variant}>{st.label}</Badge>
            <Badge variant={rk.variant}>{rk.label}</Badge>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

// ─── Timeline ────────────────────────────────────────────────────────────────

function AgentTimeline({ decisions }) {
  return (
    <Card>
      <CardHeader>
        <div className="text-sm font-medium">Agent timeline</div>
      </CardHeader>
      <CardBody>
        <div className="flex items-center gap-2 flex-wrap">
          {decisions.map((d, i) => {
            const meta = AGENT_META[d.agent_name] || { icon: GitCommit, label: d.agent_name, color: 'text-slate-400' };
            const Icon = meta.icon;
            const dec = decisionBadge(d.report?.decision);
            return (
              <div key={i} className="flex items-center gap-2">
                <div className="flex flex-col items-center gap-1.5 min-w-[120px]">
                  <div className={clsx(
                    'w-12 h-12 rounded-full bg-slate-900 border-2 flex items-center justify-center',
                    'border-slate-700',
                  )}>
                    <Icon className={clsx('w-5 h-5', meta.color)} />
                  </div>
                  <div className="text-xs font-medium text-slate-200">{meta.label}</div>
                  <Badge variant={dec.variant}>{dec.label}</Badge>
                </div>
                {i < decisions.length - 1 && (
                  <div className="w-12 h-px bg-slate-700" />
                )}
              </div>
            );
          })}
        </div>
      </CardBody>
    </Card>
  );
}

// ─── Score radar ─────────────────────────────────────────────────────────────

function ScoreRadar({ scores }) {
  const data = [
    { axis: 'Security',      value: scores.security ?? 0 },
    { axis: 'Quality',       value: scores.code_quality ?? 0 },
    { axis: 'Performance',   value: scores.performance ?? 0 },
    { axis: 'Architecture',  value: scores.architecture ?? 0 },
    { axis: 'Test Impact',   value: scores.test_impact ?? 0 },
    { axis: 'Documentation', value: scores.documentation ?? 0 },
  ];
  return (
    <ResponsiveContainer width="100%" height={260}>
      <RadarChart data={data}>
        <PolarGrid stroke="#334155" />
        <PolarAngleAxis dataKey="axis" tick={{ fill: '#94a3b8', fontSize: 11 }} />
        <PolarRadiusAxis angle={90} domain={[0, 100]} tick={false} stroke="#334155" />
        <Radar dataKey="value" stroke="#10b981" fill="#10b981" fillOpacity={0.3} />
      </RadarChart>
    </ResponsiveContainer>
  );
}

// ─── Findings ────────────────────────────────────────────────────────────────

function FindingsCounts({ findings }) {
  const counts = findings.reduce((acc, f) => {
    acc[f.severity] = (acc[f.severity] || 0) + 1;
    return acc;
  }, {});
  return (
    <div className="flex items-center gap-1.5">
      {['critical', 'high', 'medium', 'low'].map(sev => {
        if (!counts[sev]) return null;
        return (
          <Badge key={sev} variant={SEVERITY_META[sev].variant}>
            {counts[sev]} {sev}
          </Badge>
        );
      })}
    </div>
  );
}

function FindingsList({ findings }) {
  // Sort by severity rank then by file/line
  const sorted = [...findings].sort((a, b) => {
    const rankA = SEVERITY_META[a.severity]?.rank ?? 99;
    const rankB = SEVERITY_META[b.severity]?.rank ?? 99;
    if (rankA !== rankB) return rankA - rankB;
    return (a.file || '').localeCompare(b.file || '') || (a.line || 0) - (b.line || 0);
  });

  return (
    <div className="divide-y divide-slate-800">
      {sorted.map((f, i) => (
        <FindingRow key={i} finding={f} />
      ))}
    </div>
  );
}

function FindingRow({ finding }) {
  const [open, setOpen] = useState(false);
  const sev = SEVERITY_META[finding.severity] || SEVERITY_META.low;

  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-4 py-3 flex items-center gap-3 hover:bg-slate-800/40 text-left transition-colors"
      >
        <Badge variant={sev.variant}>{finding.severity}</Badge>
        <div className="flex-1 min-w-0">
          <div className="text-sm text-slate-200 truncate">{finding.title}</div>
          <div className="text-[11px] text-slate-500 font-mono mt-0.5">
            {finding.file}:{finding.line} · {finding.category}
            {finding.detection_method === 'ai' && <span className="ml-2 text-violet-400">AI</span>}
          </div>
        </div>
        <ChevronDown className={clsx('w-4 h-4 text-slate-500 transition-transform', open && 'rotate-180')} />
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-3">
          {finding.description && (
            <div className="text-sm text-slate-400">{finding.description}</div>
          )}
          {finding.code_snippet && (
            <pre className="bg-slate-950 border border-slate-800 rounded p-3 text-xs text-slate-300 font-mono overflow-x-auto">
              {finding.code_snippet}
            </pre>
          )}
          {finding.suggested_fix && (
            <div>
              <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Suggested fix</div>
              <div className="text-sm text-emerald-300">{finding.suggested_fix}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
