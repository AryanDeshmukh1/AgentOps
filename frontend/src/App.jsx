import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import AppShell from './components/AppShell.jsx';
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
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/pipelines" replace />} />
          <Route path="/pipelines" element={<PipelinesPage />} />
          <Route path="/pipelines/:id" element={<PipelineDetailPage />} />
          <Route path="/approvals" element={<ApprovalsPage />} />
          <Route path="/deployments" element={<DeploymentsPage />} />
          <Route path="/incidents" element={<IncidentsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}