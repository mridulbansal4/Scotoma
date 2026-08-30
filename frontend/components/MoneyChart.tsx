'use client';

import { useState } from 'react';
import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type { RoundRecord } from '@/lib/artifacts';

import { InkButton } from './InkButton';

const CHART_HEIGHT = 420;
const GATE_THRESHOLD = 10;
const COMPOSITE_MAX = 20;
const RATE_TICKS = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1];
const COMPOSITE_TICKS = [0, 5, 10, 15, 20];
const REJECTED = 'FIDELITY_REJECTED';
const REJECTED_BAND_OPACITY = 0.12;

const SERIES = [
  { key: 'evasion_active', label: 'Evasion — active campaign', color: 'var(--ink-black)', width: 2, dash: undefined },
  { key: 'evasion_blind', label: 'Evasion — blind holdout', color: 'var(--link-blue)', width: 2, dash: undefined },
  { key: 'fpr_legit', label: 'FPR on legitimate traffic', color: 'var(--slate-gray)', width: 1.5, dash: '4 4' },
] as const;

export function MoneyChart({ rounds }: { rounds: RoundRecord[] }) {
  const [visible, setVisible] = useState<Record<string, boolean>>({
    evasion_active: true,
    evasion_blind: true,
    fpr_legit: true,
    fidelity_composite: true,
  });

  const data = rounds.map((record) => ({
    round: record.round + 1,
    evasion_active: record.status === REJECTED ? null : record.evasion_active,
    evasion_blind: record.status === REJECTED ? null : record.evasion_blind,
    fpr_legit: record.status === REJECTED ? null : record.fpr_legit,
    fidelity_composite: record.fidelity_composite,
    rejected: record.status === REJECTED,
  }));

  return (
    <figure className="payloop-card">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <figcaption className="text-eyebrow uppercase" style={{ color: 'var(--slate-gray)' }}>
          Evasion, false positives and fidelity, co-reported
        </figcaption>
        <div className="flex flex-wrap gap-2">
          {[...SERIES, { key: 'fidelity_composite', label: 'Fidelity composite' }].map((series) => (
            <InkButton
              key={series.key}
              variant="secondary"
              pressed={visible[series.key]}
              onClick={() => setVisible((state) => ({ ...state, [series.key]: !state[series.key] }))}
            >
              {series.label}
            </InkButton>
          ))}
        </div>
      </div>

      <div style={{ height: CHART_HEIGHT }} className="mt-8">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 12, right: 24, bottom: 24, left: 8 }}>
            <CartesianGrid stroke="var(--soft-bone)" vertical={false} />
            <XAxis
              dataKey="round"
              tick={{ fontSize: 13, fill: 'var(--slate-gray)' }}
              label={{ value: 'Round', position: 'insideBottom', offset: -12, fontSize: 13 }}
            />
            <YAxis
              yAxisId="rate"
              domain={[0, 1]}
              ticks={RATE_TICKS}
              tick={{ fontSize: 13, fill: 'var(--slate-gray)' }}
              label={{
                value: 'Evasion rate / FPR',
                angle: -90,
                position: 'insideLeft',
                fontSize: 13,
              }}
            />
            <YAxis
              yAxisId="composite"
              orientation="right"
              domain={[0, COMPOSITE_MAX]}
              ticks={COMPOSITE_TICKS}
              tick={{ fontSize: 13, fill: 'var(--slate-gray)' }}
              label={{
                value: 'Fidelity composite (lower is better)',
                angle: 90,
                position: 'insideRight',
                fontSize: 13,
              }}
            />
            <Tooltip
              contentStyle={{
                background: 'var(--white)',
                border: '1px solid var(--dust-taupe)',
                borderRadius: 20,
                fontSize: 13,
              }}
            />
            <Legend wrapperStyle={{ fontSize: 13 }} />

            {data
              .filter((point) => point.rejected)
              .map((point) => (
                <ReferenceArea
                  key={`rejected-${point.round}`}
                  yAxisId="rate"
                  x1={point.round - 0.5}
                  x2={point.round + 0.5}
                  fill="var(--signal-orange)"
                  fillOpacity={REJECTED_BAND_OPACITY}
                  label={{ value: 'FIDELITY REJECTED', fontSize: 13, position: 'insideTop' }}
                />
              ))}

            <ReferenceLine
              yAxisId="composite"
              y={GATE_THRESHOLD}
              stroke="var(--signal-orange)"
              strokeDasharray="4 4"
              label={{ value: 'gate threshold', fontSize: 13, position: 'right' }}
            />

            {SERIES.filter((series) => visible[series.key]).map((series) => (
              <Line
                key={series.key}
                yAxisId="rate"
                type="monotone"
                dataKey={series.key}
                name={series.label}
                stroke={series.color}
                strokeWidth={series.width}
                strokeDasharray={series.dash}
                dot={{ r: 3 }}
                connectNulls={false}
              />
            ))}

            {visible.fidelity_composite ? (
              <Line
                yAxisId="composite"
                type="monotone"
                dataKey="fidelity_composite"
                name="Fidelity composite"
                stroke="var(--light-signal-orange)"
                strokeWidth={1.5}
                dot={{ r: 3 }}
              />
            ) : null}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
