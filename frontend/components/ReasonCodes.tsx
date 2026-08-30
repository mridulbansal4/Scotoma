import type { ReasonCode } from '@/lib/artifacts';

export function ReasonCodes({ codes }: { codes: ReasonCode[] }) {
  if (!codes.length) return null;
  return (
    <ul className="mt-3 flex flex-col gap-2">
      {codes.map((reason) => (
        <li key={`${reason.code}-${reason.feature}`} className="flex flex-wrap items-baseline gap-2">
          <span className="payloop-chip bg-bone">{reason.code}</span>
          <span className="text-body">{reason.label}</span>
          <span className="text-data tabular-nums" style={{ color: 'var(--slate-gray)' }}>
            {reason.feature} = {reason.value.toFixed(reason.value < 1 ? 3 : 1)}
            {reason.shap !== null ? ` · SHAP ${reason.shap.toFixed(3)}` : ''}
          </span>
        </li>
      ))}
    </ul>
  );
}
