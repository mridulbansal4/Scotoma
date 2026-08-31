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
        const isSelected = selected === alert.event_id;

        return (
          <li key={alert.event_id}>
            <button
              type="button"
              onClick={() => onSelect(alert.event_id)}
              className={`group w-full rounded-xl p-5 text-left transition-all duration-200 border ${
                isSelected
                  ? 'sarvam-blue-card border-indigo-300 shadow-sm'
                  : injection
                  ? 'bg-rose-50/30 border-rose-200 hover:border-rose-300 hover:bg-rose-50/50'
                  : 'bg-white border-slate-200/80 hover:border-slate-300 hover:shadow-sm'
              }`}
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-700">
                    {alert.rail}
                  </span>
                  {alert.vector_id ? (
                    <span className="inline-flex items-center rounded-full bg-indigo-100/90 px-2.5 py-0.5 text-xs font-semibold text-indigo-950 border border-indigo-200">
                      {alert.vector_id}
                    </span>
                  ) : null}
                  <span className="text-xs font-mono text-slate-500">
                    {alert.event_ts.slice(0, 19).replace('T', ' ')}
                  </span>
                </div>

                <div className="flex items-center gap-3">
                  <span className="text-sm font-mono font-semibold text-[#1e2033]">
                    Score {rate(alert.score, 3)}
                  </span>
                  <span
                    className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                      band === 'DECLINE_REVIEW'
                        ? 'bg-rose-100 text-rose-800 border border-rose-200'
                        : band === 'HOLD'
                        ? 'bg-amber-100 text-amber-800 border border-amber-200'
                        : 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                    }`}
                  >
                    {band}
                  </span>
                  <span className="text-slate-400 group-hover:translate-x-1 group-hover:text-[#1e2033] transition-all duration-200">
                    →
                  </span>
                </div>
              </div>

              <p className="mt-3 text-sm text-slate-600 font-medium leading-relaxed">
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
