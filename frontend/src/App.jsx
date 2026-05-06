import { useState, useEffect } from 'react';
import { Activity, Cpu, Shield, Zap } from 'lucide-react';

function App() {
  const [backendStatus, setBackendStatus] = useState('checking...');
  const [agentsStatus, setAgentsStatus] = useState('checking...');

  useEffect(() => {
    // Check backend health
    fetch('http://localhost:4000/api/health')
      .then(res => res.json())
      .then(data => setBackendStatus(data.status))
      .catch(() => setBackendStatus('offline'));

    // Check agents health
    fetch('http://localhost:5000/health')
      .then(res => res.json())
      .then(data => setAgentsStatus(data.status))
      .catch(() => setAgentsStatus('offline'));
  }, []);

  const StatusBadge = ({ status }) => {
    const isHealthy = status === 'healthy';
    const colorClass = isHealthy
      ? 'bg-green-100 text-green-800'
      : status === 'checking...'
      ? 'bg-yellow-100 text-yellow-800'
      : 'bg-red-100 text-red-800';
    return (
      <span className={`px-3 py-1 rounded-full text-sm font-medium ${colorClass}`}>
        {status}
      </span>
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50">
      <div className="max-w-6xl mx-auto px-6 py-12">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-primary mb-3">AgentOps</h1>
          <p className="text-xl text-slate-600">
            Multi-Agent DevOps Pipeline Orchestrator
          </p>
        </div>

        {/* Service Status */}
        <div className="bg-white rounded-2xl shadow-lg p-8 mb-8">
          <h2 className="text-2xl font-semibold text-slate-800 mb-6">
            Service Status
          </h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
              <div className="flex items-center gap-3">
                <Activity className="w-5 h-5 text-primary" />
                <span className="font-medium text-slate-700">Frontend (Vite + React)</span>
              </div>
              <StatusBadge status="healthy" />
            </div>
            <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
              <div className="flex items-center gap-3">
                <Cpu className="w-5 h-5 text-primary" />
                <span className="font-medium text-slate-700">Backend (Node.js + Express)</span>
              </div>
              <StatusBadge status={backendStatus} />
            </div>
            <div className="flex items-center justify-between p-4 bg-slate-50 rounded-lg">
              <div className="flex items-center gap-3">
                <Zap className="w-5 h-5 text-primary" />
                <span className="font-medium text-slate-700">Agent System (Python + FastAPI)</span>
              </div>
              <StatusBadge status={agentsStatus} />
            </div>
          </div>
        </div>

        {/* Coming Soon */}
        <div className="bg-white rounded-2xl shadow-lg p-8">
          <div className="flex items-center gap-3 mb-6">
            <Shield className="w-6 h-6 text-primary" />
            <h2 className="text-2xl font-semibold text-slate-800">
              Build Progress
            </h2>
          </div>
          <div className="space-y-3">
            <ProgressItem label="Day 1: Setup + Scaffold" status="in-progress" />
            <ProgressItem label="Day 2-12: ReviewAgent" status="pending" />
            <ProgressItem label="Day 13-17: TestAgent" status="pending" />
            <ProgressItem label="Day 18-21: LangGraph Orchestrator + Approvals" status="pending" />
            <ProgressItem label="Day 22-25: DeployAgent" status="pending" />
            <ProgressItem label="Day 26-28: IncidentAgent" status="pending" />
            <ProgressItem label="Day 29-33: Full Dashboard" status="pending" />
            <ProgressItem label="Day 34-35: Deploy + Document" status="pending" />
          </div>
        </div>
      </div>
    </div>
  );
}

function ProgressItem({ label, status }) {
  const icons = {
    'completed': '✅',
    'in-progress': '🚧',
    'pending': '⏳',
  };
  return (
    <div className="flex items-center gap-3 text-slate-700">
      <span className="text-xl">{icons[status]}</span>
      <span className={status === 'completed' ? 'line-through text-slate-400' : ''}>
        {label}
      </span>
    </div>
  );
}

export default App;
