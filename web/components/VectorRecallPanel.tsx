'use client';

import {
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

const CHART_HEIGHT = 320;
const RECALL_BAR = 0.6;
const TICK_STEP = 0.2;

interface VectorRecallPanelProps {
  recall: Record<string, number>;
  holdoutVectors: string[];
}

export function VectorRecallPanel({ recall, holdoutVectors }: VectorRecallPanelProps) {
  const data = Object.entries(recall)
    .map(([vector, value]) => ({ vector, recall: value }))
    .sort((a, b) => a.vector.localeCompare(b.vector));

  return (
    <figure className="payloop-card">
      <figcaption className="text-eyebrow uppercase" style={{ color: 'var(--slate-gray)' }}>
        Per-vector recall · the weak ones are shown
      </figcaption>
      <div style={{ height: CHART_HEIGHT }} className="mt-6">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 12, bottom: 8, left: 4 }}>
            <CartesianGrid stroke="var(--soft-bone)" vertical={false} />
            <XAxis dataKey="vector" tick={{ fontSize: 13, fill: 'var(--slate-gray)' }} />
            <YAxis
              domain={[0, 1]}
              ticks={[0, TICK_STEP, TICK_STEP * 2, TICK_STEP * 3, TICK_STEP * 4, 1]}
              tick={{ fontSize: 13, fill: 'var(--slate-gray)' }}
            />
            <Tooltip
              contentStyle={{
                background: 'var(--white)',
                border: '1px solid var(--dust-taupe)',
                borderRadius: 20,
                fontSize: 13,
              }}
            />
            <ReferenceLine
              y={RECALL_BAR}
              stroke="var(--slate-gray)"
              strokeDasharray="4 4"
              label={{ value: 'coverage bar', fontSize: 13, position: 'right' }}
            />
            <Bar dataKey="recall" radius={[6, 6, 0, 0]}>
              {data.map((entry) => (
                <Cell
                  key={entry.vector}
                  fill={
                    holdoutVectors.includes(entry.vector) ? 'var(--link-blue)' : 'var(--ink-black)'
                  }
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {holdoutVectors.length ? (
        <p className="mt-4 flex items-center gap-2 text-data">
          <span
            className="payloop-chip"
            style={{ background: 'var(--link-blue)', color: 'var(--white)' }}
          >
            BLIND HOLDOUT
          </span>
          <span style={{ color: 'var(--slate-gray)' }}>
            {holdoutVectors.join(', ')} never entered any training pool.
          </span>
        </p>
      ) : null}
    </figure>
  );
}
