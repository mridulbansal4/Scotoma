import type { Alert, LadderBands as Bands } from '@/lib/artifacts';
import { count, rate } from '@/lib/format';

interface LadderBandsProps {
  alerts: Alert[];
  bands: Bands;
  threshold: number;
}

const BAND_SHADES = ['var(--soft-bone)', 'var(--ghost-cream)', 'var(--dust-taupe)', 'var(--ink-black)'];

function bandFor(score: number, bands: Bands): number {
  if (score < bands.approve_max) return 0;
  if (score < bands.stepup_max) return 1;
  if (score < bands.hold_max) return 2;
  return 3;
}

export function LadderBands({ alerts, bands, threshold }: LadderBandsProps) {
  const labels = [
    `< ${rate(bands.approve_max, 2)} APPROVE`,
    `${rate(bands.approve_max, 2)}–${rate(bands.stepup_max, 2)} STEP-UP (3DS)`,
    `${rate(bands.stepup_max, 2)}–${rate(bands.hold_max, 2)} HOLD`,
    `≥ ${rate(bands.hold_max, 2)} DECLINE + SAR QUEUE`,
  ];
  const counts = [0, 0, 0, 0];
  for (const alert of alerts) {
    if (alert.score >= threshold) counts[bandFor(alert.score, bands)] += 1;
  }

  return (
    <section>
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        {labels.map((label, index) => (
          <div
            key={label}
            className="rounded-pill px-6 py-5"
            style={{
              background: BAND_SHADES[index],
              color: index === 3 ? 'var(--canvas-cream)' : 'var(--ink-black)',
            }}
          >
            <p className="text-eyebrow uppercase">{label}</p>
            <p className="mt-3 text-card tabular-nums">{count(counts[index])}</p>
          </div>
        ))}
      </div>
      <p className="mt-4 text-body">
        No autonomous block below {rate(bands.hold_max, 2)}; a human is in the loop for the
        consequential action.
      </p>
    </section>
  );
}
