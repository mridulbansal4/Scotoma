import type { RoundRecord } from '@/lib/artifacts';
import { inkScale, readableOn } from '@/lib/format';

interface RecallHeatmapProps {
  rounds: RoundRecord[];
  holdoutVectors: string[];
}

export function RecallHeatmap({ rounds, holdoutVectors }: RecallHeatmapProps) {
  const scored = rounds.filter((record) => Object.keys(record.per_vector_recall).length > 0);
  const vectors = Array.from(
    new Set(scored.flatMap((record) => Object.keys(record.per_vector_recall))),
  ).sort();

  return (
    <div className="payloop-scroll-x">
      <table className="w-full min-w-[720px] border-separate border-spacing-1">
        <thead>
          <tr className="text-eyebrow uppercase" style={{ color: 'var(--slate-gray)' }}>
            <th className="px-3 py-2 text-left">Vector</th>
            {scored.map((record) => (
              <th key={record.round} className="px-3 py-2">
                R{record.round + 1}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {vectors.map((vector) => (
            <tr key={vector}>
              <th
                className="px-3 py-2 text-left text-data"
                style={{
                  borderLeft: holdoutVectors.includes(vector)
                    ? '3px solid var(--link-blue)'
                    : '3px solid transparent',
                }}
              >
                {vector}
                {holdoutVectors.includes(vector) ? (
                  <span
                    className="payloop-chip ml-2"
                    style={{ background: 'var(--link-blue)', color: 'var(--white)' }}
                  >
                    BLIND HOLDOUT
                  </span>
                ) : null}
              </th>
              {scored.map((record) => {
                const value = record.per_vector_recall[vector];
                const present = value !== undefined;
                return (
                  <td
                    key={`${vector}-${record.round}`}
                    className="rounded-button px-3 py-2 text-center text-data tabular-nums"
                    style={{
                      background: inkScale(present ? value : null),
                      color: readableOn(present ? value : null),
                    }}
                  >
                    {present ? value.toFixed(2) : '—'}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
