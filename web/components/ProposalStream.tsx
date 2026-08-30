'use client';

import type { SseRecord } from '@/lib/artifacts';

const PARAM_PREVIEW_LIMIT = 6;

function ParamTable({ params }: { params: Record<string, unknown> }) {
  const entries = Object.entries(params).slice(0, PARAM_PREVIEW_LIMIT);
  return (
    <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-2 text-data">
      {entries.map(([key, value]) => (
        <div key={key} className="flex justify-between gap-4">
          <dt style={{ color: 'var(--slate-gray)' }}>{key}</dt>
          <dd className="tabular-nums">{JSON.stringify(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function EventCard({ record }: { record: SseRecord }) {
  const data = record.data as Record<string, never>;
  const rejected = record.event === 'proposal_rejected';
  const roundEvent = record.event === 'round_result' || record.event === 'round_rejected';

  if (record.event === 'round_start') {
    return (
      <article className="rounded-stadium bg-ink px-6 py-5 text-canvas">
        <p className="text-eyebrow uppercase">Round {String(data.round)} · start</p>
        <p className="mt-2 text-data">
          threshold {String(data.threshold)} · agent {String(data.agent_mode)}
        </p>
        <p className="mt-2 text-data opacity-70">
          top features: {(data.top_shap_features as unknown as string[])?.join(', ')}
        </p>
      </article>
    );
  }

  if (roundEvent) {
    return (
      <article
        className="rounded-stadium px-6 py-5"
        style={{
          background: 'var(--white)',
          border: `1.5px solid ${record.event === 'round_rejected' ? 'var(--signal-orange)' : 'var(--ink-black)'}`,
        }}
      >
        <p className="text-eyebrow uppercase">
          Round {String(data.round)} · {String(data.status)}
        </p>
        <p className="mt-2 text-data">
          {record.event === 'round_rejected'
            ? String(data.hint)
            : `evasion ${String(data.evasion_active)} · blind ${String(data.evasion_blind)} · PR-AUC ${String(data.pr_auc)}`}
        </p>
      </article>
    );
  }

  if (record.event === 'fidelity') {
    return (
      <article className="rounded-stadium bg-bone px-6 py-5">
        <p className="text-eyebrow uppercase">Fidelity gate · round {String(data.round)}</p>
        <p className="mt-2 text-data">
          composite {String(data.composite_behavioral)} · shadow layer {String(data.shadow_layer)} ·{' '}
          {data.passed ? 'passed' : 'failed'}
        </p>
      </article>
    );
  }

  if (record.event === 'done') {
    return (
      <article className="rounded-stadium bg-ink px-6 py-5 text-canvas">
        <p className="text-eyebrow uppercase">Run complete</p>
        <p className="mt-2 text-data">
          {String(data.rounds_completed)} completed · {String(data.rounds_rejected)} rejected
        </p>
      </article>
    );
  }

  return (
    <article
      className="rounded-stadium bg-lifted px-6 py-5"
      style={{ borderLeft: rejected ? '1.5px solid var(--signal-orange)' : 'none' }}
    >
      <div className="flex flex-wrap items-center gap-3">
        <span
          className="payloop-chip"
          style={{
            background: rejected ? 'var(--signal-orange)' : 'var(--ink-black)',
            color: rejected ? 'var(--white)' : 'var(--canvas-cream)',
          }}
        >
          {String(data.vector_id)}
        </span>
        <span className="text-eyebrow uppercase" style={{ color: 'var(--slate-gray)' }}>
          {rejected ? 'proposal rejected' : 'proposal'} · round {String(data.round)}
        </span>
      </div>
      {rejected ? (
        <div className="mt-3">
          <p className="text-body" style={{ color: 'var(--signal-orange)' }}>
            {String(data.reason)}
          </p>
          <p className="mt-1 text-body">{String(data.rule)}</p>
        </div>
      ) : (
        <p className="mt-3 text-body">{String(data.rationale)}</p>
      )}
      <ParamTable params={(data.params ?? {}) as Record<string, unknown>} />
    </article>
  );
}

export function ProposalStream({ records }: { records: SseRecord[] }) {
  return (
    <div className="mt-8 flex flex-col gap-4">
      {records.map((record, index) => (
        <EventCard key={`${record.event}-${index}`} record={record} />
      ))}
    </div>
  );
}
