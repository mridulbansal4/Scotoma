export function AgentModeBadge({ mode }: { mode: string }) {
  const live = mode === 'live';
  return (
    <span
      className={`inline-flex items-center justify-center gap-1.5 rounded-full px-3 py-1.5 text-[11px] font-semibold tracking-wide border leading-none ${
        live
          ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
          : 'bg-[#1e2033] text-white border-[#1e2033]'
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${live ? 'bg-emerald-400 animate-pulse' : 'bg-slate-300'}`} />
      <span>{live ? 'AGENT: LIVE' : 'AGENT: OFFLINE — evolutionary search'}</span>
    </span>
  );
}
