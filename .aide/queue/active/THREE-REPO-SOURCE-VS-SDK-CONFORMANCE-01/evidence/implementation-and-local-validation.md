# Bounded provider-input implementation and local validation

Date: 2026-08-05

WorkUnit: `THREE-REPO-SOURCE-VS-SDK-CONFORMANCE-01`

Classification: `partial`

## Exact FacMan state

- Base: `dev@22a70c0280cc410083d5d9b093f0b05245d691e1`.
- Implementation commit: `e0f8d3c31ca550e7b9b04a51e8dcea42d1884d5a`.
- Implementation tree: `b5d700f230a4cbe9f14de06a1341c2fbb3f3e2fc`.
- Candidate branch: `task/facman-provider-convergence-01`.
- Candidate relation to `origin/dev`: four commits ahead, zero behind before evidence commit.
- `origin/main`: `b70be10696855628c6d2948eb016c8424912e14e`.
- Existing source-closure head: `bcc0233ccda9b7d29467d4ba5da613a2e016a36f`, six commits ahead of `origin/dev` and zero behind.
- Immutable evidence head: `9a6d6783c6f99876d8be8770ae5908d0566ba11b`; it remains separate and unmerged.

The workspace lock, release-provider lock, and successor route-v1 record have no
diff from `origin/dev`. This change performs no provider adoption, repin, or route
revision.

## Inherited Windows CI remediation

The candidate ports only the directory-package containment repair from source-
closure commit `a8dbd1e272d463da1e49b4c74641fe51aab0064c`. It replaces a
junction-sensitive resolved/unresolved Windows path comparison with lexical
containment followed by explicit parent-directory reparse validation. This is an
inherited CI repair and grants no source-closure or product authority. PR #123
must later merge the updated `dev` before integration so this repair lands once
and is not replayed independently from its older base. The focused release-
staging and release-compiler suite passes 30 tests with one unsupported-platform
symlink skip; Ruff, Python compilation, diff hygiene, and changed-file scope
validation also pass.

## Exact-head hosted CI remediation

Draft PR #124 run `31018810395` tested merge ref
`25814b7bf3007fce090dfd7179e2238fedd1c3ce`, whose candidate parent was
`f2cfd94188626f441e93a0829d216509aa1eebbb`. Linux completed the native,
Release, GTK, clang-tidy, sanitizer, archive-corpus, and bounded libFuzzer
phases. Its promotion-profile Python suite then executed 820 tests with zero
failures and zero errors, but correctly failed the gate because package custody
observed a dirty tree after CMake had recorded `source_dirty=false`.

The cause was workflow-owned rather than a package-validator defect. Each
libFuzzer command supplied a tracked fixture directory as its first corpus.
libFuzzer treats that first corpus as writable and may add coverage-increasing
inputs, so an otherwise successful fuzz pass could create untracked source-tree
files. The workflow now creates three ignored, build-owned writable corpora and
passes the tracked fixture directories only as read-only seed inputs. A
repository test binds all three command shapes to that custody rule. The
fail-closed CMake/package source-identity comparison is unchanged. Run
`31018810395` remains useful predecessor evidence but is superseded for final
exact-head acceptance by the workflow run triggered from this repair.

The same predecessor run also confirmed that the complete Windows Python and
required-package suites passed before reproducibility proof stopped, and that
the complete macOS native and Python promotion suites passed before package
proof stopped. Both commands lacked the mandatory `--source-observation`
argument already required on canonical `dev`. The exact observe-project-consume
repair from source-closure commit
`353eb2decc310f7e74ebfa5aaeb9284782929c0d` is therefore ported into this
candidate: all three native lanes record and preserve the checkout/provider
observation, project it into `facman.source_observation.v1`, and pass it to each
release-oriented producer. CI policy checks enforce that ordering. This closes
an inherited integration gap only; provider-lock mismatch and every product
authority remain fail-closed. PR #123 must later merge accepted `dev` so the
equivalent downstream changes have one effective landing.

## Exact provider observations

| Repository | Canonical `main` | Canonical `dev` | Canonical tree | Current consumed pin |
| --- | --- | --- | --- | --- |
| Universal Launcher | `1cafe4054297cc11e02458b83d230db0cd064471` | `7d4fd8e25a8d529279c4ad18d983e9cd51839eb7` | `47018102de4b9fd20af9f77acd4e1e35e51590f3` | `7fc25340623131ba86c08dca4fb8a43b18a4520d` |
| Universal Setup | `32488fc13bd2439f9f6e52e83a97f6da345a7650` | `6dc48673d54fb27ac4e8949da6f43275d36c9622` | `12fe757b1fc2ae78768a8cf912d03835f46ca65b` | `3048128963dc718a7c38c1cfcdda9e813a23b0db` |

For each provider, canonical `main` and `dev` have different commits but the
same tree. Both canonical branches were observed synchronized with their origin.
The retained consumed checkouts are clean detached worktrees at the exact
workspace-lock pins. Authored release-provider identities remain ULK
`719a3ec240831547071d69098e1fe8c76f327fb7` and USK
`7f8f2baa14e78b0329db8eef8ac872818c4cf30d`; their mismatch with active
workspace pins remains visible and fail-closed at release/source-closure gates.

## Implemented boundary

- Provider mode is a closed enum: `source`, `installed_static`, or
  `installed_shared`.
- Source mode requires exact explicit provider roots and exact Git custody; no
  sibling-directory heuristic fallback remains.
- Installed modes require exact SDK roots, identity sidecars, complete inventory
  custody, and recursively root-bounded imported-target closure.
- Installed modes remain conformance-only rehearsals even if their source pins
  equal tracked pins; no adopted SDK package anchor exists yet.
- FacMan-owned wrapper targets isolate downstream consumers from provider target
  naming and linkage selection.
- Candidate locks are out-of-tree, bind exactly both provider identities, compute
  `candidate_differs_from_tracked` truthfully, and carry the exact ten false
  authority fields.
- The harness binds canonical provider source commits/trees/remotes, exact SDK
  inventories, relocation, a sixteen-field toolchain record, declared shared
  runtime closure, and negative controls.
- Semantic normalization is schema-scoped. It validates exact provider
  mode/classification pairs, normalizes only declared differences, and rejects
  unknown absolute paths or forged normalization tokens.
- CMake emits the exact ten-field compiled build identity. Package construction
  accepts only tracked, non-conformance source state, binds that exact value into
  `facman.package_build_info.v1`, and WinForms compares it to the live backend
  handshake. Release-coherence remains a dynamic compiled Boolean.
- Hosted workflow language and result fields describe bounded provider-input
  conformance. They do not claim full semantic or canonical product proof.

## Local validation

| Gate | Result |
| --- | --- |
| Provider, mode, and packaged-backend focused suite | PASS, 58 tests and 1 unsupported Windows symlink-privilege skip |
| CI source-custody workflow regression suite | PASS, 12 tests |
| Plan-view suite after stale-assertion repair | PASS, 20 tests |
| Profile/template recovery outside the constrained temporary-root override | PASS, 2 tests |
| Strict repository validator | PASS, including 326 schemas, 684 SPDX-scoped files, 125 commands, 242 refusal codes, package/provenance/release-resolution gates |
| AIDE Lite portable validation | PASS |
| Generated plan views and project-state validation | PASS |
| Source-format, Ruff, Python compilation, and CMake script parse | PASS |
| Immutable workspace-lock, release-provider-lock, and route-v1 diff | PASS, unchanged |
| Independent blocker-only code audit | PASS, no release-blocking finding in the reviewed diff |

The terminal promotion-profile Python run executed 797 tests and returned seven
failures, two errors, and six classified skips. It was not converted into a pass:

- one stale plan-view phrase was a real repository test defect; it was repaired,
  and the complete 20-test plan-view suite then passed;
- five candidate-lock fixture cases used the sandbox-forced temporary directory
  beneath the source tree and were correctly refused by the new out-of-tree
  custody law; the same 54-test surface passes with a genuine out-of-tree temp;
- one profile-template mutation was denied by the managed filesystem; the exact
  two-test suite passes outside that constrained temporary-root override;
- four package obligations could not consume the pre-change native build because
  it correctly lacks `facman-build-identity.v1.txt`; two were classified
  `required_blocked` and two setup classes errored on the same missing generated
  input;
- three symlink cases were classified unsupported and one full-scale performance
  case remained optional.

The native build was not reconfigured merely to manufacture the new identity.
The managed host has already demonstrated that its toolchain cannot launch the
required `cmd.exe` child. The preserved native-attempt observation has SHA-256
`aea6710af04c25e8d86fd0ee7dc5148de6358fcd5d68dc0ca788f564210fa24c`; its log
has SHA-256 `42ebf5cce3e2e91dd680995311b4a7e31ff97701f2c5fa97e49eeb3b43ad240d`.

## Remote governance observation

Rulesets were observed active for `main` and `dev` in all three repositories,
requiring pull requests, current exact-head status, and conversation resolution,
while blocking deletion and non-fast-forward updates. No protected ref is mutated
by this WorkUnit. The FacMan candidate must be published to a task branch and
reviewed against `dev`; hosted exact-head evidence remains mandatory.

## Explicitly pending

The following semantic equality classes remain `pending_not_fabricated`:

- operation outcomes;
- structured refusal behavior;
- interrupted-recovery projections;
- FacMan release-resolution-root equality.

Hosted Linux and Windows must still prove native source, installed static,
installed shared, relocated SDK, private-runtime, WinForms, and negative-control
behavior from the exact candidate head. `facman.package_build_info.v1` remains an
unpublished producer/consumer record; freeze or version-bump it before any
external support commitment.

## Authority ceiling

This evidence grants none of: credentials, Factorio execution, observer capture,
permit issuance, product execution, provider adoption, publication, route
promotion, Setup mutation, or signing. The WorkUnit remains active and its result
remains `PENDING`/`partial` until hosted evidence and the richer semantic matrix
are accepted.
