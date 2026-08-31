'use client';

import { Pause, Play, SkipForward } from 'lucide-react';

import { InkButton } from './InkButton';

export const REPLAY_INTERVAL_MS = 400;
export const SPEEDS = [0.5, 1, 2, 4] as const;

interface ReplayControlsProps {
  playing: boolean;
  speed: number;
  rounds: number[];
  onTogglePlay: () => void;
  onStep: () => void;
  onSpeed: (speed: number) => void;
  onJump: (round: number) => void;
}

const ICON_SIZE = 16;

export function ReplayControls({
  playing,
  speed,
  rounds,
  onTogglePlay,
  onStep,
  onSpeed,
  onJump,
}: ReplayControlsProps) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <InkButton onClick={onTogglePlay} ariaLabel={playing ? 'Pause replay' : 'Play replay'}>
        <span className="flex items-center gap-2">
          {playing ? <Pause size={ICON_SIZE} /> : <Play size={ICON_SIZE} />}
          {playing ? 'Pause' : 'Play'}
        </span>
      </InkButton>
      <InkButton variant="secondary" onClick={onStep} ariaLabel="Advance one event">
        <span className="flex items-center gap-2">
          <SkipForward size={ICON_SIZE} />
          Step
        </span>
      </InkButton>
      <div className="flex items-center gap-2">
        {SPEEDS.map((value) => (
          <InkButton
            key={value}
            variant="secondary"
            pressed={speed === value}
            onClick={() => onSpeed(value)}
          >
            {value}x
          </InkButton>
        ))}
      </div>
      {rounds.length ? (
        <label className="flex items-center gap-3 text-data">
          <span className="font-medium" style={{ color: 'var(--slate-gray)' }}>Jump to round</span>
          <select
            className="rounded-pill border-[1.5px] border-ink bg-white px-3 py-1.5 text-[14px] font-medium cursor-pointer leading-none focus:outline-none"
            onChange={(event) => onJump(Number(event.target.value))}
            defaultValue=""
          >
            <option value="" disabled>
              select
            </option>
            {rounds.map((round) => (
              <option key={round} value={round}>
                {round + 1}
              </option>
            ))}
          </select>
        </label>
      ) : null}
    </div>
  );
}
