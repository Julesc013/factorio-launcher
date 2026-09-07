# Changed files

## Canonical active-release authority

- Added `release/index/active_release_view.v1.toml` as the sole selector for
  the three current product profiles, two explicitly selected previews, and
  canonical eight-asset release shape.
- Added its closed schema, fail-closed validator, negative-control suite, and
  strict/hosted schema-workflow registration.
- Classified the broader profile, package, producer, support, distribution,
  update, artifact, and receipt inventories as active, preview, historical, or
  future without deleting compatibility evidence.

## Generated and user-facing projections

- Made project-state generation consume the selector and expose only Windows
  x64, macOS Intel x64, and Linux x64 as current product profiles.
- Reconciled README, roadmap, current state, support matrix, distribution
  matrix, package-producer guidance, checkpoint index, AIDE memory, and plan
  views to the same authority.
- Regenerated the native version header and WinForms command catalog after the
  project-state/schema revision changed.

## Maintainability and regression controls

- Extracted active-release selection and rendering into
  `tools/project_state_release_view.py`, reducing the central project-state
  module while retaining one canonical reader.
- Repaired the distribution-lane schema to validate the actual catalog-root
  document and strengthened all affected release schemas.
- Updated Alpha.5, source-closure, release-identity, AIDE, plan-view, and
  generated-state guards for the explicit successor phase and WorkUnit.
- After the predecessor entered `dev`, forward-restacked this WorkUnit onto the
  canonical merge and bound its base revision to that exact integration commit.
- Added the configured content-foundation native smoke to the fast and
  `runtime/factorio/` impact sets, with a regression test that proves relevant
  source changes select it.

## WorkUnit evidence

- Added this changed-file inventory, validation receipt, remaining-risk
  disclosure, policy-checked commit message, and durable checkpoint.
