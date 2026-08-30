'use client';

import { useState } from 'react';

import type { AblationPayload, Distributions, GatePayload } from '@/lib/artifacts';

import { AblationComparison } from './AblationComparison';
import { DistributionOverlay, OverlayMode } from './DistributionOverlay';
import { GateCardGrid } from './GateCardGrid';
import { InkButton } from './InkButton';

interface FidelityExplorerProps {
  rounds: (GatePayload & { round: number })[];
  ablation: AblationPayload | null;
  distributions: Distributions | null;
}

const OVERLAY_MODES: OverlayMode[] = ['real', 'synthetic', 'both'];

export function FidelityExplorer({ rounds, ablation, distributions }: FidelityExplorerProps) {
  const [roundIndex, setRoundIndex] = useState(0);
  const [mode, setMode] = useState<OverlayMode>('both');
  const gate = rounds[Math.min(roundIndex, rounds.length - 1)] ?? null;

  return (
    <>
      <div className="mt-12 flex flex-wrap items-center gap-3">
        <span className="mr-2 text-eyebrow uppercase" style={{ color: 'var(--slate-gray)' }}>
          Round
        </span>
        {rounds.map((entry, index) => (
          <InkButton
            key={entry.round}
            variant="secondary"
            pressed={index === roundIndex}
            onClick={() => setRoundIndex(index)}
          >
            {entry.round + 1}
          </InkButton>
        ))}
      </div>

      {gate ? (
        <div className="mt-8">
          <GateCardGrid gate={gate} />
        </div>
      ) : null}

      {gate && ablation ? <AblationComparison simulator={gate} ablation={ablation} /> : null}

      {distributions ? (
        <section className="mt-16">
          <div className="flex flex-wrap items-center gap-3">
            <span className="mr-2 text-eyebrow uppercase" style={{ color: 'var(--slate-gray)' }}>
              Overlay
            </span>
            {OVERLAY_MODES.map((value) => (
              <InkButton
                key={value}
                variant="secondary"
                pressed={mode === value}
                onClick={() => setMode(value)}
              >
                {value}
              </InkButton>
            ))}
          </div>

          <div className="mt-8 grid gap-6 lg:grid-cols-2">
            <DistributionOverlay
              title="Amount"
              xLabel="log10 amount"
              yLabel="density"
              real={distributions.amount.real}
              synthetic={distributions.amount.synthetic}
              mode={mode}
            />
            <DistributionOverlay
              title="Hour of day"
              xLabel="hour"
              yLabel="share of events"
              real={distributions.hour_of_day.real}
              synthetic={distributions.hour_of_day.synthetic}
              mode={mode}
            />
            <DistributionOverlay
              title="Inter-arrival time"
              xLabel="log10 seconds"
              yLabel="density"
              real={distributions.interarrival.real}
              synthetic={distributions.interarrival.synthetic}
              mode={mode}
            />
            <DistributionOverlay
              title="Merchant degree"
              xLabel="log10 degree"
              yLabel="density"
              real={distributions.merchant_degree.real}
              synthetic={distributions.merchant_degree.synthetic}
              mode={mode}
              powerLawAlpha={distributions.merchant_degree.power_law_alpha}
            />
          </div>
        </section>
      ) : null}
    </>
  );
}
