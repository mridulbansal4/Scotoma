export function AgentModeBadge({ mode }: { mode: string }) {
  const live = mode === 'live';
  return (
    <span
      className="payloop-chip"
      style={{
        background: live ? 'var(--ink-black)' : 'var(--signal-light)',
        color: live ? 'var(--canvas-cream)' : 'var(--ink-black)',
      }}
    >
      {live ? 'AGENT: LIVE' : 'AGENT: OFFLINE — evolutionary search'}
    </span>
  );
}
