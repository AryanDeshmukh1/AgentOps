import { BrowserRouter, Routes, Route, Navigate, useParams } from 'react-router-dom';
import AppShell from './components/AppShell.jsx';
import LandingPage from './pages/LandingPage.jsx';
import PipelinesPage from './pages/PipelinesPage.jsx';
import PipelineDetailPage from './pages/PipelineDetailPage.jsx';
import ApprovalsPage from './pages/ApprovalsPage.jsx';
import DeploymentsPage from './pages/DeploymentsPage.jsx';
import IncidentsPage from './pages/IncidentsPage.jsx';
import SettingsPage from './pages/SettingsPage.jsx';
import { NotFound } from './components/Skeleton.jsx';


export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public landing page */}
        <Route path="/" element={<LandingPage />} />

        {/* Dashboard pages — all wrapped in AppShell */}
        <Route path="/dashboard" element={<AppShell />}>
          <Route index element={<Navigate to="/dashboard/pipelines" replace />} />
          <Route path="pipelines" element={<PipelinesPage />} />
          <Route path="pipelines/:id" element={<PipelineDetailPage />} />
          <Route path="approvals" element={<ApprovalsPage />} />
          <Route path="deployments" element={<DeploymentsPage />} />
          <Route path="incidents" element={<IncidentsPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<NotFound />} />
        </Route>

        {/* Legacy redirects — old links still work */}
        <Route path="/pipelines" element={<Navigate to="/dashboard/pipelines" replace />} />
        <Route path="/pipelines/:id" element={<LegacyPipelineRedirect />} />
        <Route path="/approvals" element={<Navigate to="/dashboard/approvals" replace />} />
        <Route path="/deployments" element={<Navigate to="/dashboard/deployments" replace />} />
        <Route path="/incidents" element={<Navigate to="/dashboard/incidents" replace />} />
        <Route path="/settings" element={<Navigate to="/dashboard/settings" replace />} />

        {/* Catch-all */}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}

// Helper to preserve :id params on legacy URLs
function LegacyPipelineRedirect() {
  const { id } = useParams();
  return <Navigate to={`/dashboard/pipelines/${id}`} replace />;
}