'use client';

import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type { Histogram } from '@/lib/artifacts';

export type OverlayMode = 'real' | 'synthetic' | 'both';

interface DistributionOverlayProps {
  title: string;
  xLabel: string;
  yLabel: string;
  real: Histogram;
  synthetic: Histogram;
  mode: OverlayMode;
  powerLawAlpha?: number;
}

const CHART_HEIGHT = 260;
const FILL_OPACITY = 0.3;
const AXIS_DIGITS = 2;

interface Point {
  x: number;
  real: number;
  synthetic: number;
  fitted?: number;
}

function toPoints(real: Histogram, synthetic: Histogram, alpha?: number): Point[] {
  const bins = Math.min(real.density.length, synthetic.density.length);
  const points: Point[] = [];
  for (let index = 0; index < bins; index += 1) {
    const centre = (real.edges[index] + real.edges[index + 1]) / 2;
    const point: Point = {
      x: Number(centre.toFixed(AXIS_DIGITS)),
      real: real.density[index],
      synthetic: synthetic.density[index],
    };
    if (alpha) {
      // The Clauset-Shalizi-Newman fit, drawn as a reference rather than as a regression.
      point.fitted = Math.max(real.density[0], 1e-6) * Math.pow(10, -alpha * centre);
    }
    points.push(point);
  }
  return points;
}

export function DistributionOverlay({
  title,
  xLabel,
  yLabel,
  real,
  synthetic,
  mode,
  powerLawAlpha,
}: DistributionOverlayProps) {
  const data = toPoints(real, synthetic, powerLawAlpha);
  return (
    <figure className="rounded-stadium bg-lifted p-6 shadow-card">
      <figcaption className="text-eyebrow uppercase" style={{ color: 'var(--slate-gray)' }}>
        {title}
        {powerLawAlpha ? ` · CSN α = ${powerLawAlpha.toFixed(2)}` : ''}
      </figcaption>
      <div style={{ height: CHART_HEIGHT }} className="mt-4">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 48, left: 4 }}>
            <CartesianGrid stroke="var(--soft-bone)" vertical={false} />
            <XAxis
              dataKey="x"
              tick={{ fontSize: 13, fill: 'var(--slate-gray)' }}
              label={{ value: xLabel, position: 'insideBottom', offset: -12, fontSize: 13 }}
            />
            <YAxis
              tick={{ fontSize: 13, fill: 'var(--slate-gray)' }}
              label={{ value: yLabel, angle: -90, position: 'insideLeft', fontSize: 13 }}
            />
            <Tooltip
              contentStyle={{
                background: 'var(--white)',
                border: '1px solid var(--dust-taupe)',
                borderRadius: 20,
                fontSize: 13,
              }}
            />
            <Legend wrapperStyle={{ fontSize: 13, paddingTop: '20px' }} verticalAlign="bottom" height={40} />
            {mode !== 'synthetic' ? (
              <Area
                type="monotone"
                dataKey="real"
                name="Real"
                stroke="var(--ink-black)"
                fill="var(--ink-black)"
                fillOpacity={FILL_OPACITY}
                strokeWidth={2}
              />
            ) : null}
            {mode !== 'real' ? (
              <Area
                type="monotone"
                dataKey="synthetic"
                name="Synthetic"
                stroke="var(--light-signal-orange)"
                fill="var(--light-signal-orange)"
                fillOpacity={FILL_OPACITY}
                strokeWidth={2}
              />
            ) : null}
            {powerLawAlpha ? (
              <Line
                type="monotone"
                dataKey="fitted"
                name="Power-law fit"
                stroke="var(--slate-gray)"
                strokeDasharray="4 4"
                strokeWidth={1.5}
                dot={false}
              />
            ) : null}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
