import type { Alert, LadderBands as Bands } from '@/lib/artifacts';
import { count, rate, percent } from '@/lib/format';

interface LadderBandsProps {
  alerts: Alert[];
  bands: Bands;
  threshold: number;
}

function bandFor(score: number, bands: Bands): number {
  if (score < bands.approve_max) return 0;
  if (score < bands.stepup_max) return 1;
  if (score < bands.hold_max) return 2;
  return 3;
}

const CheckCircleIcon = () => (
  <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const ShieldExclamationIcon = () => (
  <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M20.618 5.984A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016zM12 9v2m0 4h.01" />
  </svg>
);

const HandRaisedIcon = () => (
  <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M7 11.5V14m0-2.5v-6a1.5 1.5 0 113 0m-3 6a1.5 1.5 0 00-3 0v2a7.5 7.5 0 0015 0v-5a1.5 1.5 0 00-3 0m-6-3V11m0-5.5v-1a1.5 1.5 0 013 0v1m0 0V11m0-5.5a1.5 1.5 0 013 0v3m0 0V11" />
  </svg>
);

const XCircleIcon = () => (
  <svg className="w-3 h-3 mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

export function LadderBands({ alerts, bands, threshold }: LadderBandsProps) {
  const counts = [0, 0, 0, 0];
  for (const alert of alerts) {
    if (alert.score >= threshold) counts[bandFor(alert.score, bands)] += 1;
  }
  
  const total = alerts.length || 1;

  const bandData = [
    {
      name: 'BAND 1',
      action: 'APPROVE',
      actionBg: 'bg-emerald-50 text-emerald-700',
      thresholdText: `< ${rate(bands.approve_max, 2)}`,
      icon: <CheckCircleIcon />
    },
    {
      name: 'BAND 2',
      action: 'STEP-UP (3DS)',
      actionBg: 'bg-blue-50 text-blue-700',
      thresholdText: `${rate(bands.approve_max, 2)} - ${rate(bands.stepup_max, 2)}`,
      icon: <ShieldExclamationIcon />
    },
    {
      name: 'BAND 3',
      action: 'HOLD',
      actionBg: 'bg-amber-50 text-amber-700',
      thresholdText: `${rate(bands.stepup_max, 2)} - ${rate(bands.hold_max, 2)}`,
      icon: <HandRaisedIcon />
    },
    {
      name: 'BAND 4',
      action: 'DECLINE + SAR',
      actionBg: 'bg-rose-50 text-rose-700',
      thresholdText: `≥ ${rate(bands.hold_max, 2)}`,
      icon: <XCircleIcon />
    },
  ];

  return (
    <section>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {bandData.map((data, index) => (
          <div
            key={data.name}
            className="flex flex-col rounded-[14px] bg-white border border-slate-200/80 p-5 shadow-[0_1px_2px_rgba(0,0,0,0.02)]"
          >
            {/* Top Row */}
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold tracking-wider text-slate-500 uppercase">
                {data.name}
              </span>
              <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold tracking-wide ${data.actionBg}`}>
                {data.icon}
                {data.action}
              </span>
            </div>

            {/* Main Number */}
            <div className="mt-5">
              <span className="text-[32px] font-semibold tracking-tight text-[#1e2033] leading-none font-mono">
                {count(counts[index])}
              </span>
            </div>

            {/* Subtitle */}
            <div className="mt-1.5">
              <span className="text-xs text-slate-500">
                Decision threshold {data.thresholdText}
              </span>
            </div>

            {/* Footer with divider */}
            <div className="mt-5 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-[#1e2033]">
              <span className="font-medium">{percent(counts[index] / total)} volume</span>
              <span>{counts[index]} alerts</span>
            </div>
          </div>
        ))}
      </div>
      <p className="mt-4 text-xs font-medium text-slate-500">
        No autonomous block below {rate(bands.hold_max, 2)}; a human is in the loop for the consequential action.
      </p>
    </section>
  );
}
