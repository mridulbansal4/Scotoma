import type { Alert } from '@/lib/artifacts';
import { CheckCircle2, XCircle } from 'lucide-react';

const CHECKS: { key: string; label: string; expected: boolean }[] = [
  { key: 'attestation_valid', label: 'Agent attestation valid', expected: true },
  { key: 'mandate_in_scope', label: 'Payment within the authorised mandate', expected: true },
  { key: 'nonce_reused', label: 'Mandate credential presented once', expected: false },
  { key: 'cart_hash_match', label: 'Cart hash at intent matches settlement', expected: true },
];

export function InvariantPanel({ alert }: { alert: Alert }) {
  return (
    <section className="rounded-xl sarvam-blue-spotlight p-6 shadow-sm border border-indigo-200/80 mt-10">
      <p className="text-[11px] font-mono font-semibold uppercase tracking-wider text-slate-500">
        Agentic Invariants · Event {alert.event_id.slice(0, 8)}
      </p>
      <ul className="mt-5 flex flex-col gap-3">
        {CHECKS.map((check) => {
          const observed = alert.invariants[check.key];
          const holds = observed === check.expected;
          return (
            <li key={check.key} className="flex items-center gap-3">
              {holds ? (
                <CheckCircle2 size={18} className="text-emerald-600 shrink-0" />
              ) : (
                <XCircle size={18} className="text-rose-600 shrink-0" />
              )}
              <span
                className={`text-sm font-medium ${
                  holds ? 'text-[#1e2033]' : 'text-rose-700 font-semibold'
                }`}
              >
                {check.label}
              </span>
            </li>
          );
        })}
      </ul>
      <p className="mt-5 pt-3 border-t border-indigo-100 text-xs text-slate-500 font-medium leading-relaxed">
        Every conventional check can pass while the cart digest moves. That single boolean is what
        turns agent-checkout prompt injection into a deterministic detection.
      </p>
    </section>
  );
}
