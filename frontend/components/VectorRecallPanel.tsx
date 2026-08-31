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
    <figure className="rounded-[14px] bg-white border border-slate-200/80 p-5 lg:p-6 shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
      <figcaption className="text-[11px] font-bold tracking-wider text-slate-500 uppercase">
        Per-vector recall · the weak ones are shown
      </figcaption>
      
      <div style={{ height: CHART_HEIGHT }} className="mt-8">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 0, right: 0, bottom: 0, left: -20 }}>
            <CartesianGrid stroke="#f1f5f9" vertical={false} />
            <XAxis 
              dataKey="vector" 
              tick={{ fontSize: 11, fill: '#64748b', fontWeight: 500 }}
              axisLine={false}
              tickLine={false}
              tickMargin={12}
            />
            <YAxis
              domain={[0, 1]}
              ticks={[0, TICK_STEP, TICK_STEP * 2, TICK_STEP * 3, TICK_STEP * 4, 1]}
              tick={{ fontSize: 11, fill: '#64748b', fontWeight: 500 }}
              axisLine={false}
              tickLine={false}
              tickMargin={12}
            />
            <Tooltip
              cursor={{ fill: '#f8f9fc' }}
              contentStyle={{
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: '12px',
                fontSize: 12,
                fontWeight: 600,
                color: '#1e2033',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03)'
              }}
              itemStyle={{ color: '#1e2033' }}
            />
            <ReferenceLine
              y={RECALL_BAR}
              stroke="#cbd5e1"
              strokeDasharray="4 4"
            />
            <Bar dataKey="recall" radius={[4, 4, 0, 0]} maxBarSize={48}>
              {data.map((entry) => (
                <Cell
                  key={entry.vector}
                  fill={holdoutVectors.includes(entry.vector) ? '#3b82f6' : '#1e2033'}
                  className="transition-all duration-300 hover:opacity-80 cursor-pointer"
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {holdoutVectors.length > 0 && (
        <div className="mt-8 pt-4 border-t border-slate-100 flex items-center gap-3">
          <span className="inline-flex items-center rounded-full px-2.5 py-1 text-[10px] font-bold tracking-wide bg-blue-50 text-blue-700 uppercase">
            Blind Holdout
          </span>
          <span className="text-xs font-medium text-slate-500">
            {holdoutVectors.join(', ')} never entered any training pool.
          </span>
        </div>
      )}
    </figure>
  );
}
