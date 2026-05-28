import { GitPullRequest } from 'lucide-react';
import { Card, CardBody, EmptyState, PageHeader } from '../components/ui.jsx';

export default function PipelinesPage() {
  return (
    <>
      <PageHeader
        title="Pipelines"
        subtitle="Every pull request that has flowed through the agent system"
      />
      <Card>
        <CardBody>
          <EmptyState
            icon={GitPullRequest}
            title="Pipeline list coming on Day 27"
            hint="Will render live data from GET /api/pipelines with cursor pagination + filters"
          />
        </CardBody>
      </Card>
    </>
  );
}
