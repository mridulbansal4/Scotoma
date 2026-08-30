import type { AblationPayload, GatePayload } from '@/lib/artifacts';

import { GateCardGrid } from './GateCardGrid';

interface AblationComparisonProps {
  simulator: GatePayload;
  ablation: AblationPayload;
}

function verdict(gate: GatePayload, layer: string): string {
  return gate.layers[layer]?.passed ? 'passed' : 'failed';
}

function metric(gate: GatePayload, layer: string, key: string): string {
  const value = gate.layers[layer]?.[key];
  return typeof value === 'number' ? value.toFixed(value < 1 ? 4 : 2) : '—';
}

export function AblationComparison({ simulator, ablation }: AblationComparisonProps) {
  return (
    <section className="mt-16">
      <div className="grid gap-10 lg:grid-cols-2">
        <div>
          <h3>PayLoop simulator</h3>
          <p className="mt-2 text-body" style={{ color: 'var(--slate-gray)' }}>
            Entity-aware process output, gated against a held-out legitimate partition.
          </p>
          <div className="mt-6">
            <GateCardGrid gate={simulator} columns={2} />
          </div>
        </div>
        <div>
          <h3>{ablation.generator} ablation</h3>
          <p className="mt-2 text-body" style={{ color: 'var(--slate-gray)' }}>
            Our own row-independent baseline, fitted on {ablation.fit_rows.toLocaleString()} rows and
            pushed through the identical gate.
          </p>
          <div className="mt-6">
            <GateCardGrid gate={ablation} columns={2} />
          </div>
        </div>
      </div>

      <p className="mt-10 max-w-3xl text-body">
        The ablation {verdict(ablation, 'utility')} the utility layer at a transfer ratio of{' '}
        {metric(ablation, 'utility', 'tstr_ratio')} and {verdict(ablation, 'behavioral')} the
        behavioural layer at a composite of {metric(ablation, 'behavioral', 'composite')} against a
        ceiling of {ablation.behavioral_max.toFixed(1)}. Its within-entity inter-event-time
        autocorrelation is {metric(ablation, 'behavioral', 'iet_autocorr_batch')} against{' '}
        {metric(ablation, 'behavioral', 'iet_autocorr_reference')} for the reference population.
        Naming the generator here is accurate: it is PayLoop&apos;s own ablation baseline.
      </p>
    </section>
  );
}
