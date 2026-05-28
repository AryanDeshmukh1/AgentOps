import { ShieldCheck } from 'lucide-react';
import { Card, CardBody, EmptyState, PageHeader } from '../components/ui.jsx';

export default function ApprovalsPage() {
  return (
    <>
      <PageHeader
        title="Approvals"
        subtitle="Pending human-in-the-loop decisions with countdown timers"
      />
      <Card>
        <CardBody>
          <EmptyState
            icon={ShieldCheck}
            title="Approvals queue coming on Day 29"
            hint="SOFT shows minutes to auto-promote · HARD shows hours to expire"
          />
        </CardBody>
      </Card>
    </>
  );
}
