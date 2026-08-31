'use client';

import type { CoverageRow } from '@/lib/artifacts';
import { percent } from '@/lib/format';
import { ShieldAlert, Zap } from 'lucide-react';

interface VectorTableProps {
  rows: CoverageRow[];
  selected: string | null;
  onSelect: (vectorId: string) => void;
}

const RECALL_BAR_WIDTH = 72;
const DOCUMENTED_ONLY_OPACITY = 0.65;

function StatusChip({ status }: { status: CoverageRow['status'] }) {
  const isDocumented = status === 'documented';
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider ${
        isDocumented
          ? 'bg-[#1e2033] text-white'
          : 'bg-slate-100 text-slate-600 border border-slate-200'
      }`}
    >
      {status}
    </span>
  );
}

function RecallBar({ value }: { value: number | null }) {
  if (value === null) {
    return (
      <span className="text-[12px] font-mono text-slate-400">
        not simulated
      </span>
    );
  }
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 rounded-full bg-slate-100 overflow-hidden" style={{ width: RECALL_BAR_WIDTH }}>
        <div
          className="h-full rounded-full bg-[#1e2033] transition-all duration-300"
          style={{ width: `${Math.round(value * 100)}%` }}
        />
      </div>
      <span className="text-[13px] font-mono font-medium text-[#1e2033]">{percent(value, 0)}</span>
    </div>
  );
}

export function VectorTable({ rows, selected, onSelect }: VectorTableProps) {
  return (
    <div className="scotoma-scroll-x mt-8 rounded-2xl bg-white border border-slate-200/80 shadow-sm overflow-hidden">
      <table className="w-full min-w-[840px] border-collapse text-left">
        <thead>
          <tr className="border-b border-slate-100 bg-[#f8f9fc] text-[11px] font-semibold uppercase tracking-widest text-[#1e2033]/70">
            <th className="px-5 py-3.5">ID</th>
            <th className="px-5 py-3.5">Vector Name</th>
            <th className="px-5 py-3.5">Rails</th>
            <th className="px-5 py-3.5">Tier</th>
            <th className="px-5 py-3.5">Status</th>
            <th className="px-5 py-3.5">Injector</th>
            <th className="px-5 py-3.5">Recall</th>
            <th className="px-5 py-3.5">Holdout</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => {
            const isSelected = selected === row.vector_id;
            return (
              <tr
                key={row.vector_id}
                onClick={() => onSelect(row.vector_id)}
                className={`cursor-pointer align-middle transition-all duration-200 ${
                  isSelected
                    ? 'bg-[#f0f4ff] text-[#1e2033] font-medium shadow-sm'
                    : 'hover:bg-slate-50/80'
                }`}
                style={{
                  opacity: row.has_injector ? 1 : DOCUMENTED_ONLY_OPACITY,
                }}
              >
                <td className="px-5 py-4 text-[13px] font-mono font-semibold text-[#1e2033]">
                  {row.vector_id}
                </td>
                <td className="px-5 py-4 text-[14px] font-medium text-[#1e2033]">{row.name}</td>
                <td className="px-5 py-4 text-[13px] text-slate-500">
                  {row.rails.join(', ')}
                </td>
                <td className="px-5 py-4 text-[13px] font-mono text-slate-600">{row.tier}</td>
                <td className="px-5 py-4">
                  <StatusChip status={row.status} />
                </td>
                <td className="px-5 py-4">
                  {row.has_injector ? (
                    <span className="inline-flex items-center gap-1 text-[12px] font-medium text-[#1e2033]">
                      <Zap size={13} className="text-[#1e2033]" />
                      <span>Live</span>
                    </span>
                  ) : (
                    <span className="text-[13px] text-slate-400">—</span>
                  )}
                </td>
                <td className="px-5 py-4">
                  <RecallBar value={row.recall} />
                </td>
                <td className="px-5 py-4">
                  {row.blind_holdout ? (
                    <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold text-[#1e2033] border border-slate-200">
                      <ShieldAlert size={12} className="text-[#1e2033]" />
                      <span>HOLDOUT</span>
                    </span>
                  ) : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
