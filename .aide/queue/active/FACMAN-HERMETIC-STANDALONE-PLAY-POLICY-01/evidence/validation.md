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

## Exact reviewed-head proof

PR #47 reviewed implementation head
`cf674d852e16ceb237ab83dc9254b37b0d900aa2` passed both push and
pull-request event proofs:

| Proof | Push run | Pull-request run | Result |
| --- | --- | --- | --- |
| CI | `29846149703` | `29846178980` | Pass |
| Code security | `29846150053` | `29846179861` | Pass |
| Schema check | `29846150047` | `29846179477` | Pass |
| Security policy | `29846149398` | `29846179286` | Pass |

PR #47 merged with exact-head matching into `dev` revision
`51f4fc24c9164762a88b92b4f865b04fe9256d4b`. Its exact merged-state
proof passed:

| Proof | Run | Result |
| --- | --- | --- |
| CI | `29847230819` | Pass |
| Code security | `29847230890` | Pass |
| Schema check | `29847230200` | Pass |
| Security policy | `29847230265` | Pass |

## Clean pinned reconstruction

One unique OS-temporary root used fresh detached clones and these exact pins:

- FacMan `51f4fc24c9164762a88b92b4f865b04fe9256d4b`;
- Universal Launcher `7bd4425f0c35414f738159b45d8bec42edf70235`;
- Universal Setup `3f8489275077347c2918f3bb03614ec6431362ff`.

All three repositories configured, built, tested, and passed strict checks.
FacMan additionally passed AIDE Lite and its full Python suite. The serial
single-writer matrix completed in 404.8 seconds; all three source checkouts
remained clean and exact at their pins. The complete temporary clone and build
root was removed in the same command's guaranteed cleanup path.

Gate 4A is therefore ready for a truth-only closeout and later policy-only
canonical promotion. No permit was issued, no launch route was added, and no
FacMan or Factorio product process was executed by this validation.

The truth-only closeout transition passes project-state validation, strict
validation, AIDE Lite, diff checks, and 25 focused policy/queue/truth tests. A
raw full-suite invocation after the validated build tree had deliberately been
deleted reached its expected Windows package-proof precondition because
`build/native-smoke/Debug/facman.exe` was absent; it was not recorded as a
product failure or as a passing full-suite run. The exact merged revision's
clean reconstruction above is the complete local build-backed suite, and the
closeout PR must supply a fresh hosted full-matrix proof.
