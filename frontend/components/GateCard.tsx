import type { GateLayer } from '@/lib/artifacts';
import { CheckCircle2, XCircle, EyeOff } from 'lucide-react';

interface GateCardProps {
  name: string;
  layer: GateLayer;
  headlineMetric: string;
  threshold: string;
  shadow: boolean;
}

function readMetric(layer: GateLayer, key: string): string {
  const value = layer[key];
  if (typeof value === 'number') return value.toFixed(value < 1 ? 4 : 2);
  if (value === undefined) return 'INSUFFICIENT_DATA';
  return String(value);
}

export function GateCard({ name, layer, headlineMetric, threshold, shadow }: GateCardProps) {
  const failed = !layer.passed;
  return (
    <article
      className={`group relative flex flex-col justify-between rounded-xl p-6 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md border ${
        failed
          ? 'border-rose-200 bg-rose-50/20'
          : 'bg-gradient-to-br from-indigo-50/60 via-blue-50/20 to-white border-indigo-200/80 hover:border-indigo-300'
      }`}
    >
      <div>
        <div className="flex items-center justify-between gap-4">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            {name} Layer
          </span>
          {shadow ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold text-slate-600 border border-slate-200">
              <EyeOff size={11} />
              <span>SHADOW HELD OUT</span>
            </span>
          ) : null}
        </div>

        <div className="mt-4 flex items-baseline gap-2">
          <span className="font-mono text-3xl font-semibold tracking-tight text-[#1e2033] tabular-nums">
            {readMetric(layer, headlineMetric)}
          </span>
          <span className="font-mono text-xs text-slate-400">({headlineMetric})</span>
        </div>

        <p className="mt-2 text-xs leading-relaxed text-slate-500">{threshold}</p>
      </div>

      <div className="mt-6 pt-4 border-t border-slate-100 flex items-center justify-between">
        <span className="text-xs font-mono text-slate-400 uppercase">Target Gate</span>
        {failed ? (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-100 px-3 py-1 text-xs font-semibold text-rose-700 border border-rose-200">
            <XCircle size={14} />
            <span>FAILED</span>
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100/80 px-3 py-1 text-xs font-semibold text-emerald-800 border border-emerald-200/80">
            <CheckCircle2 size={14} className="text-emerald-600" />
            <span>PASSED</span>
          </span>
        )}
      </div>
    </article>
  );
}

