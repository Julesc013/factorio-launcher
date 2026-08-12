# Validation

Recorded: 13 August 2026 (AEST)

## Hosted exact-head closeout

All required push workflows for FacMan protected `dev` merge
`da7c825f0695b401d367d9bd3aab990690d8573e` completed successfully:

- CI: run 31615374693;
- bounded provider-input conformance: run 31615374761;
- provider SDK consumption: run 31615374699, Windows/macOS/Ubuntu success;
- schema check: run 31615374686;
- security policy: run 31615374527;
- code security: run 31615374554;
- synthetic product TCK: run 31615374716.

ULK merge-head run 31615374501 also completed successfully.

## Local exact-input matrix

Validation used the locked development packages from
`tools/requirements-dev.lock`, task-owned external build output, and disposable
detached provider clones at the exact consumed locks:

- ULK `1cafe4054297cc11e02458b83d230db0cd064471`, tree
  `47018102de4b9fd20af9f77acd4e1e35e51590f3`;
- USK `32488fc13bd2439f9f6e52e83a97f6da345a7650`, tree
  `12fe757b1fc2ae78768a8cf912d03835f46ca65b`.

Results:

- MSVC Debug source/static build: PASS;
- `ctest -C Debug`: PASS, 40/40 native tests;
- full Python discovery: PASS, 998 tests, 328 classified skips;
- `tools/strict_check.py`: PASS;
- `tools/generate_plan_views.py --check`: PASS;
- `tools/project_state.py --validate`: PASS;
- `py -3 .aide/scripts/aide_lite.py test`: PASS;
- `git diff --check`: PASS.

The first fully provisioned Python run found one repeatable CPython 3.14/Windows
cleanup race after a supervised fake-process timeout. The supervisor now gives
the kernel one bounded 50 ms interval to release the terminated process's
current-directory reference. Its focused regression and the subsequent full
998-test run pass. No Factorio process was used.

## Review and truth closeout

- PR #134 was closed as integrated through #136.
- PR #135 was closed as integrated through #136.
- PR #136 records why #131/#132 are ancestry-derived merged history and do not
  represent current temporary authority.
- Generated README, roadmap, todo, support matrix, checkpoint index, compact
  current state, and AIDE memory agree with the canonical truth compiler.
- ULK `dev@85df03b` is observed, while ULK `main` and the consumed FacMan pin
  remain `1cafe405` pending the separate promotion and adoption trains.

All execution, Setup mutation, provider adoption, signing, publication, tag,
release, and public support authorities remain false.
