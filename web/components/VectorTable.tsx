'use client';

import type { CoverageRow } from '@/lib/artifacts';
import { percent } from '@/lib/format';

interface VectorTableProps {
  rows: CoverageRow[];
  selected: string | null;
  onSelect: (vectorId: string) => void;
}

const RECALL_BAR_WIDTH = 72;
// Rows without an injector are documented, not simulated. They are shown, not hidden.
const DOCUMENTED_ONLY_OPACITY = 0.55;

function StatusChip({ status }: { status: CoverageRow['status'] }) {
  const emphasis = status === 'documented';
  return (
    <span
      className="payloop-chip"
      style={{
        background: emphasis ? 'var(--ink-black)' : 'var(--soft-bone)',
        color: emphasis ? 'var(--canvas-cream)' : 'var(--slate-gray)',
      }}
    >
      {status}
    </span>
  );
}

function RecallBar({ value }: { value: number | null }) {
  if (value === null) {
    return (
      <span className="text-data" style={{ color: 'var(--dust-taupe)' }}>
        not simulated
      </span>
    );
  }
  return (
    <span className="flex items-center gap-2">
      <span
        className="inline-block h-2 rounded-pill"
        style={{ width: RECALL_BAR_WIDTH, background: 'var(--soft-bone)' }}
      >
        <span
          className="block h-2 rounded-pill"
          style={{ width: `${Math.round(value * RECALL_BAR_WIDTH)}px`, background: 'var(--ink-black)' }}
        />
      </span>
      <span className="text-data tabular-nums">{percent(value, 0)}</span>
    </span>
  );
}

export function VectorTable({ rows, selected, onSelect }: VectorTableProps) {
  return (
    <div className="payloop-scroll-x mt-8 rounded-stadium bg-lifted p-2 shadow-card">
      <table className="w-full min-w-[840px] border-collapse text-left">
        <thead>
          <tr className="text-eyebrow uppercase" style={{ color: 'var(--slate-gray)' }}>
            <th className="px-4 py-4">ID</th>
            <th className="px-4 py-4">Vector</th>
            <th className="px-4 py-4">Rails</th>
            <th className="px-4 py-4">Tier</th>
            <th className="px-4 py-4">Status</th>
            <th className="px-4 py-4">Injector</th>
            <th className="px-4 py-4">Recall</th>
            <th className="px-4 py-4">Holdout</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr
              key={row.vector_id}
              onClick={() => onSelect(row.vector_id)}
              className="cursor-pointer align-middle"
              style={{
                background:
                  selected === row.vector_id
                    ? 'var(--ghost-cream)'
                    : index % 2 === 0
                      ? 'transparent'
                      : 'var(--soft-bone)',
                opacity: row.has_injector ? 1 : DOCUMENTED_ONLY_OPACITY,
                borderLeft: row.has_injector ? 'none' : '3px solid var(--dust-taupe)',
              }}
            >
              <td className="px-4 py-4 text-data tabular-nums">{row.vector_id}</td>
              <td className="px-4 py-4 text-body">{row.name}</td>
              <td className="px-4 py-4 text-data" style={{ color: 'var(--slate-gray)' }}>
                {row.rails.join(', ')}
              </td>
              <td className="px-4 py-4 text-data tabular-nums">{row.tier}</td>
              <td className="px-4 py-4">
                <StatusChip status={row.status} />
              </td>
              <td className="px-4 py-4 text-data">{row.has_injector ? 'live' : '—'}</td>
              <td className="px-4 py-4">
                <RecallBar value={row.recall} />
              </td>
              <td className="px-4 py-4">
                {row.blind_holdout ? (
                  <span
                    className="payloop-chip"
                    style={{ background: 'var(--link-blue)', color: 'var(--white)' }}
                  >
                    BLIND HOLDOUT
                  </span>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
