'use client';

import type { SseRecord } from '@/lib/artifacts';
import { AlertCircle, CheckCircle2, Play, Flag } from 'lucide-react';

const PARAM_PREVIEW_LIMIT = 6;

function ParamTable({ params }: { params: Record<string, unknown> }) {
  const entries = Object.entries(params).slice(0, PARAM_PREVIEW_LIMIT);
  if (entries.length === 0) return null;
  
  return (
    <div className="mt-4 rounded-lg bg-slate-50 p-3 border border-slate-200/60">
      <div className="text-[11px] font-mono font-medium uppercase tracking-wider text-slate-500 mb-2">
        Injected Parameters
      </div>
      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1.5 text-xs">
        {entries.map(([key, value]) => (
          <div key={key} className="flex items-center justify-between gap-2 py-0.5 border-b border-slate-200/40 last:border-0">
            <dt className="font-mono text-slate-600 truncate">{key}</dt>
            <dd className="font-mono font-semibold text-[#1e2033] tabular-nums truncate">
              {JSON.stringify(value)}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function EventCard({ record }: { record: SseRecord }) {
  const data = record.data as Record<string, never>;
  const rejected = record.event === 'proposal_rejected';
  const roundEvent = record.event === 'round_result' || record.event === 'round_rejected';

  if (record.event === 'round_start') {
    return (
      <article className="rounded-xl bg-gradient-to-r from-indigo-50/90 via-blue-50/40 to-white p-5 shadow-sm border border-indigo-200/80 transition-all">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#1e2033] text-white shadow-xs">
              <Play size={13} className="ml-0.5 fill-white" />
            </div>
            <span className="text-xs font-bold uppercase tracking-wider text-indigo-950">
              Round {String(data.round)} Launched
            </span>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-[#1e2033] px-3 py-1 text-xs font-mono font-semibold text-white shadow-xs">
            <span className="text-indigo-300">AGENT:</span>
            <span className="uppercase">{String(data.agent_mode)}</span>
          </span>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-1 text-xs text-slate-700 font-medium">
          <div>
            <span className="text-slate-500 font-normal">Threshold: </span>
            <span className="font-mono font-semibold text-[#1e2033]">{String(data.threshold)}</span>
          </div>
          <div>
            <span className="text-slate-500 font-normal">Top SHAP features: </span>
            <span className="font-mono text-slate-800 font-medium">
              {(data.top_shap_features as unknown as string[])?.join(', ')}
            </span>
          </div>
        </div>
      </article>
    );
  }

  if (roundEvent) {
    const isRoundRejected = record.event === 'round_rejected';
    return (
      <article
        className={`rounded-xl p-5 shadow-sm transition-all border ${
          isRoundRejected
            ? 'bg-amber-50/80 border-amber-200/90 text-amber-950'
            : 'bg-white border-slate-200 text-[#1e2033]'
        }`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {isRoundRejected ? (
              <AlertCircle size={16} className="text-amber-600" />
            ) : (
              <CheckCircle2 size={16} className="text-emerald-600" />
            )}
            <span className="text-xs font-bold uppercase tracking-wider">
              Round {String(data.round)} • {String(data.status)}
            </span>
          </div>
        </div>
        <p className="mt-2 text-sm font-medium leading-relaxed">
          {isRoundRejected
            ? String(data.hint)
            : `Evasion: ${String(data.evasion_active)} • Blind: ${String(data.evasion_blind)} • PR-AUC: ${String(data.pr_auc)}`}
        </p>
      </article>
    );
  }

  if (record.event === 'fidelity') {
    return (
      <article className="rounded-xl bg-slate-50/80 p-5 border border-slate-200 text-[#1e2033]">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-600">
            Fidelity Gate • Round {String(data.round)}
          </span>
          <span
            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
              data.passed
                ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                : 'bg-rose-100 text-rose-800 border border-rose-200'
            }`}
          >
            {data.passed ? 'PASSED' : 'FAILED'}
          </span>
        </div>
        <p className="mt-2 text-sm text-slate-700">
          Composite behavioral: <span className="font-mono font-semibold">{String(data.composite_behavioral)}</span> • Shadow layer: <span className="font-mono">{String(data.shadow_layer)}</span>
        </p>
      </article>
    );
  }

  if (record.event === 'done') {
    return (
      <article className="rounded-xl bg-gradient-to-r from-emerald-50/90 via-teal-50/40 to-white p-5 shadow-sm border border-emerald-200/80">
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-emerald-600 text-white shadow-xs">
            <Flag size={14} />
          </div>
          <span className="text-xs font-bold uppercase tracking-wider text-emerald-950">
            Execution Complete
          </span>
        </div>
        <p className="mt-2.5 text-xs text-slate-700 font-medium">
          <span className="font-semibold text-emerald-900">{String(data.rounds_completed)}</span> rounds completed • <span className="font-semibold text-amber-800">{String(data.rounds_rejected)}</span> rounds rejected
        </p>
      </article>
    );
  }

  return (
    <article
      className={`rounded-xl p-5 shadow-sm transition-all duration-200 hover:shadow-md border ${
        rejected
          ? 'bg-rose-50/40 border-rose-200'
          : 'bg-white border-slate-200'
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span
            className={`inline-flex items-center rounded-md px-2.5 py-0.5 text-xs font-mono font-bold ${
              rejected
                ? 'bg-rose-100 text-rose-900 border border-rose-300'
                : 'bg-[#1e2033] text-white'
            }`}
          >
            {String(data.vector_id)}
          </span>
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Round {String(data.round)}
          </span>
        </div>
        
        {rejected ? (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-100 px-2.5 py-0.5 text-xs font-semibold text-rose-800 border border-rose-200">
            <AlertCircle size={13} />
            <span>PROPOSAL REJECTED</span>
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-800 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-200">
            <CheckCircle2 size={13} className="text-emerald-600" />
            <span>ACCEPTED</span>
          </span>
        )}
      </div>

      {rejected ? (
        <div className="mt-3.5 space-y-1">
          <p className="text-sm font-semibold text-rose-900 leading-snug">
            {String(data.reason)}
          </p>
          <p className="text-xs text-rose-700/80">{String(data.rule)}</p>
        </div>
      ) : (
        <p className="mt-3 text-sm leading-relaxed text-slate-700">{String(data.rationale)}</p>
      )}

      <ParamTable params={(data.params ?? {}) as Record<string, unknown>} />
    </article>
  );
}

export function ProposalStream({ records }: { records: SseRecord[] }) {
  return (
    <div className="mt-6 flex flex-col gap-3.5">
      {records.map((record, index) => (
        <EventCard key={`${record.event}-${index}`} record={record} />
      ))}
    </div>
  );
}
