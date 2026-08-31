import type { CoverageRow, VectorEntry } from '@/lib/artifacts';
import { percent } from '@/lib/format';

interface VectorDetailPanelProps {
  vector: VectorEntry;
  row: CoverageRow | undefined;
  onClose: () => void;
}

export function VectorDetailPanel({ vector, row, onClose }: VectorDetailPanelProps) {
  return (
    <aside className="mt-8 rounded-xl sarvam-blue-spotlight p-6 shadow-sm border border-indigo-200/80">
      <div className="flex items-start justify-between gap-6 pb-4 border-b border-indigo-100">
        <div>
          <span className="text-xs font-mono font-semibold uppercase tracking-wider text-indigo-700 bg-indigo-50 px-2.5 py-0.5 rounded-full border border-indigo-200/80">
            {vector.id} · Tier {vector.tier} · {vector.status}
          </span>
          <h3 className="mt-3 text-xl font-semibold text-[#1e2033]">{vector.name}</h3>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-full bg-white px-4 py-1.5 text-xs font-semibold text-[#1e2033] border border-slate-300 hover:bg-slate-50 transition-all shadow-2xs"
        >
          Close
        </button>
      </div>

      <div className="mt-6 grid gap-8 lg:grid-cols-2">
        <div>
          <p className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-500">Mechanism</p>
          <p className="mt-1.5 text-sm text-[#1e2033] leading-relaxed">{vector.mechanism}</p>

          <p className="mt-5 text-xs font-mono font-semibold uppercase tracking-wider text-slate-500">What GenAI Changed</p>
          <p className="mt-1.5 text-sm text-[#1e2033] leading-relaxed">{vector.genai_delta}</p>

          <p className="mt-5 text-xs font-mono font-semibold uppercase tracking-wider text-slate-500">Countermeasure</p>
          <p className="mt-1.5 text-sm text-[#1e2033] leading-relaxed">{vector.countermeasure}</p>
        </div>
        <div>
          <p className="text-xs font-mono font-semibold uppercase tracking-wider text-slate-500">Observable Signals</p>
          <ul className="mt-1.5 list-disc pl-5 text-sm text-[#1e2033] space-y-1">
            {vector.observable_signals.map((signal) => (
              <li key={signal}>{signal}</li>
            ))}
          </ul>

          <p className="mt-5 text-xs font-mono font-semibold uppercase tracking-wider text-slate-500">Expected Features</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {vector.expected_features.map((feature) => (
              <span key={feature} className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-mono font-medium text-slate-700">
                {feature}
              </span>
            ))}
          </div>

          <p className="mt-5 text-xs font-mono font-semibold uppercase tracking-wider text-slate-500">Sources</p>
          <p className="mt-1.5 text-xs font-mono text-slate-600">
            {vector.sources.join(' · ')}
          </p>

          <p className="mt-5 text-xs font-mono font-semibold uppercase tracking-wider text-slate-500">Measured Recall</p>
          <p className="mt-1.5 text-sm font-semibold text-[#1e2033]">
            {row && row.recall !== null ? percent(row.recall) : 'No Injector — Documented Only'}
          </p>
        </div>
      </div>

      <p className="mt-6 pt-3 border-t border-indigo-100 text-xs text-slate-500 font-medium leading-relaxed">
        The registry documents mechanism, observable signals, and countermeasure. It contains no
        operational instructions.
      </p>
    </aside>
  );
}
