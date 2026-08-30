import { ErrorState } from '@/components/ErrorState';
import { Eyebrow } from '@/components/Eyebrow';
import { ReplayConsole } from '@/components/ReplayConsole';
import { loadRounds, loadSseLog } from '@/lib/artifacts';

export default function RedTeamPage() {
  const log = loadSseLog();
  const rounds = loadRounds();

  if (log.missing) {
    return (
      <div className="payloop-section">
        <ErrorState file={log.name} />
      </div>
    );
  }

  const agentMode = rounds.missing ? 'offline' : (rounds.data[0]?.agent_mode ?? 'offline');

  return (
    <div className="payloop-section">
      <Eyebrow>Red team</Eyebrow>
      <h1 className="mt-6 max-w-3xl">
        The agent proposes. The constraint validator refuses.
      </h1>
      <p className="mt-6 max-w-2xl text-body" style={{ color: 'var(--slate-gray)' }}>
        Proposals are parameter sets for pre-built simulators, validated against each vector&apos;s
        JSON Schema and against physical plausibility before anything is realised. Invalid proposals
        are regenerated, never silently clipped.
      </p>

      <ReplayConsole
        records={log.data}
        rounds={rounds.missing ? [] : rounds.data}
        agentMode={agentMode}
      />
    </div>
  );
}
