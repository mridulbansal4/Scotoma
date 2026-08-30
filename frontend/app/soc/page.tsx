import { ErrorState } from '@/components/ErrorState';
import { Eyebrow } from '@/components/Eyebrow';
import { LatencyFigure } from '@/components/LatencyFigure';
import { SocConsole } from '@/components/SocConsole';
import { VectorRecallPanel } from '@/components/VectorRecallPanel';
import {
  loadAlerts,
  loadLatency,
  loadManifest,
  loadPerVectorRecall,
  loadRounds,
} from '@/lib/artifacts';

export default function SocPage() {
  const alerts = loadAlerts();
  const manifest = loadManifest();
  const recall = loadPerVectorRecall();
  const latency = loadLatency();
  const rounds = loadRounds();

  if (alerts.missing || manifest.missing) {
    return (
      <div className="payloop-section">
        <ErrorState file={alerts.missing ? alerts.name : 'manifest.json'} />
      </div>
    );
  }

  const lastRound = rounds.missing ? null : rounds.data[rounds.data.length - 1];
  const threshold = lastRound?.threshold ?? manifest.data.ladder_bands.approve_max;

  return (
    <div className="payloop-section">
      <Eyebrow>Blue team</Eyebrow>
      <h1 className="mt-6 max-w-3xl">
        Every alert carries its reasons, its band, and the cost of acting on it.
      </h1>

      <SocConsole
        alerts={alerts.data}
        bands={manifest.data.ladder_bands}
        costMatrix={manifest.data.cost_matrix}
        threshold={threshold}
      />

      <div className="mt-16 grid gap-8 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        {recall.missing ? null : (
          <VectorRecallPanel
            recall={recall.data.recall}
            holdoutVectors={manifest.data.blind_holdout_vectors}
          />
        )}

        {latency.missing ? null : (
          <aside className="payloop-card flex flex-col gap-8">
            <LatencyFigure label="p50 model scoring" value={latency.data.p50_ms} source="measured" />
            <LatencyFigure label="p95 model scoring" value={latency.data.p95_ms} source="measured" />
            <LatencyFigure
              label="p99 model scoring"
              value={latency.data.p99_ms}
              source="measured"
              note={latency.data.path}
            />
            <LatencyFigure
              label="Engineering target, total inline path"
              value={latency.data.targets.inline_total_ms}
              source="target"
            />
            <LatencyFigure
              label="HyperLogLog feature lookup"
              value={latency.data.feature_lookup?.p99_ms ?? latency.data.feature_lookup?.target_ms ?? 0}
              source={latency.data.feature_lookup?.source === 'measured' ? 'measured' : 'unavailable'}
              note={latency.data.feature_lookup?.reason}
            />
            <p className="text-data" style={{ color: 'var(--slate-gray)' }}>
              {latency.data.iterations.toLocaleString()} single-row scoring calls on {latency.data.host},
              first {latency.data.warmup} discarded.
            </p>
          </aside>
        )}
      </div>
    </div>
  );
}
