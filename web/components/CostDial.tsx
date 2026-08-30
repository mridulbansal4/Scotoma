'use client';

import type { Alert, LadderBands } from '@/lib/artifacts';
import { count, currency, percent, rate } from '@/lib/format';

export interface CostParameters {
  threshold: number;
  chargebackFee: number;
  customerLtv: number;
  attrition: number;
  merchantMargin: number;
}

interface CostDialProps {
  alerts: Alert[];
  parameters: CostParameters;
  bands: LadderBands;
  onChange: (next: CostParameters) => void;
}

const THRESHOLD_STEP = 0.01;
const FEE_STEP = 5;
const LTV_STEP = 100;
const ATTRITION_STEP = 0.01;
const COST_SCALE_PER = 100_000;

/** Elkan (2001): predict positive iff expected cost is lower, so tau* = C_FP/(C_FP+C_FN). */
export function closedFormThreshold(amount: number, parameters: CostParameters): number {
  const costFp = amount * parameters.merchantMargin + parameters.attrition * parameters.customerLtv;
  const costFn = amount + parameters.chargebackFee;
  return costFp / (costFp + costFn);
}

export function expectedCost(alerts: Alert[], parameters: CostParameters): number {
  let total = 0;
  for (const alert of alerts) {
    const predicted = alert.score >= parameters.threshold;
    if (alert.is_fraud && !predicted) total += alert.amount + parameters.chargebackFee;
    if (!alert.is_fraud && predicted) {
      total += alert.amount * parameters.merchantMargin + parameters.attrition * parameters.customerLtv;
    }
  }
  return alerts.length ? (total / alerts.length) * COST_SCALE_PER : 0;
}

export function confusion(alerts: Alert[], threshold: number) {
  let truePositive = 0;
  let falsePositive = 0;
  let falseNegative = 0;
  for (const alert of alerts) {
    const predicted = alert.score >= threshold;
    if (alert.is_fraud && predicted) truePositive += 1;
    if (!alert.is_fraud && predicted) falsePositive += 1;
    if (alert.is_fraud && !predicted) falseNegative += 1;
  }
  return {
    truePositive,
    falsePositive,
    falseNegative,
    precision: truePositive + falsePositive ? truePositive / (truePositive + falsePositive) : 0,
    recall: truePositive + falseNegative ? truePositive / (truePositive + falseNegative) : 0,
    fpTp: truePositive ? falsePositive / truePositive : Number.POSITIVE_INFINITY,
  };
}

function Slider({
  label,
  value,
  min,
  max,
  step,
  display,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  display: string;
  onChange: (value: number) => void;
}) {
  return (
    <label className="flex flex-col gap-2">
      <span className="flex items-center justify-between text-data">
        <span style={{ color: 'var(--slate-gray)' }}>{label}</span>
        <span className="tabular-nums">{display}</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="h-2 w-full cursor-pointer appearance-none rounded-pill"
        style={{ background: 'var(--soft-bone)', accentColor: 'var(--ink-black)' }}
      />
    </label>
  );
}

export function CostDial({ alerts, parameters, bands, onChange }: CostDialProps) {
  const stats = confusion(alerts, parameters.threshold);
  const cost = expectedCost(alerts, parameters);
  const medianAmount = alerts.length
    ? [...alerts].sort((a, b) => a.amount - b.amount)[Math.floor(alerts.length / 2)].amount
    : 0;
  const optimal = closedFormThreshold(medianAmount, parameters);

  return (
    <section className="payloop-card mt-10">
      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-6">
          <Slider
            label="Decision threshold"
            value={parameters.threshold}
            min={0.01}
            max={0.99}
            step={THRESHOLD_STEP}
            display={rate(parameters.threshold, 2)}
            onChange={(value) => onChange({ ...parameters, threshold: value })}
          />
          <Slider
            label="Chargeback fee"
            value={parameters.chargebackFee}
            min={0}
            max={200}
            step={FEE_STEP}
            display={currency(parameters.chargebackFee)}
            onChange={(value) => onChange({ ...parameters, chargebackFee: value })}
          />
          <Slider
            label="Customer lifetime value"
            value={parameters.customerLtv}
            min={100}
            max={20000}
            step={LTV_STEP}
            display={currency(parameters.customerLtv)}
            onChange={(value) => onChange({ ...parameters, customerLtv: value })}
          />
          <Slider
            label="Attrition probability"
            value={parameters.attrition}
            min={0}
            max={1}
            step={ATTRITION_STEP}
            display={rate(parameters.attrition, 2)}
            onChange={(value) => onChange({ ...parameters, attrition: value })}
          />

          <div className="relative mt-2 h-10 rounded-pill" style={{ background: 'var(--soft-bone)' }}>
            <span
              className="absolute top-0 h-10 w-[2px]"
              style={{ left: `${optimal * 100}%`, background: 'var(--link-blue)' }}
              aria-hidden
            />
            <span
              className="absolute -top-6 text-data"
              style={{ left: `${Math.min(optimal * 100, 88)}%`, color: 'var(--link-blue)' }}
            >
              Elkan optimum {rate(optimal, 2)}
            </span>
            <span
              className="absolute top-0 h-10 w-[2px]"
              style={{ left: `${parameters.threshold * 100}%`, background: 'var(--ink-black)' }}
              aria-hidden
            />
          </div>
          <p className="text-data" style={{ color: 'var(--slate-gray)' }}>
            Bands: approve below {rate(bands.approve_max, 2)}, step-up to {rate(bands.stepup_max, 2)},
            hold to {rate(bands.hold_max, 2)}.
          </p>
        </div>

        <dl className="grid grid-cols-2 gap-6 self-start">
          <div>
            <dt className="text-eyebrow uppercase" style={{ color: 'var(--slate-gray)' }}>
              Cost per 100k events
            </dt>
            <dd className="payloop-readout mt-2">{currency(cost)}</dd>
          </div>
          <div>
            <dt className="text-eyebrow uppercase" style={{ color: 'var(--slate-gray)' }}>
              False positives per true positive
            </dt>
            <dd className="payloop-readout mt-2">
              {Number.isFinite(stats.fpTp) ? stats.fpTp.toFixed(1) : '—'}
            </dd>
          </div>
          <div>
            <dt className="text-eyebrow uppercase" style={{ color: 'var(--slate-gray)' }}>
              Precision
            </dt>
            <dd className="payloop-readout mt-2">{percent(stats.precision)}</dd>
          </div>
          <div>
            <dt className="text-eyebrow uppercase" style={{ color: 'var(--slate-gray)' }}>
              Recall
            </dt>
            <dd className="payloop-readout mt-2">{percent(stats.recall)}</dd>
          </div>
          <div className="col-span-2 text-data" style={{ color: 'var(--slate-gray)' }}>
            {count(alerts.length)} scored alerts in the committed queue. Every figure here is
            recomputed in the browser from those rows; nothing is requested.
          </div>
        </dl>
      </div>
    </section>
  );
}
