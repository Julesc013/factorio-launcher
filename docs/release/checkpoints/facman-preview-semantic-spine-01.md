# FacMan preview semantic-spine checkpoint

Status: bounded Phase C characterization complete locally; stacked draft PR and
hosted CI are required before synchronization is complete.

## Exact base and branch

- branch: `task/facman-preview-semantic-spine-01`
- exact base: `909e9c62f447f72707cffb9ca9dbcb1b1bf5e274`
- base branch: `task/facman-technical-preview-census-01`

## Decision

The production path was not migrated. A complete atomic change would have to
move WinForms, AppKit, GTK, backend presentation/action dispatch, canonical
Last Run persistence, legacy cache handling, and revision/idempotency
enforcement together. Doing only part would violate the explicit stop law.

This branch instead characterizes all three frontend-local Last Run view
copies, reuses the existing `facman.presentation.v0` view vocabulary, and adds
one non-authorizing engineering fixture for the full preview walking skeleton.
The fixture covers workspace, discovery, read-only registration, instance
creation/selection, readiness, Launch Deck, fake session, operation, Last Run,
fake relaunch, and recovery inspection.

Every fixture action binds an expected presentation revision and request ID.
Effectful actions also bind an idempotency key and durable operation ID. Every
step records `production_command_dispatched=false`; `run.execute` and Setup
commands are forbidden by the checker.

## Validation

- `python tools/preview_semantic_spine_check.py`: pass, 11 fixture steps;
- `python -m unittest tests.test_preview_semantic_spine -v`: 5/5 pass;
- presentation/live-shell/semantic-spine focused suite: 14/14 pass;
- `python tools/schema_validate.py`: 338 schemas pass;
- `python tools/strict_check.py`: pass;
- project-state and generated version/catalog views regenerated and current.

## No-effect statement

No production frontend logic, backend command handler, workspace persistence
implementation, route availability, or provider source changed. This branch
did not run Factorio, mutate Setup or a live installation, read private
archives, edit ULK or USK, change IR4, write `main` or `dev`, create/move a tag,
sign, publish, create a release, or promote support.

## Next atomic WorkUnit

`FACMAN-PREVIEW-SEMANTIC-SPINE-MIGRATION-01` must implement one backend
presentation/action service and one canonical Last Run store, enforce expected
revision/idempotency/operation identities, migrate or invalidate all three
legacy caches atomically, and switch every preview-path frontend only after
semantic parity passes. Until then, the production path remains unchanged.
