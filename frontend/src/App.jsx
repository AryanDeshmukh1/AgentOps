import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import AppShell from './components/AppShell.jsx';
import PipelinesPage from './pages/PipelinesPage.jsx';
import ApprovalsPage from './pages/ApprovalsPage.jsx';
import DeploymentsPage from './pages/DeploymentsPage.jsx';
import IncidentsPage from './pages/IncidentsPage.jsx';
import SettingsPage from './pages/SettingsPage.jsx';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/pipelines" replace />} />
          <Route path="/pipelines" element={<PipelinesPage />} />
          <Route path="/approvals" element={<ApprovalsPage />} />
          <Route path="/deployments" element={<DeploymentsPage />} />
          <Route path="/incidents" element={<IncidentsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
