import type { RoundRecord } from '@/lib/artifacts';
import { percent, rate } from '@/lib/format';

const REJECTED = 'FIDELITY_REJECTED';

export function RoundTimeline({ rounds }: { rounds: RoundRecord[] }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {rounds.map((record) => {
        const rejected = record.status === REJECTED;
        return (
          <article
            key={record.round}
            className="rounded-stadium bg-lifted p-6"
            style={{ border: rejected ? '1.5px solid var(--signal-orange)' : 'none' }}
          >
            <p className="text-eyebrow uppercase" style={{ color: 'var(--slate-gray)' }}>
              Round {record.round + 1}
            </p>
            <p
              className="mt-2 text-subhead uppercase"
              style={{ color: rejected ? 'var(--signal-orange)' : 'var(--ink-black)' }}
            >
              {record.status.replace(/_/g, ' ')}
            </p>
            <p className="payloop-readout mt-4">
              {rejected ? rate(record.fidelity_composite, 2) : percent(record.evasion_active)}
            </p>
            <p className="mt-2 text-data" style={{ color: 'var(--slate-gray)' }}>
              {rejected
                ? 'behavioural composite at rejection'
                : `evasion on the active campaign · blind ${percent(record.evasion_blind)}`}
            </p>
            <p className="mt-4 text-data" style={{ color: 'var(--slate-gray)' }}>
              {record.proposals_valid}/{record.proposals_total} proposals valid ·{' '}
              {record.campaigns.length} campaigns
            </p>
            {record.suspicious_pr_auc ? (
              <p className="mt-3 text-data" style={{ color: 'var(--signal-orange)' }}>
                SUSPICIOUS_PR_AUC — treated as a defect, not a result.
              </p>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}
