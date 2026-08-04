# Universal Provider Contract Wave Reconciliation 01

Status: complete; provider contracts design-ready; implementation not started

Date: 2026-08-04

WorkUnit: `UNIVERSAL-PROVIDER-CONTRACT-WAVE-RECONCILIATION-01`

## Exact inputs

- FacMan task base: `0da078ff89e9d5e85bb8a98c1b7d4f546c4757bd`
- ULK synchronized `main`/`dev`: `db58cdffefe470cbd01a79558d177db3dda8aa32`
- USK synchronized `main`/`dev`: `095a6cf4e5d9635201c29c466dcb71ce359f9374`
- C3 immutable audit base: `ea984df9b7ab99cf47fcdbd8edcb571e6ce80d52`
- C3 bounded delta head: `f27c1d0c6798ea68b81ac0b0889ef770ad19d2d9`
- Dominium immutable audit head: `623ab08ae8c867719d5abc2e60c16a6fbb37b313`

FacMan's qualified provider pins remain
`7fc25340623131ba86c08dca4fb8a43b18a4520d` for ULK and
`3048128963dc718a7c38c1cfcdda9e813a23b0db` for USK.

## Reconciliation result

- The eleven-commit C3 delta leaves package lanes, deterministic package
  closure, preservation boundaries, activation/session behavior, and absence
  of setup mutation/self-replacement intact.
- C3 row `C3-20` is authoritatively `split/adapt`: acquisition remains
  consumer-owned; USK begins at local-package verification and lifecycle
  mutation. The C3 README toolchain contradiction is recorded as a consumer
  documentation defect, not a support claim.
- Thirteen Dominium lifecycle-specific corrections prevent content stores,
  reachability/GC, verification, pack semantics, and runnable-reference binding
  from moving wholesale to USK.
- ULK and USK contract WorkUnits are `design_ready` from the synchronized
  provider `dev` heads above. `SYNTHETIC-PRODUCT-TCK-01` is
  `blocked_on_provider_contracts`.
- The TCK is assigned to ULK-local fixtures, USK-local fixtures, and the
  existing FacMan superbuild tests. No fourth repository is created.
- Contract maturity is per contract from `fixture-qualified` through `stable`.
- Reconciliation closes at WIP `0/3`; the next admission set is workspace-root
  authority plus the two provider contracts.

## Validation

- Focused reconciliation suite: 50 tests passed.
- `python tools/strict_check.py`: passed.
- `python -m unittest discover -s tests`: 717 tests passed, 3 expected skips.
- `python .aide/scripts/aide_lite.py test`: passed.
- `python tools/generate_plan_views.py --check`: passed.
- `git diff --check`: passed.

## Authority boundary

No provider code or product code moved. No FacMan repin, live setup mutation,
product execution, signing, publication, credential, protected merge, or
successor route is authorized by this checkpoint.
