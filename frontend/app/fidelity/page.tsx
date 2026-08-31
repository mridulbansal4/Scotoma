import { ClaimText } from '@/components/ClaimText';
import { ErrorState } from '@/components/ErrorState';
import { Eyebrow } from '@/components/Eyebrow';
import { FidelityExplorer } from '@/components/FidelityExplorer';
import { loadAblation, loadDistributions, loadFidelityReport } from '@/lib/artifacts';
import { claimFor } from '@/lib/claims';

import { InteractiveHeroBox } from '@/components/InteractiveHeroBox';

export default function FidelityPage() {
  const report = loadFidelityReport();
  const ablation = loadAblation();
  const distributions = loadDistributions();

  if (report.missing) {
    return (
      <div className="scotoma-section">
        <ErrorState file={report.name} target="make fidelity && make web-data" />
      </div>
    );
  }

  return (
    <div className="scotoma-section relative">
      {/* Background ambient radial glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-10 left-1/2 -z-10 h-[380px] w-[600px] -translate-x-1/2 opacity-30 blur-[90px]"
        style={{
          background: 'radial-gradient(ellipse at center, #a5bbfc 0%, #d5e2ff 50%, transparent 75%)',
        }}
      />

      <InteractiveHeroBox>
        <div className="flex flex-col items-start max-w-4xl relative z-10">
          <Eyebrow>FIDELITY VERIFICATION LAB</Eyebrow>
          <h1 className="mt-3 text-[38px] md:text-[52px] font-medium leading-[1.08] tracking-tight text-[#1e2033]">
            Six Validation Layers.{' '}
            <span className="sarvam-gradient-text border-b-2 border-indigo-300/60 pb-0.5">
              Ablation fails Layer 5
            </span>
            .
          </h1>
          <p className="mt-4 text-[17px] md:text-[19px] leading-relaxed text-slate-600 max-w-2xl font-medium">
            A batch passes only if every active layer passes. One of layers 1, 2, and 5 is held out in shadow each round, preventing a generator from over-tuning against a fixed set of six checks.
          </p>
        </div>
      </InteractiveHeroBox>

      <div className="mt-12">
        <FidelityExplorer
          rounds={report.data.rounds}
          ablation={ablation.missing ? null : ablation.data}
          distributions={distributions.missing ? null : distributions.data}
        />
      </div>

      <div className="scotoma-card mt-16 border border-slate-200/60 bg-white shadow-sm">
        <ClaimText claim={claimFor('behavioural_degradation_range')} />
      </div>
    </div>
  );
}

