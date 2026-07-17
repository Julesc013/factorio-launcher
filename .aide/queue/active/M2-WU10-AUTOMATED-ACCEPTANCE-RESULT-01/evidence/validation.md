# Validation

Result: blocked before `EvidencePass`; no acceptance result recorded.

- Rebuilt `usk_live_acceptance` and `usk_interruption_recovery_smoke` from
  pinned Universal Setup revision `3f8489275077347c2918f3bb03614ec6431362ff`:
  PASS.
- Fresh lifecycle run `m2wu10-20260717-01`: runner PASS.
- Fresh interruption run `m2wu10-20260717-01-interruptions`: runner PASS.
- Frozen verifier from accepted policy revision
  `7a3f812ab0f81fb35e2e6104bd573d8832a44e59`: FAIL CLOSED before
  `EvidencePass`.

The verifier rejected all eighteen lifecycle and interruption journals because
their compact deterministic native field order differs from sorted-key
canonical JSON. The verifier nevertheless parses those documents and is
designed to recompute their transaction chains, contained roots, and journal
digests. PR A's generated fixture used sorted-key JSON and therefore did not
exercise the native serialization format.

No observation output file was created.
