import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import AppShell from './components/AppShell.jsx';
import PipelinesPage from './pages/PipelinesPage.jsx';
import ApprovalsPage from './pages/ApprovalsPage.jsx';
import DeploymentsPage from './pages/DeploymentsPage.jsx';
import IncidentsPage from './pages/IncidentsPage.jsx';
import SettingsPage from './pages/SettingsPage.jsx';

function PipelineDetailPlaceholder() {
  return (
    <div className="text-slate-400">
      Pipeline detail view ships on Day 28.
      <div className="text-xs text-slate-600 mt-2 font-mono">
        Will render agent timeline, findings, score radar, audit log.
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/pipelines" replace />} />
          <Route path="/pipelines" element={<PipelinesPage />} />
          <Route path="/pipelines/:id" element={<PipelineDetailPlaceholder />} />
          <Route path="/approvals" element={<ApprovalsPage />} />
          <Route path="/deployments" element={<DeploymentsPage />} />
          <Route path="/incidents" element={<IncidentsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}