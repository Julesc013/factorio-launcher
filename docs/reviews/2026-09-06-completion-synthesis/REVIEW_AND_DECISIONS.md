# Review findings and proposed decision deltas

## Evidence boundary

All eight supplied files were inspected, including the eleven ZIP members. The three duplicate loose/archived Markdown documents were matched byte-for-byte. The report HTML's visible content and the JSON's text were
compared with their Markdown projections; distinct content was inspected separately. Both pasted reviews and both master/TODO revisions were read.

The ZIP's `SOURCE_REGISTER.json` describes ten earlier originals, but expressly says they were not copied into the package. Its prior assertion that they were read is a historical assertion by that report's author. This
assessment did not independently read those unavailable originals or inherit that author's GitHub checks. The earlier plan also names companion files not supplied here.

Selected local repository files and Git objects were inspected. No remote fetch, GitHub authentication check, provider checkout audit, product build, Factorio execution or human acceptance was performed. No external
technical citation is newly verified here. This review relies on supplied material and local primary source; platform-specific implementation details should be checked against the admitted toolkit/version when
implemented.

## What the local evidence changes

| Finding | Observation | Consequence |
|---|---|---|
| Reported FacMan dev matches local source | HEAD/dev `8fee0d0d…`, tree `9bccadbf…`; local history includes #246–#248 | Preserve integrated work; no repeat implementation based on an old TODO |
| Corrected train already exists | `plan.v1.toml` delivery_train and `docs/product/master_plan.md` contain 0.1–0.4 direction | Reconcile statuses and missing profile detail; do not request the same scope decision anew |
| Closeout metadata trails integration | delivery_train says pending integration; workspace and corrected-train WorkUnits remain active | Check acceptance receipts and close only established contributions; whole journeys may remain open |
| Generated views are internally current | `tools/generate_plan_views.py --check` passes | The issue is source-record semantics, not failed generation; do not “fix” generated files directly |
| Alpha.5 remains selected | Selector: Alpha.5, three profiles/eight assets; release authorities false | Preserve history; qualify future Terminal/Desktop producers and selectors together |
| Setup crosses an effect boundary | `apps/setup/main.cpp:584`: setup precedes native integration, whose helpers receipt and compensate | Reproduce interruption/ownership recovery; native effects have receipts |
| Prior NO_COLOR work is present | Merge #247 exists; terminal/PTY/ConPTY tests contain colourless-mode cases | Preserve and rerun affected regression tests when changing terminal behavior; no renewed original bug claim |
| Provider state remains unverified here | Supplied reports describe ULK #18 and USK #27/#28; sibling provider repositories were not audited | Reobserve exact current provider state before integration or version recommendations |

The local source starts clean. Only this dated planning package is added by the current task. Production code, active policy, provider locks, canonical TODO, branches, tags and releases are unchanged.

## Improvements over both supplied backlogs

The older backlog has 20 broad bundles; the newer has 36. A valid acyclic graph is useful but cannot establish that its dependency edges are necessary or that a bundle fits one reviewable change.

| Prior scheduling issue | Improved treatment |
|---|---|
| Newer P10 makes USK qualification depend on ULK truth/documentation P04 | Qualify the changed USK subset with actual consumed ULK compatibility; independent documentation is not a runtime prerequisite |
| P03 provisions all three OS hosts before P12/P23 can finish or appear ready | Provision the specific scenario host first; other required hosts block their own qualification cells |
| P19 worlds waits on all P18 content | Start consistent save backup/restore independently; content-linked reconstruction closes only when content is ready |
| P15/P16 “complete CLI/TUI” precede incomplete domain work | Split compatibility/mechanics from full outcome closure; evolve ordinary workflow adapters with each domain |
| P24/P25 full desktop bundles look like late start gates | Start production controls and typed adapters early; full desktop completion depends on the integrated outcomes |
| Existing-install Play is technically independent but canonical Alpha work is serial | Prepare a small reviewed split/reorder of existing WorkUnits; don't execute out of order solely from this advisory graph |
| Native effects described too broadly as untracked | Preserve existing receipts/compensation; close crash recovery and ownership across phases with a focused reproduction |
| Planning/package validation repeated as evidence of plan quality | Check semantic edge necessity, source mapping and coverage as well as graph syntax; make no product qualification claim |

## Decision register

“Retain” means supported by the inspected integrated design. “Reconcile” means fix stale/misaligned records without altering historical qualification. “Propose” requires an actual reviewed adoption if it changes
canonical behavior or policy.

| ID | Disposition | Recommendation | Incorporation target |
|---|---|---|---|
| D01 | Retain | Complete local terminal plus WinForms/GTK in 0.1; acquisition 0.2, hosting 0.3, AppKit 0.4 | Existing delivery_train and product master plan |
| D02 | Reconcile | Close integrated #246/#248 contributions only when acceptance evidence supports it; preserve open package/journey obligations | `plan.v1.toml`, `project_status.v2.toml`, `current_state.v1.toml`, generated views |
| D03 | Retain | One `facman` terminal host and separate native GUI; both TUI modes | Command law, entrypoint/package tests, existing CLI/TUI instructions |
| D04 | Retain | Preserve actual grammar, aliases, RPC framing, exits and wait behavior | Characterization tests and generated help; no imported example schema or blanket rename |
| D05 | Retain | Existing ownership and typed presentation seam; no speculative universal workbench prerequisite | Component ownership and relevant implementation modules |
| D06 | Propose | Distinguish start/closure dependencies; start both exemplars and native fixtures early | Reviewed split/reorder of existing Alpha.6/Alpha.7 WorkUnits |
| D07 | Reconcile | Admit exact target/source-format/applicability cells; avoid broad “all Linux” or historic-OS claims | Scope/readiness, profile catalog, support matrix and journey corpus |
| D08 | Retain/reconcile | Terminal/Desktop component model; portable and installed-use paths; count generated from profiles | Package producers, manifests, active selector and qualification, in one coherent transition |
| D09 | Retain | Current formats and renderer unless measured evidence justifies replacement | Existing package and terminal implementation contracts |
| D10 | Propose focused implementation | Recover native installation effects across payload/integration phase interruption; preserve prior owned state | Setup/USK effect owner plus fault/lifecycle tests |
| D11 | Retain | Independent bootstrap/maintenance and terminal recovery over one lifecycle engine | Setup package contract and J11 |
| D12 | Retain/refine | Entry-based restart, generation leases, domain-specific rollback and independent outcome oracles | Provider lifecycle and J03/J07/J09/J10 tests |
| D13 | Propose operational amendment if needed | Deliberate bounded checkpoint promotion; do not force paperwork-only promotions or silently ignore max-one unpromoted rule | Current `branch_policy.v1.toml` and operator integration policy |
| D14 | Reconcile authority only when needed | Use existing user/session authorization; prepare exact next action before requesting a missing decision | Existing policy/WorkUnit records; this proposal grants nothing |
| D15 | Retain | Current human/publication gates; no default new autonomous evaluation-release policy | `version_train.v1.toml`, active selector, applicable release-specific policy |
| D16 | Propose before later minor promotion | Permit supported maintenance from the protected 0.1 line where main-only tagging conflicts | Branch/version policy and maintenance procedures |
| D17 | Retain/refine | Stable candidate identity before build; accept final bytes; scoped evidence reuse and durable artifact retrieval | Existing composition/qualification/release records |
| D18 | Retain | System Native baseline; bounded OEM+; platform-specific controls and real input/accessibility proof | Existing design system, production galleries and native tests |
| D19 | Propose calibration | Set measured performance budgets on named hosts; preserve existing scale evidence | Existing quality budgets and package scenarios |
| D20 | Retain | Freeze 0.1–0.4; leave later optional portfolio unallocated; real provider consumers before stability | Existing roadmap/later registry and provider stability programme |

The current branch policy has `maximum_completed_unpromoted_work_units = 1` and `protected_dev_merge_active = false`. Those are observed file contents, not proof of current hosted settings or a substitute for
session-specific authorization. This request authorizes assessment and deliverables, not execution of the supplied merge/release prompts.

## Import strategy

1. Incorporate D02 and required outcome/profile details in existing source records, using actual receipts. Do not simply mark all formerly active work complete.
2. Review a bounded WorkUnit split that permits the independent Play exemplar, native fixtures and provider work. Keep canonical scheduling authoritative.
3. Apply compatibility corrections where current generation instructions actually exist. The two original CLI/TUI generation briefs are not supplied here; the ZIP contains amendments to them, not their full originals.
4. Implement narrowly scoped product tasks with their own evidence. Qualify Terminal/Desktop producer changes before selecting them as release obligations.
5. Regenerate existing views. Keep this package as a dated assessment, and stop using it as a second active backlog once its decisions are assimilated.

No new permanent architecture constitution, broad schema migration, repository rename or automatic policy expansion is recommended.
