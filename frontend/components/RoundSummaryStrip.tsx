import type { RoundRecord } from '@/lib/artifacts';

const REJECTED = 'FIDELITY_REJECTED';

export function RoundSummaryStrip({ rounds }: { rounds: RoundRecord[] }) {
  return (
    <div className="flex flex-wrap gap-2">
      {rounds.map((record) => {
        const rejected = record.status === REJECTED;
        return (
          <span
            key={record.round}
            className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold border transition-all ${
              rejected
                ? 'bg-amber-50 text-amber-900 border-amber-200'
                : 'bg-indigo-50/80 text-indigo-950 border-indigo-200/80 hover:bg-indigo-100/60'
            }`}
          >
            Round {record.round + 1} · {record.status.replace(/_/g, ' ').toLowerCase()}
          </span>
        );
      })}
    </div>
  );
}
