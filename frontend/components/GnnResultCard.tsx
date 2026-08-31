import type { GnnResult } from '@/lib/artifacts';

const LIFT_DIGITS = 3;

export function GnnResultCard({ gnn }: { gnn: GnnResult }) {
  const lift = gnn.measured_lift_pr_auc;
  const cleared = lift !== null && lift >= gnn.kill_threshold;
  return (
    <article className="rounded-xl sarvam-blue-spotlight p-6 shadow-sm border border-indigo-200/80">
      <p className="text-eyebrow uppercase" style={{ color: 'var(--slate-gray)' }}>
        Graph channel · measured lift against its kill rule
      </p>
      <p className="scotoma-readout mt-6">
        {lift === null ? 'not evaluated' : lift.toFixed(LIFT_DIGITS)}
      </p>
      <p className="mt-2 text-data" style={{ color: 'var(--slate-gray)' }}>
        bar to clear: {gnn.kill_threshold.toFixed(2)}, three absolute PR-AUC points, not three
        percent
      </p>
      <p
        className="mt-6 text-subhead uppercase"
        style={{ color: cleared ? 'var(--ink-black)' : 'var(--signal-orange)' }}
      >
        {cleared ? 'kept in the ensemble' : 'disabled by its own rule'}
      </p>
      <p className="mt-4 max-w-2xl text-body">
        {cleared
          ? 'The graph channel earned its place and stays in the blend. It runs as an offline batch job here; in production it would sit on a stream at 30 seconds to 5 minutes of lag.'
          : 'This is a designed negative result, not an omission. The channel was built, measured against a pre-registered bar, and dropped because it did not earn its place.'}
      </p>
    </article>
  );
}
