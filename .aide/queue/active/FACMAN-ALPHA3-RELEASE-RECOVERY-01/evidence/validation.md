# Validation

- Tag run `33391586142` passed Windows, macOS, Linux, distribution-contract,
  and exact-six-input jobs.
- The recovered eight-asset set passed `alpha3_release_assets.py verify`.
- All eight GitHub assets were downloaded into a fresh governed directory;
  every SHA-256 matched the uploaded set.
- The evidence ZIP binds source `227257f36b1d37d5ca13ad3b49cbd7d90836790c`,
  tree `1b13eb46dda48672bafda5e458494e2084297251`, and annotated tag object
  `7aec84204521685568d98d5136ebfd529f08a664`.
- `tests.test_alpha3_distribution` passes with release-ordering and limitation
  schema regression coverage.
- Plan views regenerate successfully after terminal `superseded` WorkUnits are
  excluded from near-term queue capacity.
- Full local `tools/strict_check.py` passes against clean detached ULK and USK
  worktrees at the exact alpha.3 pins. Hosted promotion checks remain required
  on the recovery PR and are not replaced by the local result.
