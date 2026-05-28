import { Rocket } from 'lucide-react';
import { Card, CardBody, EmptyState, PageHeader } from '../components/ui.jsx';

export default function DeploymentsPage() {
  return (
    <>
      <PageHeader
        title="Deployments"
        subtitle="Live blue/green traffic shifting and rollback controls"
      />
      <Card>
        <CardBody>
          <EmptyState
            icon={Rocket}
            title="Deployment visualizer coming on Day 30"
            hint="Animated blue/green bars updating live from deployment.traffic_shifted events"
          />
        </CardBody>
      </Card>
    </>
  );
}
