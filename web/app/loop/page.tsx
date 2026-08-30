import { ErrorState } from '@/components/ErrorState';
import { Eyebrow } from '@/components/Eyebrow';
import { GnnResultCard } from '@/components/GnnResultCard';
import { HonestyCallout } from '@/components/HonestyCallout';
import { MoneyChart } from '@/components/MoneyChart';
import { RecallHeatmap } from '@/components/RecallHeatmap';
import { RoundTimeline } from '@/components/RoundTimeline';
import { ScopeMatrix } from '@/components/ScopeMatrix';
import { loadGnn, loadManifest, loadRounds, loadScopeMatrix } from '@/lib/artifacts';

export default function LoopPage() {
  const rounds = loadRounds();
  const manifest = loadManifest();
  const scope = loadScopeMatrix();
  const gnn = loadGnn();

  if (rounds.missing) {
    return (
      <div className="payloop-section">
        <ErrorState file={rounds.name} target="make loop && make web-data" />
      </div>
    );
  }

  const holdout = manifest.missing ? [] : manifest.data.blind_holdout_vectors;

  return (
    <div className="payloop-section">
      <Eyebrow>The loop</Eyebrow>
      <h1 className="mt-6 max-w-4xl">
        Evasion falls. The blind holdout barely moves. That is the finding.
      </h1>

      <div className="mt-12">
        <MoneyChart rounds={rounds.data} />
      </div>

      <div className="mt-10">
        <HonestyCallout />
      </div>

      <section className="mt-16">
        <h2>Round by round</h2>
        <div className="mt-8">
          <RoundTimeline rounds={rounds.data} />
        </div>
      </section>

      <section className="mt-16">
        <h2>Recall per vector, per round</h2>
        <p className="mt-4 max-w-2xl text-body" style={{ color: 'var(--slate-gray)' }}>
          The vectors that do badly are shown at the same weight as the ones that do well.
        </p>
        <div className="mt-8">
          <RecallHeatmap rounds={rounds.data} holdoutVectors={holdout} />
        </div>
      </section>

      {scope.missing ? null : (
        <section className="mt-16">
          <h2>Party-scope projection</h2>
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
