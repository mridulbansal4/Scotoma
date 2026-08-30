import type { GatePayload } from '@/lib/artifacts';

import { GateCard } from './GateCard';

export const LAYER_ORDER = [
  'marginal',
  'joint',
  'behavioral',
  'utility',
  'adversarial',
  'privacy',
] as const;

export const HEADLINE_METRIC: Record<string, string> = {
  marginal: 'ks_column_pass_frac',
  joint: 'pcd',
  behavioral: 'composite',
  utility: 'tstr_ratio',
  adversarial: 'discriminator_auc',
  privacy: 'mia_auc',
};

export const LAYER_THRESHOLD: Record<string, string> = {
  marginal: 'KS pass fraction must reach 0.90',
  joint: 'correlation difference must stay under 0.15',
  behavioral: 'composite must stay under 10.0',
  utility: 'train-synthetic transfer must reach 0.90 of baseline',
  adversarial: 'discriminator AUC must sit between 0.50 and 0.65',
  privacy: 'membership inference AUC must sit between 0.50 and 0.55',
};

interface GateCardGridProps {
  gate: GatePayload;
  columns?: 2 | 3;
}

export function GateCardGrid({ gate, columns = 3 }: GateCardGridProps) {
  return (
    <div
      className={`grid gap-6 ${columns === 3 ? 'md:grid-cols-2 lg:grid-cols-3' : 'md:grid-cols-2'}`}
    >
      {LAYER_ORDER.map((name) => {
        const layer = gate.layers[name];
        if (!layer) return null;
        return (
          <GateCard
            key={name}
            name={name}
            layer={layer}
            headlineMetric={HEADLINE_METRIC[name]}
            threshold={LAYER_THRESHOLD[name]}
            shadow={gate.shadow_layer === name}
          />
        );
      })}
    </div>
  );
}
