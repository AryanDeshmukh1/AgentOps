import { Link } from 'react-router-dom';
import {
  Activity, GitPullRequest, FlaskConical, ShieldCheck, Rocket, AlertTriangle,
  ArrowRight, Github, Linkedin, Sparkles, CheckCircle2, Zap, Database,
  Cpu, Code2, ExternalLink,
} from 'lucide-react';

const AGENTS = [
  {
    icon: GitPullRequest,
    color: 'text-sky-400',
    bg: 'bg-sky-950/30 border-sky-900',
    name: 'ReviewAgent',
    tagline: 'Code review with AI',
    desc: 'Multi-layer scanner (regex + AST + Gemini) finds security issues, scores quality on 6 axes, blocks PRs with critical findings.',
  },
  {
    icon: FlaskConical,
    color: 'text-amber-400',
    bg: 'bg-amber-950/30 border-amber-900',
    name: 'TestAgent',
    tagline: 'Coverage impact analysis',
    desc: 'Maps source changes to test files, flags untested modifications to critical paths, generates test stubs with AI.',
  },
  {
    icon: Rocket,
    color: 'text-emerald-400',
    bg: 'bg-emerald-950/30 border-emerald-900',
    name: 'DeployAgent',
    tagline: 'Blue/green with rollback',
    desc: 'Provisions slots, runs HTTP health checks, gradually shifts traffic 10→50→100% green, auto-rollbacks on failure.',
  },
  {
    icon: AlertTriangle,
    color: 'text-red-400',
    bg: 'bg-red-950/30 border-red-900',
    name: 'IncidentAgent',
    tagline: 'Anomaly detection + AI RCA',
    desc: 'Z-score detection on rolling baseline. When anomalies fire, Gemini hypothesizes root cause from full forensic context.',
  },
];

const DECISIONS = [
  {
    title: 'Atomic state machines',
    body: 'Every state transition is a DynamoDB conditional update. Two simultaneous approvals? Exactly one wins. 5 explicit concurrency tests prove it.',
  },
  {
    title: 'AI off the critical path',
    body: 'Gemini calls bounded by file count, wrapped in timeouts, fire-and-forget for root cause analysis. If AI is down, the deploy still ships.',
  },
  {
    title: 'Fire-and-forget WebSocket',
    body: 'Agents emit events to a broadcaster with 4 channels. Dashboard renders state changes within ~50ms. The DB is source of truth; the UI is a view.',
  },
  {
    title: 'Direction-aware anomaly detection',
    body: 'Error rate spikes UP are bad. Request volume DOWN is bad. Per-metric direction config prevents alert storms while catching real regressions.',
  },
];

const STACK = [
  { label: 'Python 3.12', sub: 'LangGraph + FastAPI' },
  { label: 'Node 22', sub: 'Express + Socket.IO' },
  { label: 'React 18', sub: 'Vite + Tailwind + Recharts' },
  { label: 'AWS DynamoDB', sub: '8 tables, ca-central-1' },
  { label: 'Google Gemini', sub: '2.5 Flash, JSON mode' },
  { label: 'Docker Compose', sub: 'Local dev orchestration' },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Top nav */}
      <header className="border-b border-slate-800/60 sticky top-0 backdrop-blur z-10 bg-slate-950/80">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-emerald-400" />
            <span className="font-bold tracking-tight">AgentOps</span>
            <span className="text-[10px] uppercase tracking-widest text-slate-500 ml-1">demo</span>
          </div>
          <div className="flex items-center gap-2">
            <a
              href="https://github.com/AryanDeshmukh1/AgentOps"
              target="_blank"
              rel="noopener noreferrer"
              className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-900 transition-colors"
            >
              <Github className="w-3.5 h-3.5" />
              Source
            </a>
            <Link
              to="/dashboard"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition-colors"
            >
              Live Dashboard
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-5xl mx-auto px-6 pt-20 pb-16 text-center">
        

        <h1 className="text-4xl sm:text-6xl font-bold tracking-tight leading-tight">
          Four AI agents that ship your PRs<br />
          <span className="text-emerald-400">to production safely.</span>
        </h1>

        <p className="text-base sm:text-lg text-slate-400 mt-6 max-w-2xl mx-auto leading-relaxed">
          AgentOps watches GitHub PRs and runs <strong className="text-slate-200">code review</strong>,
          {' '}<strong className="text-slate-200">test analysis</strong>,
          {' '}<strong className="text-slate-200">blue/green deployment</strong>, and
          {' '}<strong className="text-slate-200">incident response</strong> — all orchestrated by a state machine,
          streamed live to a React dashboard, and powered by Google Gemini.
        </p>

        <div className="flex items-center justify-center gap-3 mt-10 flex-wrap">
          <Link
            to="/dashboard"
            className="flex items-center gap-2 px-5 py-3 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white font-medium transition-colors text-sm shadow-lg shadow-emerald-900/40"
          >
            Try the Live Dashboard
            <ArrowRight className="w-4 h-4" />
          </Link>
          <a
            href="https://github.com/AryanDeshmukh1/AgentOps"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-5 py-3 rounded-md border border-slate-700 hover:bg-slate-900 text-slate-200 font-medium transition-colors text-sm"
          >
            <Github className="w-4 h-4" />
            View Source
          </a>
        </div>

        <div className="flex items-center justify-center gap-6 mt-12 text-xs text-slate-500 flex-wrap">
          <Stat value="4" label="AI agents" />
          <Stat value="9" label="state machine states" />
          <Stat value="23" label="passing tests" />
          <Stat value="8" label="DynamoDB tables" />
          <Stat value="35" label="days to build" />
        </div>
      </section>

      {/* The 4 agents */}
      <section className="max-w-6xl mx-auto px-6 py-16">
        <div className="text-center mb-12">
          <div className="text-[11px] uppercase tracking-widest text-slate-500 mb-2">The agents</div>
          <h2 className="text-2xl sm:text-3xl font-bold">A pipeline of specialized intelligence</h2>
          <p className="text-sm text-slate-400 mt-2 max-w-xl mx-auto">
            Each agent has a single job. Together they form a state machine that takes a PR from open to production.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {AGENTS.map(({ icon: Icon, name, tagline, desc, color, bg }) => (
            <div key={name} className={`p-5 rounded-lg border ${bg}`}>
              <div className="flex items-start gap-3 mb-3">
                <div className="p-2 rounded-md bg-slate-900/60">
                  <Icon className={`w-5 h-5 ${color}`} />
                </div>
                <div className="flex-1">
                  <div className="font-semibold text-slate-100">{name}</div>
                  <div className={`text-xs ${color}`}>{tagline}</div>
                </div>
              </div>
              <p className="text-sm text-slate-400 leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>

        {/* Approval gate between agents */}
        <div className="mt-6 p-4 rounded-lg border border-violet-900 bg-violet-950/20 flex items-center gap-3">
          <div className="p-2 rounded-md bg-slate-900/60">
            <ShieldCheck className="w-5 h-5 text-violet-400" />
          </div>
          <div className="flex-1 text-sm text-slate-400">
            <span className="text-violet-300 font-medium">Plus: Human-in-the-loop approval gate.</span>
            {' '}A risk classifier decides AUTO / SOFT / HARD. SOFT approvals auto-promote after 30 min. HARD requires human review.
          </div>
        </div>
      </section>

      {/* Architecture diagram (text-based) */}
      <section className="max-w-5xl mx-auto px-6 py-16">
        <div className="text-center mb-10">
          <div className="text-[11px] uppercase tracking-widest text-slate-500 mb-2">Architecture</div>
          <h2 className="text-2xl sm:text-3xl font-bold">Three services, eight tables, one source of truth</h2>
        </div>

        <div className="p-6 sm:p-8 rounded-xl border border-slate-800 bg-slate-900/30">
          <pre className="text-[10px] sm:text-xs text-slate-300 leading-relaxed font-mono overflow-x-auto whitespace-pre">
{`   GitHub Webhook
        │
        ▼
   ┌─────────────────┐         ┌──────────────────────┐
   │ Backend (Node)  │ ──HTTP─▶│   Agents (Python)    │
   │ Express + WS    │         │  LangGraph + FastAPI │
   │ Port 4000       │         │  Port 5000           │
   └─────────────────┘         └──────────────────────┘
        │                              │
        │ Socket.IO                    │ All 4 agents
        │ 4 channels                   │ + Gemini API
        ▼                              ▼
   ┌──────────────────────────────────────────┐
   │           AWS DynamoDB (8 tables)         │
   │   Pipelines · Decisions · Approvals       │
   │   Events · Deployments · Metrics · etc.   │
   └──────────────────────────────────────────┘
        ▲
        │ Live updates
        ▼
   ┌─────────────────┐
   │ React Dashboard │
   │ Vite + Tailwind │
   │ (you are here)  │
   └─────────────────┘`}
          </pre>
        </div>
      </section>

      {/* Key engineering decisions */}
      <section className="max-w-5xl mx-auto px-6 py-16">
        <div className="text-center mb-12">
          <div className="text-[11px] uppercase tracking-widest text-slate-500 mb-2">Engineering decisions</div>
          <h2 className="text-2xl sm:text-3xl font-bold">The choices that matter</h2>
          <p className="text-sm text-slate-400 mt-2 max-w-xl mx-auto">
            Not every decision is interesting in interviews. These four are.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {DECISIONS.map((d, i) => (
            <div key={i} className="p-5 rounded-lg border border-slate-800 bg-slate-900/30">
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <div className="font-semibold text-slate-100 text-sm">{d.title}</div>
              </div>
              <p className="text-sm text-slate-400 leading-relaxed pl-6">{d.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Tech stack */}
      <section className="max-w-5xl mx-auto px-6 py-16">
        <div className="text-center mb-10">
          <div className="text-[11px] uppercase tracking-widest text-slate-500 mb-2">Built with</div>
          <h2 className="text-2xl sm:text-3xl font-bold">Production-grade stack</h2>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {STACK.map((s, i) => (
            <div key={i} className="p-4 rounded-lg border border-slate-800 bg-slate-900/30">
              <div className="font-semibold text-slate-100 text-sm">{s.label}</div>
              <div className="text-[11px] text-slate-500 mt-0.5">{s.sub}</div>
            </div>
          ))}
        </div>
      </section>

      {/* CTA + signature */}
      <section className="max-w-3xl mx-auto px-6 py-20 text-center">
        <h2 className="text-2xl sm:text-3xl font-bold mb-3">Want to see it work?</h2>
        <p className="text-slate-400 mb-8">
          Real data from real test runs. Live WebSocket updates. Click around — it's connected to AWS DynamoDB.
        </p>
        <Link
          to="/dashboard"
          className="inline-flex items-center gap-2 px-6 py-3 rounded-md bg-emerald-600 hover:bg-emerald-500 text-white font-medium transition-colors shadow-lg shadow-emerald-900/40"
        >
          Open the Live Dashboard
          <ArrowRight className="w-4 h-4" />
        </Link>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-800/60 mt-10">
        <div className="max-w-6xl mx-auto px-6 py-10 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="text-xs text-slate-500 text-center sm:text-left">
            <div className="font-medium text-slate-300 mb-1">Built by Aryan Deshmukh</div>
            <div>Master's in Information Systems · Northeastern University Toronto · Graduating Sept 2027</div>
            <div className="mt-1">Looking for SDE / DevOps / Cloud co-op roles in Toronto.</div>
          </div>
          <div className="flex items-center gap-3">
            <a
              href="https://github.com/AryanDeshmukh1"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-slate-800 hover:bg-slate-900 text-xs text-slate-300 transition-colors"
            >
              <Github className="w-3.5 h-3.5" />
              GitHub
            </a>
            <a
              href="https://www.linkedin.com/in/aryandeshmukh"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-slate-800 hover:bg-slate-900 text-xs text-slate-300 transition-colors"
            >
              <Linkedin className="w-3.5 h-3.5" />
              LinkedIn
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}

function Stat({ value, label }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="text-emerald-400 font-bold text-sm">{value}</span>
      <span>{label}</span>
    </div>
  );
}