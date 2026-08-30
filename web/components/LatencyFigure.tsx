type Source = 'measured' | 'target';

interface LatencyFigureProps {
  label: string;
  value: number;
  source: Source;
}

const BADGE: Record<Source, { text: string; background: string; color: string }> = {
  measured: { text: 'MEASURED', background: 'var(--ink-black)', color: 'var(--canvas-cream)' },
  target: { text: 'TARGET', background: 'var(--soft-bone)', color: 'var(--slate-gray)' },
};

const DECIMALS = 2;

/** Every millisecond value rendered anywhere on these screens passes through here. */
export function LatencyFigure({ label, value, source }: LatencyFigureProps) {
  const badge = BADGE[source];
  return (
    <div className="flex flex-col gap-2">
      <p className="text-eyebrow uppercase" style={{ color: 'var(--slate-gray)' }}>
        {label}
      </p>
      <div className="flex items-baseline gap-3">
        <span className="payloop-readout">{value.toFixed(DECIMALS)} ms</span>
        <span
          className="payloop-chip"
          style={{ background: badge.background, color: badge.color }}
        >
          {badge.text}
        </span>
      </div>
    </div>
  );
}
