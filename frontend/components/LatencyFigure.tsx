type Source = 'measured' | 'target' | 'unavailable';

interface LatencyFigureProps {
  label: string;
  value: number;
  source: Source;
  note?: string;
}

const BADGE: Record<Source, { text: string; bg: string; color: string; border: string }> = {
  measured: { text: 'MEASURED', bg: 'bg-indigo-100/80', color: 'text-indigo-950', border: 'border-indigo-200' },
  target: { text: 'TARGET', bg: 'bg-slate-100', color: 'text-slate-700', border: 'border-slate-200' },
  unavailable: {
    text: 'NOT MEASURED',
    bg: 'bg-amber-100',
    color: 'text-amber-900',
    border: 'border-amber-200',
  },
};

const DECIMALS = 2;

/** Every millisecond value rendered anywhere on these screens passes through here. */
export function LatencyFigure({ label, value, source, note }: LatencyFigureProps) {
  const badge = BADGE[source];
  return (
    <div className="flex flex-col gap-2">
      <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
        {label}
      </p>
      <div className="flex items-baseline gap-3">
        <span className="font-mono text-3xl font-bold tracking-tight text-[#1e2033]">
          {source === 'unavailable' ? '-' : `${value.toFixed(DECIMALS)} ms`}
        </span>
        <span
          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold border ${badge.bg} ${badge.color} ${badge.border}`}
        >
          {badge.text}
        </span>
      </div>
      {note ? (
        <p className="text-xs text-slate-500 font-medium">
          {note}
        </p>
      ) : null}
    </div>
  );
}
