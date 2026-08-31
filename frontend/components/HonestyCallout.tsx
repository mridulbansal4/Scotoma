// The three sentences that must survive contact with a judge. No collapse control and no
// hidden class: tests/test_claims.py asserts this exact text ships.
const CALLOUT_TEXT =
  "This loop measures and shrinks a detector's blind spots. It does not claim to make anyone " +
  'monotonically safer. The blind holdout is one attack family and one entity cohort, neither ' +
  'of which enters any training pool, and it is not independently generated.';

export function HonestyCallout() {
  return (
    <section className="rounded-2xl bg-gradient-to-r from-indigo-50/90 via-blue-50/60 to-white border border-indigo-200/80 p-8 lg:p-10 shadow-sm relative overflow-hidden">
      <div className="absolute top-0 right-0 w-32 h-32 bg-blue-200/20 rounded-full blur-2xl pointer-events-none" />
      <p className="max-w-3xl text-body font-medium text-slate-700 relative z-10">{CALLOUT_TEXT}</p>
    </section>
  );
}
