'use client';

import { useEffect, useMemo, useState } from 'react';

import type { RoundRecord, SseRecord } from '@/lib/artifacts';

import { AgentModeBadge } from './AgentModeBadge';
import { EmptyState } from './EmptyState';
import { ProposalStream } from './ProposalStream';
import { REPLAY_INTERVAL_MS, ReplayControls } from './ReplayControls';
import { RoundSummaryStrip } from './RoundSummaryStrip';

interface ReplayConsoleProps {
  records: SseRecord[];
  rounds: RoundRecord[];
  agentMode: string;
}

const FIRST_EVENT_COUNT = 1;

export function ReplayConsole({ records, rounds, agentMode }: ReplayConsoleProps) {
  const [cursor, setCursor] = useState(FIRST_EVENT_COUNT);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1);

  useEffect(() => {
    if (!playing || cursor >= records.length) return;
    const timer = window.setTimeout(
      () => setCursor((value) => Math.min(value + 1, records.length)),
      REPLAY_INTERVAL_MS / speed,
    );
    return () => window.clearTimeout(timer);
  }, [playing, cursor, speed, records.length]);

  const roundStarts = useMemo(
    () =>
      records
        .map((record, index) => ({ record, index }))
        .filter((entry) => entry.record.event === 'round_start'),
    [records],
  );

  if (!records.length) {
    return <EmptyState message="No proposals recorded for this run." />;
  }

  return (
    <>
      <div className="mt-8 flex flex-wrap items-center gap-4">
        <AgentModeBadge mode={agentMode} />
        <ReplayControls
          playing={playing}
          speed={speed}
          rounds={roundStarts.map((entry) => Number(entry.record.data.round))}
          onTogglePlay={() => setPlaying((value) => !value)}
          onStep={() => {
            setPlaying(false);
            setCursor((value) => Math.min(value + 1, records.length));
          }}
          onSpeed={setSpeed}
          onJump={(round) => {
            const target = roundStarts.find((entry) => Number(entry.record.data.round) === round);
            if (target) {
              setPlaying(false);
              setCursor(target.index + 1);
            }
          }}
        />
      </div>

      <p className="mt-4 text-data" style={{ color: 'var(--slate-gray)' }}>
        Replaying {cursor} of {records.length} recorded events from{' '}
        <code>runs/&lt;run_id&gt;/sse_log.jsonl</code>. Nothing here is requested at view time.
      </p>

      <div className="mt-8">
        <RoundSummaryStrip rounds={rounds} />
      </div>

      <ProposalStream records={records.slice(0, cursor)} />
    </>
  );
}
