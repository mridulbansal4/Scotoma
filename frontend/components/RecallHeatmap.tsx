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
    <div className="scotoma-scroll-x overflow-x-auto rounded-xl border border-slate-200/80 bg-white p-4 shadow-sm">
      <table className="w-full min-w-[720px] border-separate border-spacing-1.5">
        <thead>
          <tr className="text-[11px] font-mono font-semibold uppercase tracking-wider text-slate-500">
            <th className="px-3 py-2 text-left">Vector ID</th>
            {scored.map((record) => (
              <th key={record.round} className="px-3 py-2 text-center">
                R{record.round + 1}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {vectors.map((vector) => {
            const isHoldout = holdoutVectors.includes(vector);
            return (
              <tr key={vector}>
                <th className="px-3 py-2 text-left font-mono text-xs font-semibold text-[#1e2033]">
                  <div className="flex items-center gap-2">
                    <span>{vector}</span>
                    {isHoldout ? (
                      <span className="inline-flex items-center rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-semibold text-indigo-700 border border-indigo-200/80">
                        HOLDOUT
                      </span>
                    ) : null}
                  </div>
                </th>
                {scored.map((record) => {
                  const value = record.per_vector_recall[vector];
                  const present = value !== undefined;
                  return (
                    <td
                      key={`${vector}-${record.round}`}
                      className="rounded-md px-3 py-2 text-center text-xs font-mono font-medium tabular-nums transition-transform duration-200 hover:scale-105"
                      style={{
                        background: inkScale(present ? value : null),
                        color: readableOn(present ? value : null),
                      }}
                    >
                      {present ? value.toFixed(2) : '-'}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
