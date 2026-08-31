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
  const fillPercent = Math.min(Math.max(((value - min) / (max - min)) * 100, 0), 100);
  return (
    <label className="flex flex-col gap-2">
      <div className="flex items-center justify-between text-xs font-semibold text-slate-700">
        <span>{label}</span>
        <span className="font-mono text-[#1e2033] font-bold tabular-nums">{display}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="w-full h-2 rounded-lg appearance-none cursor-pointer accent-[#1e2033] focus:outline-none"
        style={{
          background: `linear-gradient(to right, #1e2033 0%, #1e2033 ${fillPercent}%, #e2e8f0 ${fillPercent}%, #e2e8f0 100%)`
        }}
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
    <section className="scotoma-card mt-10 p-6 rounded-2xl bg-white border border-slate-200/80 shadow-sm">
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

          <div className="relative mt-6 pt-10 pb-2">
            <div className="relative h-3 w-full rounded-full bg-[#f4f5fa] border border-slate-200/80 shadow-[inset_0_1px_3px_rgba(0,0,0,0.04)]">
              {/* Animated Progress Fill for Elkan Optimum */}
              <div
                className="absolute top-0 bottom-0 left-0 bg-gradient-to-r from-[#d5e2ff] to-[#a5bbfc] transition-all duration-500 ease-out rounded-full"
                style={{ width: `${Math.min(Math.max(optimal * 100, 0), 100)}%` }}
              />
              
              {/* Elkan Optimum Marker with Tooltip */}
              <div
                className="absolute top-1/2 w-1.5 h-5 bg-[#1e2033] shadow-sm z-20 rounded-full transition-all duration-500 ease-out -translate-y-1/2"
                style={{ left: `calc(${Math.min(Math.max(optimal * 100, 0), 100)}% - 3px)` }}
              >
                <div className="absolute bottom-full mb-3 left-1/2 -translate-x-1/2 bg-[#1e2033] text-white text-[11px] font-mono font-bold px-3 py-1.5 rounded-lg whitespace-nowrap shadow-[0_4px_12px_rgba(30,32,51,0.2)]">
                  Elkan optimum {rate(optimal, 2)}
                  <div className="absolute top-full left-1/2 -translate-x-1/2 border-[5px] border-transparent border-t-[#1e2033]" />
                </div>
              </div>

              {/* Current Threshold Marker (from slider above) */}
              <div
                className="absolute top-1/2 w-1 h-4 bg-white border border-slate-300 z-10 transition-all duration-200 rounded-full -translate-y-1/2 shadow-sm"
                style={{ left: `calc(${Math.min(Math.max(parameters.threshold * 100, 0), 100)}% - 2px)` }}
                title={`Current Threshold: ${rate(parameters.threshold, 2)}`}
              />
            </div>
          </div>

          <p className="text-xs text-slate-500 font-medium">
            Bands: approve below {rate(bands.approve_max, 2)}, step-up to {rate(bands.stepup_max, 2)},
            hold to {rate(bands.hold_max, 2)}.
          </p>
        </div>

        <dl className="grid grid-cols-2 gap-6 self-start rounded-xl sarvam-blue-spotlight p-6 shadow-sm border border-indigo-200/80">
          <div>
            <dt className="text-[11px] font-mono font-semibold uppercase tracking-wider text-slate-500">
              Cost per 100k events
            </dt>
            <dd className="font-mono text-3xl font-semibold tracking-tight text-[#1e2033] mt-2">
              {currency(cost)}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] font-mono font-semibold uppercase tracking-wider text-slate-500">
              FP per True Positive
            </dt>
            <dd className="font-mono text-3xl font-semibold tracking-tight text-[#1e2033] mt-2">
              {Number.isFinite(stats.fpTp) ? stats.fpTp.toFixed(1) : '—'}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] font-mono font-semibold uppercase tracking-wider text-slate-500">
              Precision
            </dt>
            <dd className="font-mono text-3xl font-semibold tracking-tight text-[#1e2033] mt-2">
              {percent(stats.precision)}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] font-mono font-semibold uppercase tracking-wider text-slate-500">
              Recall
            </dt>
            <dd className="font-mono text-3xl font-semibold tracking-tight text-[#1e2033] mt-2">
              {percent(stats.recall)}
            </dd>
          </div>
          <div className="col-span-2 text-xs text-slate-500 leading-relaxed font-medium pt-2 border-t border-indigo-100">
            {count(alerts.length)} scored alerts in the committed queue. Every figure here is
            recomputed in the browser from those rows; zero network calls.
          </div>
        </dl>
      </div>
    </section>
  );
}
