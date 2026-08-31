import { ErrorState } from '@/components/ErrorState';
import { Eyebrow } from '@/components/Eyebrow';
import { ReplayConsole } from '@/components/ReplayConsole';
import { loadRounds, loadSseLog } from '@/lib/artifacts';

import { InteractiveHeroBox } from '@/components/InteractiveHeroBox';

export default function RedTeamPage() {
  const log = loadSseLog();
  const rounds = loadRounds();

  if (log.missing) {
    return (
      <div className="scotoma-section">
        <ErrorState file={log.name} />
      </div>
    );
  }

  const agentMode = rounds.missing ? 'offline' : (rounds.data[0]?.agent_mode ?? 'offline');

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
          <Eyebrow>RED TEAM ADVERSARY CONSOLE</Eyebrow>
          <h1 className="mt-3 text-[38px] md:text-[52px] font-medium leading-[1.08] tracking-tight text-[#1e2033]">
            The agent proposes.{' '}
            <span className="sarvam-gradient-text border-b-2 border-indigo-300/60 pb-0.5">
              The validator refuses
            </span>
            .
          </h1>
          <p className="mt-4 text-[17px] md:text-[19px] leading-relaxed text-slate-600 max-w-2xl font-medium">
            Proposals are parameter sets for pre-built simulators, validated against vector JSON Schemas and physical plausibility before realization. Invalid proposals are regenerated, never silently clipped.
          </p>
        </div>
      </InteractiveHeroBox>

      <div className="mt-12">
        <ReplayConsole
          records={log.data}
          rounds={rounds.missing ? [] : rounds.data}
          agentMode={agentMode}
        />
      </div>
    </div>
  );
}

