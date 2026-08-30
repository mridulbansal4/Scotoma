import { readJson } from './artifacts';

export interface Claim {
  key: string;
  value: string;
  scope: string;
  provenance: 'independent' | 'vendor' | 'vendor_commissioned';
  attribution: string;
  approved_text: string;
  suffix: string;
}

// Every externally quotable number on these screens resolves to one of these entries.
// Adding a figure to the UI without adding it here fails tests/test_claims.py.
export function loadClaims(): Record<string, Claim> {
  const result = readJson<Claim[]>('claims.json');
  if (result.missing || !result.data) return {};
  return Object.fromEntries(result.data.map((claim) => [claim.key, claim]));
}

export function claimFor(key: string): Claim | null {
  return loadClaims()[key] ?? null;
}
