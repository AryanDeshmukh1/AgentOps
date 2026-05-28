import { AlertTriangle } from 'lucide-react';
import { Card, CardBody, EmptyState, PageHeader } from '../components/ui.jsx';

export default function IncidentsPage() {
  return (
    <>
      <PageHeader
        title="Incidents"
        subtitle="Anomaly detections with AI-generated root cause hypotheses"
      />
      <Card>
        <CardBody>
          <EmptyState
            icon={AlertTriangle}
            title="Incidents view coming on Day 31"
            hint="Metric chart with anomaly window highlighted + AI Analysis panel"
          />
        </CardBody>
      </Card>
    </>
  );
}
