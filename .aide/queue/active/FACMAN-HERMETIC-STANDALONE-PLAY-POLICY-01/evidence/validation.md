# Hermetic standalone Play policy validation evidence

The WorkUnit was activated only after Gate 3 merged to reviewed `dev` and its
exact workflows and clean pinned three-repository reconstruction passed.

Activation validation establishes only:

- the policy-only objective and allowed paths;
- no permit issuance or process authority;
- `menu` as the sole intended candidate launch intent;
- separate candidate-implementation and human-verdict WorkUnits;
- retained `Pass`, `Fail`, and `Inconclusive` verdict outcomes.

No candidate policy, runtime implementation, real-product run, or authority is
claimed by activation evidence.

The no-authority Gates 0-3 baseline was subsequently promoted through PR #44
to canonical `main` `810e92ccd52ad89fada8a9bb5699805cb5580c24` and its ancestry
was synchronized through PR #45 to `dev`
`08d4318ffd32bd9553ce8914cbd8bfc98fde7b74`. Exact promotion-head,
canonical-main, synchronization-head, and final-dev workflows passed. This is
a prerequisite baseline only; it does not freeze this WorkUnit's policy or
authorize its candidate.

The evidence-only public-integration record passes local project-state and
strict validation, AIDE Lite, full native CTest (47/47), and the full Python
suite (364 passed, 2 skipped). Its canonical local build root was removed after
validation.

## Policy implementation validation

The implemented policy freezes:

- `factorio.hermetic_process_tree.v1`, explicitly excluding whole-host
  immutability;
- Windows x64, Factorio 2.0.77, authenticated non-Steam standalone source,
  fixed local NTFS, a FacMan-owned instance, an empty mod lock, and `menu`;
- 13 writable resources and 18 protected, forbidden-observed, or disclosed
  resource domains;
- 31 required evidence bindings and two independent observation scopes;
- 29 automated, human, and synthetic-deferred interruption/journey cases; and
- human-reviewed `Pass`, `Fail`, and `Inconclusive` law that cannot itself
  grant authority.

Focused validation passes:

- `py -3 tools/hermetic_play_policy_check.py`;
- eight policy mutation and negative-control tests;
- JSON Schema 2020-12 metaschema validation for 274 repository schemas;
- project-state generation and validation; and
- source-format and diff hygiene after the ledger correction.

Repository-wide local validation also passes:

- a fresh Windows MSVC Debug configure and warnings-as-errors build with the
  CLI and TUI enabled;
- native CTest, 47/47 passed;
- the full Python suite, 372 passed and 2 expected skips, against the fresh
  `facman.exe` and `facman-tui.exe` binaries;
- `py -3 .aide/scripts/aide_lite.py test`;
- `py -3 tools/strict_check.py`; and
- `git diff --check`.

The initial combined configure/build command and the first verbose full-Python
wrapper each reached their 120-second command window. The build completed when
resumed, and the first Python run had already printed `OK (skipped=2)` for all
372 tests before the wrapper exited. A second full Python run with a wider
window returned exit code zero in 120.8 seconds. These were command-duration
limits, not product or test failures.

The remaining closeout evidence is exact-head hosted review, clean pinned
three-repository reproduction, exact merged-`dev` proof, and policy-only
canonical promotion. No permit was issued, no launch route was added, and no
Factorio process was executed by this validation.
