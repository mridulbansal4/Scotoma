// The three sentences that must survive contact with a judge. No collapse control and no
// hidden class: tests/test_claims.py asserts this exact text ships.
const CALLOUT_TEXT =
  "This loop measures and shrinks a detector's blind spots. It does not claim to make anyone " +
  'monotonically safer. The blind holdout is one attack family and one entity cohort, neither ' +
  'of which enters any training pool — it is not independently generated.';

export function HonestyCallout() {
  return (
    <section className="rounded-stadium bg-lifted p-8 lg:p-10">
      <p className="max-w-3xl text-body">{CALLOUT_TEXT}</p>
    </section>
  );
}
