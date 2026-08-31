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

import { InteractiveHeroBox } from '@/components/InteractiveHeroBox';

export default function SocPage() {
  const alerts = loadAlerts();
  const manifest = loadManifest();
  const recall = loadPerVectorRecall();
  const latency = loadLatency();
  const rounds = loadRounds();

  if (alerts.missing || manifest.missing) {
    return (
      <div className="scotoma-section">
        <ErrorState file={alerts.missing ? alerts.name : 'manifest.json'} />
      </div>
    );
  }

  const lastRound = rounds.missing ? null : rounds.data[rounds.data.length - 1];
  const threshold = lastRound?.threshold ?? manifest.data.ladder_bands.approve_max;

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
          <Eyebrow>BLUE TEAM OPERATIONAL CONSOLE</Eyebrow>
          <h1 className="mt-3 text-[38px] md:text-[52px] font-medium leading-[1.08] tracking-tight text-[#1e2033]">
            Real-Time Threat Telemetry.{' '}
            <span className="sarvam-gradient-text border-b-2 border-indigo-300/60 pb-0.5">
              Explicit Reason Codes
            </span>
            .
          </h1>
          <p className="mt-4 text-[17px] md:text-[19px] leading-relaxed text-slate-600 max-w-2xl font-medium">
            Every alert carries its reason codes, ladder band, and exact financial cost of action. Zero opaque scores.
          </p>
        </div>
      </InteractiveHeroBox>

      <div className="mt-12">
        <SocConsole
          alerts={alerts.data}
          bands={manifest.data.ladder_bands}
          costMatrix={manifest.data.cost_matrix}
          threshold={threshold}
        />
      </div>

      <div className="mt-16 grid gap-8 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        {recall.missing ? null : (
          <VectorRecallPanel
            recall={recall.data.recall}
            holdoutVectors={manifest.data.blind_holdout_vectors}
          />
        )}

        {latency.missing ? null : (
          <aside className="scotoma-card flex flex-col gap-8 border border-slate-200/60 bg-white">
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
            <p className="text-data text-slate-500">
              {latency.data.iterations.toLocaleString()} single-row scoring calls on {latency.data.host},
              first {latency.data.warmup} discarded.
            </p>
          </aside>
        )}
      </div>
    </div>
  );
}

