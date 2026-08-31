import { ErrorState } from '@/components/ErrorState';
import { Eyebrow } from '@/components/Eyebrow';
import { GnnResultCard } from '@/components/GnnResultCard';
import { HonestyCallout } from '@/components/HonestyCallout';
import { MoneyChart } from '@/components/MoneyChart';
import { RecallHeatmap } from '@/components/RecallHeatmap';
import { RoundTimeline } from '@/components/RoundTimeline';
import { ScopeMatrix } from '@/components/ScopeMatrix';
import { loadGnn, loadManifest, loadRounds, loadScopeMatrix } from '@/lib/artifacts';

import { InteractiveHeroBox } from '@/components/InteractiveHeroBox';

export default function LoopPage() {
  const rounds = loadRounds();
  const manifest = loadManifest();
  const scope = loadScopeMatrix();
  const gnn = loadGnn();

  if (rounds.missing) {
    return (
      <div className="scotoma-section">
        <ErrorState file={rounds.name} target="make loop && make web-data" />
      </div>
    );
  }

  const holdout = manifest.missing ? [] : manifest.data.blind_holdout_vectors;

  return (
    <div className="scotoma-section relative">
      <InteractiveHeroBox>
        <div className="flex flex-col items-start max-w-4xl relative z-10">
          <Eyebrow>CLOSED-LOOP ADVERSARIAL METRICS</Eyebrow>
          <h1 className="mt-3 text-[38px] md:text-[52px] font-medium leading-[1.08] tracking-tight text-[#1e2033]">
            Evasion falls.{' '}
            <span className="sarvam-gradient-text border-b-2 border-indigo-300/60 pb-0.5">
              Blind holdouts barely move
            </span>
            .
          </h1>
          <p className="mt-4 text-[17px] md:text-[19px] leading-relaxed text-slate-600 max-w-2xl font-medium">
            That is the core finding. Empirical measurement across adversarial iterations without masking or false assurances.
          </p>
        </div>
      </InteractiveHeroBox>

      <div className="mt-12">
        <MoneyChart rounds={rounds.data} />
      </div>

      <div className="mt-10">
        <HonestyCallout />
      </div>

      <section className="mt-16">
        <h2 className="text-[28px] md:text-[32px] font-medium text-[#1e2033]">Round by round</h2>
        <div className="mt-8">
          <RoundTimeline rounds={rounds.data} />
        </div>
      </section>

      <section className="mt-16">
        <h2 className="text-[28px] md:text-[32px] font-medium text-[#1e2033]">Recall per vector, per round</h2>
        <p className="mt-3 max-w-2xl text-[16px] text-slate">
          The vectors that perform poorly are displayed at the exact same weight as high-performing ones.
        </p>
        <div className="mt-8">
          <RecallHeatmap rounds={rounds.data} holdoutVectors={holdout} />
        </div>
      </section>

      {scope.missing ? null : (
        <section className="mt-16">
          <h2 className="text-[28px] md:text-[32px] font-medium text-[#1e2033]">Party-scope projection</h2>
          <div className="mt-8">
            <ScopeMatrix data={scope.data} />
          </div>
        </section>
      )}

      {gnn.missing ? null : (
        <section className="mt-16">
          <GnnResultCard gnn={gnn.data} />
        </section>
      )}
    </div>
  );
}
