# Remaining risks

- The repaired exact head still requires the complete hosted Linux, Windows,
  macOS, security, schema, package, reproducibility, sanitizer, fuzz, and
  coverage matrix before merge.
- The local runtime identity correctly reports `source_dirty=true` because it
  was built before commit. Hosted clean checkouts must report `false`.
- The legacy WinForms artifact and the opt-in bounded performance corpus remain
  classified optional in this local matrix.
- Two Windows symlink negative controls remain classified unsupported because
  this host cannot create the required links; hosted platform lanes remain the
  portability proof.
- Visual Studio invokes the selected multi-target fast graph less efficiently
  than a future generated aggregate target could. This is a performance
  follow-up, not a correctness or coverage gap.
- Durable operation outcome semantics, candidate/runtime separation, fresh
  candidate qualification, human revalidation, exact route promotion, and the
  player alpha remain downstream.

There is still no product Play authority and no accepted real-Play route.
