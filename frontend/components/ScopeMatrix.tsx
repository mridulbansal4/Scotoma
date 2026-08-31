'use client';

import { useState } from 'react';

import type { ScopeMatrix as ScopeMatrixData } from '@/lib/artifacts';
import { inkScale, readableOn } from '@/lib/format';

import { InkButton } from './InkButton';

const SCOPES = ['ISSUER', 'ACQUIRER', 'NETWORK'] as const;
type Scope = (typeof SCOPES)[number] | 'none';

// A twenty-point PR-AUC gap between network and issuer is unambiguous; smaller gaps are
// noise at this sample size.
const SCOPE_COLLAPSE_DELTA = 0.2;
const SCORE_DIGITS = 3;

export function ScopeMatrix({ data }: { data: ScopeMatrixData }) {
  const [highlight, setHighlight] = useState<Scope>('none');
  const vectors = Object.keys(data.matrix).sort();

  return (
    <section>
      <div className="flex flex-wrap items-center gap-2">
        <span className="mr-2 text-eyebrow uppercase" style={{ color: 'var(--slate-gray)' }}>
          Highlight scope
        </span>
        {[...SCOPES, 'none' as const].map((scope) => (
          <InkButton
            key={scope}
            variant="secondary"
            pressed={highlight === scope}
            onClick={() => setHighlight(scope)}
          >
            {scope.toLowerCase()}
          </InkButton>
        ))}
      </div>

      <div className="scotoma-scroll-x mt-6">
        <table className="w-full min-w-[560px] border-separate border-spacing-1">
          <thead>
            <tr className="text-eyebrow uppercase" style={{ color: 'var(--slate-gray)' }}>
              <th className="px-3 py-2 text-left">Vector</th>
              {SCOPES.map((scope) => (
                <th key={scope} className="px-3 py-2">
                  {scope}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {vectors.map((vector) => {
              const row = data.matrix[vector];
              const issuer = row.ISSUER;
              const network = row.NETWORK;
              const collapsed =
                issuer !== undefined && network !== undefined && network - issuer > SCOPE_COLLAPSE_DELTA;
              return (
                <tr key={vector}>
                  <th className="px-3 py-2 text-left text-data">{vector}</th>
                  {SCOPES.map((scope) => {
                    const value = row[scope];
                    const present = value !== undefined;
                    return (
                      <td
                        key={`${vector}-${scope}`}
                        className="rounded-button px-3 py-2 text-center text-data tabular-nums"
                        style={{
                          background: inkScale(present ? value : null),
                          color: readableOn(present ? value : null),
                          outline: collapsed ? '2px solid var(--light-signal-orange)' : 'none',
                          opacity: highlight === 'none' || highlight === scope ? 1 : 0.45,
                        }}
                      >
                        {present ? value.toFixed(SCORE_DIGITS) : '—'}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <ul className="mt-6 flex flex-col gap-1">
        {SCOPES.map((scope) => {
          const status = data.status?.[scope];
          if (!status || status.status === 'fitted') return null;
          return (
            <li key={scope} className="text-data" style={{ color: 'var(--signal-orange)' }}>
              {scope} could not fit a detector at all: {status.positives} fraud events across{' '}
              {status.rows.toLocaleString()} visible rows. That is the asymmetry in its strongest
              form, not a missing column.
            </li>
          );
        })}
      </ul>

      <p className="mt-6 max-w-3xl text-body">
        Same detector, three visibility masks. We operationalise a known asymmetry; we did not
        discover it.
      </p>
    </section>
  );
}
