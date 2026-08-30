type Source = 'measured' | 'target' | 'unavailable';

interface LatencyFigureProps {
  label: string;
  value: number;
  source: Source;
  note?: string;
}

const BADGE: Record<Source, { text: string; background: string; color: string }> = {
  measured: { text: 'MEASURED', background: 'var(--ink-black)', color: 'var(--canvas-cream)' },
  target: { text: 'TARGET', background: 'var(--soft-bone)', color: 'var(--slate-gray)' },
  unavailable: {
    text: 'NOT MEASURED',
    background: 'var(--signal-orange)',
    color: 'var(--white)',
  },
};

const DECIMALS = 2;

/** Every millisecond value rendered anywhere on these screens passes through here. */
export function LatencyFigure({ label, value, source, note }: LatencyFigureProps) {
  const badge = BADGE[source];
  return (
    <div className="flex flex-col gap-2">
      <p className="text-eyebrow uppercase" style={{ color: 'var(--slate-gray)' }}>
        {label}
      </p>
      <div className="flex items-baseline gap-3">
        <span className="payloop-readout">
          {source === 'unavailable' ? '—' : `${value.toFixed(DECIMALS)} ms`}
        </span>
        <span
          className="payloop-chip"
          style={{ background: badge.background, color: badge.color }}
        >
          {badge.text}
        </span>
      </div>
      {note ? (
        <p className="text-data" style={{ color: 'var(--slate-gray)' }}>
          {note}
        </p>
      ) : null}
    </div>
  );
}
