import type { Alert } from '@/lib/artifacts';

const CHECKS: { key: string; label: string; expected: boolean }[] = [
  { key: 'attestation_valid', label: 'Agent attestation valid', expected: true },
  { key: 'mandate_in_scope', label: 'Payment within the authorised mandate', expected: true },
  { key: 'nonce_reused', label: 'Mandate credential presented once', expected: false },
  { key: 'cart_hash_match', label: 'Cart hash at intent matches settlement', expected: true },
];

const DOT_SIZE = 10;

export function InvariantPanel({ alert }: { alert: Alert }) {
  return (
    <section className="payloop-card mt-10">
      <p className="text-eyebrow uppercase" style={{ color: 'var(--slate-gray)' }}>
        Agentic invariants · {alert.event_id.slice(0, 8)}
      </p>
      <ul className="mt-6 flex flex-col gap-4">
        {CHECKS.map((check) => {
          const observed = alert.invariants[check.key];
          const holds = observed === check.expected;
          return (
            <li key={check.key} className="flex items-center gap-3">
              <span
                className="inline-block rounded-pill"
                style={{
                  width: DOT_SIZE,
                  height: DOT_SIZE,
                  background: holds ? 'var(--ink-black)' : 'transparent',
                  border: holds ? 'none' : '2px solid var(--signal-orange)',
                }}
                aria-hidden
              />
              <span
                className="text-body"
                style={{ color: holds ? 'var(--ink-black)' : 'var(--signal-orange)' }}
              >
                {check.label}
              </span>
            </li>
          );
        })}
      </ul>
      <p className="mt-6 text-body" style={{ color: 'var(--slate-gray)' }}>
        Every conventional check can pass while the cart digest moves. That single boolean is what
        turns agent-checkout prompt injection into a deterministic detection.
      </p>
    </section>
  );
}
