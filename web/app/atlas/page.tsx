import { AtlasExplorer } from '@/components/AtlasExplorer';
import { ErrorState } from '@/components/ErrorState';
import { Eyebrow } from '@/components/Eyebrow';
import { loadCoverage, loadVectors } from '@/lib/artifacts';

export default function AtlasPage() {
  const coverage = loadCoverage();
  const vectors = loadVectors();

  if (coverage.missing) {
    return (
      <div className="payloop-section">
        <ErrorState file={coverage.name} target="make loop && make web-data" />
      </div>
    );
  }

  return (
    <div className="payloop-section">
      <Eyebrow>Registry</Eyebrow>
      <h1 className="mt-6 max-w-3xl">
        {coverage.data.total_vectors} vectors. {coverage.data.vectors_with_injector} with live
        simulators.
      </h1>
      <p className="mt-6 max-w-2xl text-body" style={{ color: 'var(--slate-gray)' }}>
        Eight injector modules, twelve injector classes. The greyed rows are documented, not
        simulated. The gap is displayed rather than implied away.
      </p>

      <AtlasExplorer
        coverage={coverage.data}
        vectors={vectors.missing ? [] : vectors.data}
      />
    </div>
  );
}
