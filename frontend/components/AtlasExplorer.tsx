'use client';

import { useMemo, useState } from 'react';

import type { Coverage, VectorEntry } from '@/lib/artifacts';
import { percent } from '@/lib/format';

import { EmptyState } from './EmptyState';
import { AtlasFilters, FilterBar } from './FilterBar';
import { StatPortrait } from './StatPortrait';
import { VectorDetailPanel } from './VectorDetailPanel';
import { VectorTable } from './VectorTable';

// The client boundary for the atlas: the page reads the artefacts on the server and this
// owns the filter and selection state the three controls below it share.
const INITIAL_FILTERS: AtlasFilters = { rails: [], statuses: [], injectorOnly: false };

interface AtlasExplorerProps {
  coverage: Coverage;
  vectors: VectorEntry[];
}

export function AtlasExplorer({ coverage, vectors }: AtlasExplorerProps) {
  const [filters, setFilters] = useState<AtlasFilters>(INITIAL_FILTERS);
  const [selected, setSelected] = useState<string | null>(null);

  const rows = useMemo(
    () =>
      coverage.rows.filter((row) => {
        if (filters.rails.length && !row.rails.some((rail) => filters.rails.includes(rail))) {
          return false;
        }
        if (filters.statuses.length && !filters.statuses.includes(row.status)) return false;
        if (filters.injectorOnly && !row.has_injector) return false;
        return true;
      }),
    [coverage, filters],
  );

  const simulated = rows.filter((row) => row.has_injector).length;
  const vector = vectors.find((entry) => entry.id === selected) ?? null;

  return (
    <>
      <div className="mt-8 grid gap-8 md:grid-cols-3">
        <StatPortrait
          value={String(coverage.total_vectors)}
          label="Documented"
          caption={`${coverage.counts.documented} documented, ${coverage.counts.emerging} emerging, ${coverage.counts.speculative} speculative.`}
          href="#vectors"
        />
        <StatPortrait
          value={String(coverage.vectors_with_injector)}
          label="Simulated"
          caption={`${coverage.injector_modules} modules and ${coverage.injector_classes} classes ship as live simulators.`}
          href="/redteam"
        />
        <StatPortrait
          value={percent(rows.length ? simulated / rows.length : 0, 1)}
          label="Coverage in view"
          caption="Recomputed against the current filters, not a fixed headline."
          href="/loop"
        />
      </div>

      <div className="mt-8" id="vectors">
        <FilterBar filters={filters} onChange={setFilters} />
      </div>

      {rows.length ? (
        <VectorTable rows={rows} selected={selected} onSelect={setSelected} />
      ) : (
        <div className="mt-8">
          <EmptyState message="No vectors match these filters." />
        </div>
      )}

      {vector ? (
        <VectorDetailPanel
          vector={vector}
          row={coverage.rows.find((row) => row.vector_id === vector.id)}
          onClose={() => setSelected(null)}
        />
      ) : null}
    </>
  );
}
