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
            className="payloop-chip"
            style={{
              background: rejected ? 'var(--signal-orange)' : 'var(--ink-black)',
              color: rejected ? 'var(--white)' : 'var(--canvas-cream)',
            }}
          >
            Round {record.round + 1} · {record.status.replace(/_/g, ' ').toLowerCase()}
          </span>
        );
      })}
    </div>
  );
}
