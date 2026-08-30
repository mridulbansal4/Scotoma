import type { GateLayer } from '@/lib/artifacts';

interface GateCardProps {
  name: string;
  layer: GateLayer;
  headlineMetric: string;
  threshold: string;
  shadow: boolean;
}

const DOT_SIZE = 10;

function readMetric(layer: GateLayer, key: string): string {
  const value = layer[key];
  if (typeof value === 'number') return value.toFixed(value < 1 ? 4 : 2);
  if (value === undefined) return 'INSUFFICIENT_DATA';
  return String(value);
}

export function GateCard({ name, layer, headlineMetric, threshold, shadow }: GateCardProps) {
  const failed = !layer.passed;
  return (
    <article
      className="rounded-stadium bg-lifted p-8 shadow-card"
      style={{ border: failed ? '1.5px solid var(--signal-orange)' : 'none' }}
    >
      <div className="flex items-start justify-between gap-4">
        <p className="text-eyebrow uppercase" style={{ color: 'var(--slate-gray)' }}>
          {name}
        </p>
        {shadow ? (
          <span className="payloop-chip bg-bone" style={{ color: 'var(--slate-gray)' }}>
            SHADOW THIS ROUND
          </span>
        ) : null}
      </div>

      <p className="payloop-readout mt-6">{readMetric(layer, headlineMetric)}</p>
      <p className="mt-2 text-data" style={{ color: 'var(--slate-gray)' }}>
        {threshold}
      </p>

      <p
        className="mt-6 flex items-center gap-2 text-subhead uppercase"
        style={{ color: failed ? 'var(--signal-orange)' : 'var(--ink-black)' }}
      >
        <span
          className="inline-block rounded-pill"
          style={{
            width: DOT_SIZE,
            height: DOT_SIZE,
            background: failed ? 'transparent' : 'var(--ink-black)',
            border: failed ? '2px solid var(--signal-orange)' : 'none',
          }}
          aria-hidden
        />
        {failed ? 'FAIL' : 'PASS'}
      </p>
    </article>
  );
}
