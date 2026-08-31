# Real-floor experiment, 31 Aug 2026

Run with FIDELITY_FLOOR_SOURCE=real: the fidelity gate reference is the Sparkov
floor partition rather than Scotoma-generated traffic.

All three rounds rejected. Composite behavioural 13.20, 13.25, 13.33 against a
threshold of 10.0.

The two comparable velocity ratios are velocity_pan_token 48.97 and
velocity_merchant_id 83.62. device_id is listed under not_comparable_keys because
Sparkov has no device column. Inter-event-time autocorrelation is 1.40, which is
close to parity; graph motif is 5.28.

The velocity failure is dominated by population density, not by generator
realism. Measured on the same frames:

  Sparkov floor      939 cards    2.6985 events/card/day   iet_std  46,710 s
  Scotoma synthetic  34,152 cards 0.2966 events/card/day   iet_std 457,590 s

Each Sparkov card is roughly nine times busier than a Scotoma card. Comparing
inter-event-time spread across two populations of such different density measures
the density gap first and realism second. Before this ratio can be read as a
fidelity statement, either the generator population has to be matched to the
reference or the ratio has to be normalised by events per key per day.

The shipped run in runs/2026-08-31-final uses the synthetic reference, which is
the default.
