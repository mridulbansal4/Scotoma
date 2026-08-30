import type { Claim } from '@/lib/claims';

const SUFFIX_BY_PROVENANCE: Record<Claim['provenance'], string> = {
  independent: '',
  vendor: 'vendor-reported',
  vendor_commissioned: 'vendor-commissioned',
};

export function ClaimText({ claim }: { claim: Claim | null }) {
  if (!claim) return null;
  const suffix = claim.suffix || SUFFIX_BY_PROVENANCE[claim.provenance];
  return (
    <p className="text-body">
      {claim.approved_text}
      {suffix ? (
        <span style={{ color: 'var(--slate-gray)' }}> — {suffix}.</span>
      ) : null}
    </p>
  );
}
