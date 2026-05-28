import { useOutletContext } from 'react-router-dom';
import { Card, CardBody, CardHeader, PageHeader, Badge } from '../components/ui.jsx';

export default function SettingsPage() {
  const { status } = useOutletContext();
  const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:4000';
  const wsUrl  = import.meta.env.VITE_WS_URL || 'http://localhost:4000';

  return (
    <>
      <PageHeader title="Settings" subtitle="Environment + connection diagnostics" />

      <div className="space-y-4 max-w-2xl">
        <Card>
          <CardHeader>
            <div className="text-sm font-medium">Connection</div>
          </CardHeader>
          <CardBody>
            <Row label="WebSocket" value={
              <Badge variant={status === 'connected' ? 'success' : 'danger'}>{status}</Badge>
            } />
            <Row label="API base"     value={<code className="text-xs text-slate-400">{apiUrl}</code>} />
            <Row label="WebSocket URL" value={<code className="text-xs text-slate-400">{wsUrl}</code>} />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <div className="text-sm font-medium">Build</div>
          </CardHeader>
          <CardBody>
            <Row label="Version"     value="0.5.0 (Day 26 — Phase 5 starts)" />
            <Row label="Environment" value={<Badge variant="info">development</Badge>} />
            <Row label="Authentication" value={<Badge variant="muted">shared token (dev only)</Badge>} />
          </CardBody>
        </Card>
      </div>
    </>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-slate-800 last:border-0">
      <div className="text-sm text-slate-400">{label}</div>
      <div>{value}</div>
    </div>
  );
}
