import { AtlasExplorer } from '@/components/AtlasExplorer';
import { ErrorState } from '@/components/ErrorState';
import { InteractiveHeroBox } from '@/components/InteractiveHeroBox';
import { loadCoverage, loadVectors } from '@/lib/artifacts';
import { Eyebrow } from '@/components/Eyebrow';
import { InkButton } from '@/components/InkButton';
import Link from 'next/link';
import { Shield, Sparkles } from 'lucide-react';

// The AtlasPage server component
export default function AtlasPage() {
  const coverage = loadCoverage();
  const vectors = loadVectors();

  if (coverage.missing) {
    return (
      <div className="scotoma-section">
        <ErrorState file={coverage.name} target="make loop && make web-data" />
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
        <Eyebrow>ATTACK COVERAGE MATRIX</Eyebrow>

        <h1 className="mt-2 text-[32px] md:text-[42px] font-medium leading-[1.1] tracking-tight text-[#1e2033]">
          {coverage.data.total_vectors} Attack Vectors.{' '}
          <span className="sarvam-gradient-text border-b-2 border-indigo-300/60 pb-0.5">
            {coverage.data.vectors_with_injector} Live Simulators
          </span>
          .
        </h1>

        <p className="mt-3 text-[15px] md:text-[17px] leading-relaxed text-slate-600 max-w-2xl font-medium">
          Eight injector modules across twelve injector classes. Greyed rows are documented, not simulated — displaying the visibility gap rather than implying perfection.
        </p>

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <Link href="/redteam">
            <InkButton variant="primary">
              <Sparkles size={16} className="text-[#a5bbfc]" />
              <span>Launch Red Agent Simulator</span>
            </InkButton>
          </Link>
          <Link href="/fidelity">
            <InkButton variant="secondary">
              <Shield size={16} className="text-[#1e2033]" />
              <span>View Gate Fidelity Report</span>
            </InkButton>
          </Link>
        </div>
      </InteractiveHeroBox>

      <div className="mt-6">
        <AtlasExplorer
          coverage={coverage.data}
          vectors={vectors.missing ? [] : vectors.data}
        />
      </div>
    </div>
  );
}

