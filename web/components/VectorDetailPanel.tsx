import type { CoverageRow, VectorEntry } from '@/lib/artifacts';
import { percent } from '@/lib/format';

interface VectorDetailPanelProps {
  vector: VectorEntry;
  row: CoverageRow | undefined;
  onClose: () => void;
}

export function VectorDetailPanel({ vector, row, onClose }: VectorDetailPanelProps) {
  return (
    <aside className="payloop-card mt-8">
      <div className="flex items-start justify-between gap-6">
        <div>
          <p className="text-eyebrow uppercase" style={{ color: 'var(--slate-gray)' }}>
            {vector.id} · tier {vector.tier} · {vector.status}
          </p>
          <h3 className="mt-2">{vector.name}</h3>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-pill border-[1.5px] border-ink px-4 py-2 text-data"
          style={{ minHeight: 44 }}
        >
          Close
        </button>
      </div>

      <div className="mt-8 grid gap-8 lg:grid-cols-2">
        <div>
          <p className="text-subhead uppercase">Mechanism</p>
          <p className="mt-2">{vector.mechanism}</p>
          <p className="mt-6 text-subhead uppercase">What GenAI changed</p>
          <p className="mt-2">{vector.genai_delta}</p>
          <p className="mt-6 text-subhead uppercase">Countermeasure</p>
          <p className="mt-2">{vector.countermeasure}</p>
        </div>
        <div>
          <p className="text-subhead uppercase">Observable signals</p>
          <ul className="mt-2 list-disc pl-5">
            {vector.observable_signals.map((signal) => (
              <li key={signal} className="text-body">
                {signal}
              </li>
            ))}
          </ul>
          <p className="mt-6 text-subhead uppercase">Expected features</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {vector.expected_features.map((feature) => (
              <span key={feature} className="payloop-chip bg-bone">
                {feature}
              </span>
            ))}
          </div>
          <p className="mt-6 text-subhead uppercase">Sources</p>
          <p className="mt-2" style={{ color: 'var(--slate-gray)' }}>
            {vector.sources.join(' · ')}
          </p>
          <p className="mt-6 text-subhead uppercase">Measured recall</p>
          <p className="mt-2">
            {row && row.recall !== null ? percent(row.recall) : 'no injector — documented only'}
          </p>
        </div>
      </div>

      <p className="mt-8 text-data" style={{ color: 'var(--slate-gray)' }}>
        The registry documents mechanism, observable signals, and countermeasure. It contains no
        operational instructions.
      </p>
    </aside>
  );
}
