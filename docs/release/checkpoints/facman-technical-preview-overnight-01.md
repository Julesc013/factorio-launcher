# FacMan Technical Preview overnight operator report

Date: 2026-08-12 (Australia/Sydney)

Status: all three bounded phases implemented, committed, pushed, and opened as
stacked draft pull requests. Phase A, Phase B, and the Phase C implementation
head are hosted-green. This report-only closeout is validated separately at its
final exact head and recorded in the draft pull request.

## Executive result

The programme now has one reviewable path from canonical remote `dev` to a
smaller Windows Technical Preview without claiming authority that was never
earned.

- Phase A preserves useful synthesized history but closes source/evidence and
  execution authority.
- Phase B replaces command-shaped parity planning with 37 factual user
  outcomes and a separate 125-command/API ledger.
- Phase C obeys the stop law: it characterizes the three frontend-local Last
  Run copies and proves an 11-step fake-process semantic skeleton without
  partially switching the production path.

No merge, tag, release, signing, real Factorio execution, live Setup mutation,
or protected-branch write occurred.

## Exact refs before and after

### Inputs

- canonical remote `origin/dev`:
  `4da0bf2c4c1df92d8e3a4d2d7eae39ebf65cba2f`;
- synthesized candidate head:
  `85648ff0bf0bef30b71bfb25a805c4082f144f9b`;
- local pre-existing `dev`: `85648ff0bf0bef30b71bfb25a805c4082f144f9b`;
  it was not treated as canonical and was not changed;
- Universal Launcher read-only canonical observation:
  `1cafe4054297cc11e02458b83d230db0cd064471`;
- Universal Setup read-only canonical observation:
  `32488fc13bd2439f9f6e52e83a97f6da345a7650`.

### Synchronized outputs

- Phase A: `task/facman-dev-reconciliation-01` at
  `51047053760557b52a9bf06cff1b79bf6614dafb`;
- Phase B: `task/facman-technical-preview-census-01` at
  `909e9c62f447f72707cffb9ca9dbcb1b1bf5e274`;
- Phase C: `task/facman-preview-semantic-spine-01` at
  `fb2e1bbf62cfa615f9c2b9a702e595ff8cfe919d` before this report-only commit;
- `origin/dev`, `main`, tags, and releases: unchanged.

## Commit parentage

```text
4da0bf2c4c1df92d8e3a4d2d7eae39ebf65cba2f  origin/dev base
└─ f92da63747324330a4e4a7718d3a0f9cbd7f2099  activate reconciliation
   └─ 30082279453a12a80539c238dec2d5454ce39944  two-parent reconciliation merge
      ├─ first parent:  f92da63747324330a4e4a7718d3a0f9cbd7f2099
      └─ second parent: 85648ff0bf0bef30b71bfb25a805c4082f144f9b
      └─ b20d73fe334138a7396e7bd33b77de3c9c001eda  Phase A checkpoint
         └─ 51047053760557b52a9bf06cff1b79bf6614dafb  POSIX fixture repair
            └─ 909e9c62f447f72707cffb9ca9dbcb1b1bf5e274  Phase B census
               └─ fb2e1bbf62cfa615f9c2b9a702e595ff8cfe919d  Phase C characterization
```

The synthesized parent remains visible in history. No rebase, force push, or
history rewrite was used.

## Draft pull requests

- Phase A: https://github.com/Julesc013/factorio-launcher/pull/133
  (`dev` <- `task/facman-dev-reconciliation-01`);
- Phase B: https://github.com/Julesc013/factorio-launcher/pull/134
  (`task/facman-dev-reconciliation-01` <-
  `task/facman-technical-preview-census-01`);
- Phase C: https://github.com/Julesc013/factorio-launcher/pull/135
  (`task/facman-technical-preview-census-01` <-
  `task/facman-preview-semantic-spine-01`).

All three remain open drafts. No pull request was merged or closed; PR #131
and PR #132 were not changed.

## Authority matrix before and after

| Authority / state | Synthesized input | Reconciled stack |
| --- | --- | --- |
| source closure | temporary gates open | `deferred_external` / `not_run` |
| current valid source evidence | unresolved temporary path | `[]` |
| admission implementation tests | mixed with evidence expectations | separate synthetic implementation suite |
| deferred-state tests | incomplete distinction | explicit canonical deferred suite |
| integrated-admission tests | conflated with evidence run | explicit synthetic integration fixture |
| actual evidence run | not performed | external and `not_run` |
| Factorio execution | unavailable but temporary route permissions existed | false/unavailable |
| Setup mutation | false | false |
| qualification | false | false |
| route capability / promotion | false | false |
| tag / sign / publish / support | false | false |
| product capability planning | 12 reserved command-shaped slices | 37 user outcomes: 28 required, 9 deferred |
| command/API planning | one-row-per-command requirement | separate generated 125-command many-to-many ledger |
| ordinary preview frontends | CLI human/JSON, TUI, WinForms mandatory peers | WinForms primary, CLI JSON normative, human CLI diagnostic/recovery, TUI non-blocking |
| managed installation | preview blocker | deferred |
| Factorio instances/profiles/modsets/saves/readiness | partially misassigned to providers | FacMan product authority |
| ULK preview role | broad instance/profile/launch ownership | opaque runnable plus generic operation/process/session/Last Run |
| USK preview role | managed lifecycle blocker | installed-state/setup mutation only; deferred |
| local modset effect | `setup_mutation` | `instance_content_mutation` |
| workspace persistence | JSON/TOML store with SQLite question open | JSON/TOML canonical; SQLite rebuildable derived index only |
| Last Run production authority | three frontend-local non-authoritative copies | characterized unchanged; atomic backend migration required |

## Technical Preview required scope

The frozen milestone is `FacMan 0.1.0 — Technical Preview`:

- Windows x64;
- WinForms primary ordinary-user frontend;
- CLI JSON normative automation/test contract;
- human CLI required for Doctor, diagnostics, status, support, and recovery;
- TUI retained and tested as a grammar-generated command explorer, not a
  parity blocker;
- existing standalone installation discovered and registered read-only;
- isolated instance, profile/configuration, local content, save inspection and
  backup, readiness, Launch Deck, launch-to-menu plan/route state, session,
  Last Run, relaunch, recovery, support, identity, package relocation,
  reproducibility, and WinForms accessibility obligations;
- unsigned internal candidate only.

The canonical 28 required IDs are in
`release/index/technical_preview_scope.v1.toml` and the detailed evidence
classification is in `release/index/capability_frontend_matrix.v1.toml`.

## Explicit deferred scope

- managed Factorio installation and live Setup mutation;
- selected-save launch route;
- accounts, credentials, acquisition, network, Mod Portal, Steam, and
  storefront mutation;
- self-update, system-wide installation, elevation, and native installers;
- server execution and administration;
- macOS/Linux ordinary-workflow support and other GUI projections;
- public provider APIs, daemon, remote administration, and plugins.

The real 4.6 GB ZIP64/Deflate Factorio 2.1.14 corpus remains outside the
current USK whole-payload/stored-only lifecycle. No streaming work was started.

## Persistence and semantic-spine result

The existing `runtime/workspace` file store remains the single canonical
workspace boundary. It retains typed, path-based, durable no-follow JSON/TOML
repositories and fail-closed migration apply. There is no demonstrated daemon,
multi-client query, or concurrency pressure that justifies SQLite authority.

Phase C found that WinForms, AppKit, and GTK each retain a workspace-bound Last
Run view copy while separately reconstructing presentation. Because a complete
atomic migration was not safe in this bounded phase, production was not
switched. Instead, the stack adds:

- an explicit characterization record;
- a closed fixture schema;
- an 11-step fake-process walking skeleton;
- expected presentation revisions and request IDs on every action;
- idempotency keys and durable operation IDs on effectful fixture actions;
- fail-closed rejection of real `run.execute`, Setup commands, or production
  dispatch.

This is engineering evidence only. It is not real Factorio evidence,
qualification, or release evidence.

## Validation commands and results

### Phase A local

- `python -m unittest discover -s tests`: PASS, 976 passed / 13 skipped at the
  reconciliation checkpoint;
- native Debug configure/build with pinned ULK/USK inputs: PASS;
- `ctest --test-dir build/native-smoke -C Debug --output-on-failure`: PASS,
  38/38;
- `python tools/strict_check.py`: PASS;
- `python tools/schema_validate.py`: PASS, 337 schemas;
- `python tools/package_check.py`: PASS, 26 manifests;
- `python -m unittest discover -s tests -p test_test_architecture.py -v`:
  PASS, 21/21 after the platform-suffix repair;
- AIDE `task inspect`, `task noop-check`, `task recover`, `git policy`,
  `git detect`, `git plan`, commit checks, and changelog preview: PASS/report-only.

Two additional local full-suite attempts were not accepted as positive Phase A
evidence because pre-existing/incomplete local static/shared package build roots
contaminated package identity and omitted required WinForms/TUI outputs. Clean
hosted CI supplied the authoritative package evidence.

### Phase B local

- `python tools/technical_preview_census.py --check`: PASS;
- `python tools/release_programme_check.py`: PASS;
- focused plan/census/programme suite: PASS, 45/45;
- `python tools/facman_release.py validate`: PASS, 11 existing compiler inputs;
- `python tools/strict_check.py`: PASS;
- AIDE commit check and changelog preview: PASS;
- full discovery: 969 tests run / 321 skipped; one stale generated plan view was
  regenerated and its focused test passed; the remaining local setup error was
  the intentionally absent clean-built Windows package binary. Hosted Windows
  CI built and verified it with zero required skips.

### Phase C local

- `python tools/preview_semantic_spine_check.py`: PASS, 11 steps;
- `python -m unittest tests.test_preview_semantic_spine -v`: PASS, 5/5;
- presentation/live-shell/semantic-spine focused suite: PASS, 14/14;
- `python tools/schema_validate.py`: PASS, 338 schemas;
- `python tools/project_state.py --write`: generated projections current;
- `python tools/codegen/generate_metadata.py --write`: generated metadata
  current;
- `python tools/strict_check.py`: PASS;
- AIDE commit check and changelog preview: PASS.

## Interpreter and toolchain identities

- local Python: CPython 3.11.9;
- hosted Python: CPython 3.11.9;
- CMake: 4.2.3;
- local Git: 2.53.0.windows.1;
- GitHub CLI: 2.96.0;
- Phase A Windows compiler: MSVC 19.51;
- hosted runners exercised Windows, Ubuntu, and macOS native/package lanes;
- no production signing, release, or private-archive toolchain was invoked.

## Hosted CI

### Phase A exact head `5104705`

- General CI run 31573458973: PASS, six jobs including Linux native, macOS
  native/archive/AppKit, Windows WinForms/package, and coverage;
- schema, security policy, code security, Python, C/C++, C#, CodeQL, and
  synthetic-product workflows: PASS;
- first run failure root cause: POSIX test fixture incorrectly created an `.exe`
  path; branch repair `5104705` fixed the fixture and the clean rerun passed.

### Phase B exact head `909e9c6`

- General CI run 31577099352 attempt 2: PASS, all six jobs;
- first AppKit attempt passed build/runtime/relocation/package proof but GitHub's
  artifact service timed out five times; bounded rerun uploaded successfully;
- independent push run 31577062808 also passed AppKit at the exact head;
- schema, security policy, code security, and synthetic-product workflows:
  PASS.

### Phase C exact head `fb2e1bb`

- push General CI run 31579451900: PASS, all six jobs including Linux native,
  sanitizers and bounded fuzzing; macOS native CLI, archive core and AppKit;
  Windows WinForms/package; and coverage;
- PR General CI run 31579490147: inspected as the parallel pull-request run;
- security policy and synthetic-product TCK: PASS;
- the report-only closeout commit is required to pass its own final exact-head
  hosted checks; its immutable run URL is recorded in PR #135 because a commit
  cannot truthfully contain the ID of a workflow triggered by that same commit.

## Files and systems not modified

Confirmed unchanged by this work:

- IR4;
- `D:\Games\Factorio\2.1`;
- private Factorio archives and credentials;
- Universal Launcher source/history;
- Universal Setup source/history;
- `main`;
- `origin/dev`;
- tags;
- releases;
- production credentials and signing state;
- live Factorio installations and saves;
- PR #131 and PR #132 state.

## Unresolved blockers

1. The exact route target is Factorio 2.0.77 while the retained real archive
   corpus is Factorio 2.1.14. A reviewed route/version decision is mandatory;
   silent substitution is forbidden.
2. `run.execute` has no qualified clean-host real route and remains unavailable.
3. Last Run and presentation policy need one atomic backend migration across all
   preview-path frontends; the current production view copies remain
   non-authoritative debt.
4. The v2 release target graph contains CLI targets but no reviewed combined
   WinForms target; the legacy WinForms profile is only package-preview truth.
5. Final WinForms experiential/accessibility receipt, exact candidate freeze,
   production signing, and D4 promotion remain future public-release gates.
6. USK cannot yet stream/materialize the retained 4.6 GB ZIP64/Deflate corpus;
   managed installation remains deferred and non-blocking.

## Next six dependency-ordered WorkUnits

1. `FACMAN-PREVIEW-STACK-INTEGRATION-01` — review the three draft PRs in order,
   preserve exact parentage, and land only through the normal reviewed path.
2. `FACMAN-PREVIEW-SEMANTIC-SPINE-MIGRATION-01` — atomically implement one
   backend presentation/action service and canonical Last Run store, including
   all three frontend adapters and legacy-cache migration/invalidation.
3. `FACMAN-WINDOWS-EXISTING-INSTALL-WALKING-SKELETON-01` — make the exact
   WinForms + CLI JSON existing-install route executable with fake process or
   structured unavailability and recovery, without real Factorio execution.
4. `FACMAN-ROUTE-VERSION-DECISION-01` — review and bind 2.0.77 versus 2.1.14,
   regenerate the exact route definition, and forbid implicit replacement.
5. `FACMAN-WINDOWS-MENU-ROUTE-QUALIFICATION-01` — on a separately authorized
   clean Windows host, qualify exactly one launch-to-menu route and record the
   required human/operator evidence.
6. `FACMAN-0.1-UNSIGNED-CANDIDATE-01` — add the reviewed v2 WinForms target,
   resolve/reproduce/relocate the exact unsigned package, close required
   outcome rows, and prepare (not perform) the later RC/receipt/signing gate.

None of these WorkUnits is authorized by this report. In particular, real
Factorio execution, live Setup mutation, protected-branch merges, signing,
tags, publication, and releases remain separately controlled.
