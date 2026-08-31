'use client';

const RAILS = ['CARD_CNP', 'CARD_CP', 'UPI', 'SEPA_INST', 'ACH', 'AGENTIC'];
const STATUSES = ['documented', 'emerging', 'speculative'];

export interface AtlasFilters {
  rails: string[];
  statuses: string[];
  injectorOnly: boolean;
}

interface FilterBarProps {
  filters: AtlasFilters;
  onChange: (next: AtlasFilters) => void;
}

function toggle(values: string[], value: string): string[] {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function Chip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`inline-flex items-center rounded-full px-4 py-1.5 text-xs font-semibold border transition-all duration-200 ${
        active
          ? 'bg-[#1e2033] text-white border-[#1e2033] shadow-sm scale-[1.02]'
          : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50 hover:border-slate-300'
      }`}
    >
      {label}
    </button>
  );
}

export function FilterBar({ filters, onChange }: FilterBarProps) {
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="mr-2 text-xs font-bold uppercase tracking-wider text-slate-500">
          Rail
        </span>
        {RAILS.map((rail) => (
          <Chip
            key={rail}
            label={rail}
            active={filters.rails.includes(rail)}
            onClick={() => onChange({ ...filters, rails: toggle(filters.rails, rail) })}
          />
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="mr-2 text-xs font-bold uppercase tracking-wider text-slate-500">
          Status
        </span>
        {STATUSES.map((status) => (
          <Chip
            key={status}
            label={status}
            active={filters.statuses.includes(status)}
            onClick={() => onChange({ ...filters, statuses: toggle(filters.statuses, status) })}
          />
        ))}
        <Chip
          label="Only vectors with injectors"
          active={filters.injectorOnly}
          onClick={() => onChange({ ...filters, injectorOnly: !filters.injectorOnly })}
        />
      </div>
    </div>
  );
}
