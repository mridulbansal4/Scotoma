import { ClaimText } from '@/components/ClaimText';
import { ErrorState } from '@/components/ErrorState';
import { Eyebrow } from '@/components/Eyebrow';
import { FidelityExplorer } from '@/components/FidelityExplorer';
import { loadAblation, loadDistributions, loadFidelityReport } from '@/lib/artifacts';
import { claimFor } from '@/lib/claims';

export default function FidelityPage() {
  const report = loadFidelityReport();
  const ablation = loadAblation();
  const distributions = loadDistributions();

  if (report.missing) {
    return (
      <div className="payloop-section">
        <ErrorState file={report.name} target="make fidelity && make web-data" />
      </div>
    );
  }

  return (
    <div className="payloop-section">
      <Eyebrow>Fidelity gate</Eyebrow>
      <h1 className="mt-6 max-w-3xl">Six layers. Our own ablation fails one of them.</h1>
      <p className="mt-6 max-w-2xl text-body" style={{ color: 'var(--slate-gray)' }}>
        A batch passes only if every active layer passes. One of layers 1, 2 and 5 is held out in
        shadow each round, so a generator cannot be tuned against a fixed set of six checks.
      </p>

      <FidelityExplorer
        rounds={report.data.rounds}
        ablation={ablation.missing ? null : ablation.data}
        distributions={distributions.missing ? null : distributions.data}
      />

      <div className="payloop-card mt-16">
        <ClaimText claim={claimFor('behavioural_degradation_range')} />
      </div>
    </div>
  );
}
