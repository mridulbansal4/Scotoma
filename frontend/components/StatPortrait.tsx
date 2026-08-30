import { ArrowUpRight } from 'lucide-react';

interface StatPortraitProps {
  value: string;
  label: string;
  caption: string;
  satellite?: boolean;
}

const SATELLITE_SIZE = 56;
const ICON_SIZE = 20;

export function StatPortrait({ value, label, caption, satellite = true }: StatPortraitProps) {
  return (
    <figure className="flex flex-col items-center text-center">
      <div className="relative">
        <div className="flex h-[220px] w-[220px] items-center justify-center rounded-full bg-lifted shadow-card lg:h-[260px] lg:w-[260px]">
          <span className="payloop-readout">{value}</span>
        </div>
        {satellite ? (
          <span
            className="absolute -bottom-2 -right-2 flex items-center justify-center rounded-full bg-white"
            style={{ width: SATELLITE_SIZE, height: SATELLITE_SIZE }}
            aria-hidden
          >
            <ArrowUpRight size={ICON_SIZE} />
          </span>
        ) : null}
      </div>
      <figcaption className="mt-6 max-w-[260px]">
        <p className="text-eyebrow uppercase" style={{ color: 'var(--slate-gray)' }}>
          {label}
        </p>
        <p className="mt-2 text-body">{caption}</p>
      </figcaption>
    </figure>
  );
}
