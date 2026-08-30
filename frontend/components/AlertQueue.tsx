'use client';

import type { Alert, LadderBands } from '@/lib/artifacts';
import { rate } from '@/lib/format';

import { EmptyState } from './EmptyState';
import { ReasonCodes } from './ReasonCodes';

interface AlertQueueProps {
  alerts: Alert[];
  threshold: number;
  bands: LadderBands;
  selected: string | null;
  onSelect: (eventId: string) => void;
}

// The queue is virtualised by slicing: 200 committed rows never need windowing beyond this.
const VISIBLE_ROWS = 60;

function bandLabel(score: number, bands: LadderBands): string {
  if (score < bands.approve_max) return 'APPROVE';
  if (score < bands.stepup_max) return 'STEP_UP';
  if (score < bands.hold_max) return 'HOLD';
  return 'DECLINE_REVIEW';
}

export function AlertQueue({ alerts, threshold, bands, selected, onSelect }: AlertQueueProps) {
  const visible = alerts.filter((alert) => alert.score >= threshold).slice(0, VISIBLE_ROWS);
  if (!visible.length) {
    return <EmptyState message="No alerts above the current threshold." />;
  }

  return (
    <ul className="flex flex-col gap-3">
      {visible.map((alert) => {
        const band = bandLabel(alert.score, bands);
        const injection = alert.invariants.cart_hash_match === false;
        return (
          <li key={alert.event_id}>
            <button
              type="button"
              onClick={() => onSelect(alert.event_id)}
              className="w-full rounded-stadium bg-lifted p-6 text-left shadow-lift"
              style={{
                border:
                  selected === alert.event_id
                    ? '1.5px solid var(--ink-black)'
                    : injection
                      ? '1.5px solid var(--signal-orange)'
                      : '1.5px solid transparent',
              }}
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="payloop-chip bg-bone">{alert.rail}</span>
                  {alert.vector_id ? (
                    <span
                      className="payloop-chip"
                      style={{ background: 'var(--ink-black)', color: 'var(--canvas-cream)' }}
                    >
                      {alert.vector_id}
                    </span>
                  ) : null}
                  <span className="text-data" style={{ color: 'var(--slate-gray)' }}>
                    {alert.event_ts.slice(0, 19).replace('T', ' ')}
                  </span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-card tabular-nums">{rate(alert.score, 3)}</span>
                  <span
                    className="payloop-chip"
                    style={{
                      background: band === 'DECLINE_REVIEW' ? 'var(--ink-black)' : 'var(--soft-bone)',
                      color: band === 'DECLINE_REVIEW' ? 'var(--canvas-cream)' : 'var(--ink-black)',
                    }}
                  >
                    {band}
                  </span>
                </div>
              </div>
              <p className="mt-3 text-body" style={{ color: 'var(--slate-gray)' }}>
                {alert.action}
              </p>
              <ReasonCodes codes={alert.reason_codes} />
            </button>
          </li>
        );
      })}
    </ul>
  );
}
