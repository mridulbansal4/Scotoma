import type { RoundRecord } from '@/lib/artifacts';
import { percent, rate } from '@/lib/format';
import { AlertCircle, CheckCircle2 } from 'lucide-react';

const REJECTED = 'FIDELITY_REJECTED';

export function RoundTimeline({ rounds }: { rounds: RoundRecord[] }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {rounds.map((record) => {
        const rejected = record.status === REJECTED;
        return (
          <article
            key={record.round}
            className={`rounded-xl p-6 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md border ${
              rejected
                ? 'bg-amber-50/40 border-amber-200/80'
                : 'bg-white border-slate-200/80 shadow-sm'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Round {record.round + 1}
              </span>
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                  rejected
                    ? 'bg-amber-100 text-amber-800 border border-amber-200/80'
                    : 'bg-emerald-100/80 text-emerald-800 border border-emerald-200/80'
                }`}
              >
                {rejected ? <AlertCircle size={12} /> : <CheckCircle2 size={12} />}
                <span>{record.status.replace(/_/g, ' ')}</span>
              </span>
            </div>

            <p className="mt-4 font-mono text-3xl font-semibold tracking-tight text-[#1e2033]">
              {rejected ? rate(record.fidelity_composite, 2) : percent(record.evasion_active)}
            </p>
            <p className="mt-1 text-xs text-slate-500 font-medium">
              {rejected
                ? 'Behavioural composite at rejection'
                : `Evasion active campaign • Blind ${percent(record.evasion_blind)}`}
            </p>

            <div className="mt-5 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500 font-medium">
              <span>{record.proposals_valid}/{record.proposals_total} valid</span>
              <span>{record.campaigns.length} campaigns</span>
            </div>

            {record.suspicious_pr_auc ? (
              <div className="mt-3 rounded-lg bg-rose-100/60 p-2.5 border border-rose-200/80 text-xs font-semibold text-rose-800 flex items-center gap-1.5">
                <AlertCircle size={14} className="shrink-0" />
                <span>SUSPICIOUS PR-AUC — treated as defect</span>
              </div>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}
