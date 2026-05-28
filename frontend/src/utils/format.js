// Time helpers
export function timeAgo(iso) {
  if (!iso) return '—';
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return '—';
  const secs = Math.floor((Date.now() - t) / 1000);
  if (secs < 5) return 'just now';
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  const days = Math.floor(secs / 86400);
  return `${days}d ago`;
}

// Decision → badge variant
export function decisionBadge(decision) {
  const map = {
    BLOCK:          { variant: 'danger',  label: 'BLOCK' },
    REQUEST_CHANGES:{ variant: 'warning', label: 'CHANGES' },
    AUTO_APPROVE:   { variant: 'success', label: 'AUTO' },
    PASS:           { variant: 'success', label: 'PASS' },
    PROMOTED:       { variant: 'success', label: 'PROMOTED' },
    PASS_WITH_WARNINGS: { variant: 'info', label: 'PASS+WARN' },
  };
  return map[decision] || { variant: 'default', label: decision || '—' };
}

// Status → badge variant
export function statusBadge(status) {
  const map = {
    running:           { variant: 'info',    label: 'running' },
    complete:          { variant: 'success', label: 'complete' },
    blocked:           { variant: 'danger',  label: 'blocked' },
    awaiting_approval: { variant: 'warning', label: 'awaiting' },
    failed:            { variant: 'danger',  label: 'failed' },
  };
  return map[status] || { variant: 'muted', label: status || '—' };
}

// Risk → badge variant
export function riskBadge(risk) {
  const map = {
    auto: { variant: 'success', label: 'auto' },
    soft: { variant: 'warning', label: 'soft' },
    hard: { variant: 'danger',  label: 'hard' },
  };
  return map[risk] || { variant: 'muted', label: '—' };
}