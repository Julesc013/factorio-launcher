# Completion and acceptance contract

This document proposes concrete acceptance deltas for the existing [readiness records](../../../release/index/foundation_beta_readiness.v1.toml). It creates no new product schema or completed evidence record.

## 1. One finite matrix

The unit of proof is:

`named outcome × admitted target profile × applicable interface × package selection/form × scenario`

Use the existing full journey IDs, including `J11_product_setup_maintenance` and `J12_diagnostics_support`. A bare J-number is only a display abbreviation. Do not renumber old C1 journey evidence, which can use similar
labels for a different scope.

Enumerate required ordinary outcomes first, then applicability. Avoid both a universal Cartesian explosion and selective happy-path coverage. Every required outcome needs a positive path and the meaningful
refusal/fault/recovery cases for its effects. Use covering combinations for ordinary presentation variation and explicit combinations for known high-risk interactions.

| Dimension | Required treatment |
|---|---|
| Target | Exact OS/build, architecture, runtime, filesystem, toolchain and terminal/native backend where relevant |
| Interface | Human CLI, CLI JSON, process RPC, fullscreen TUI, linear TUI; WinForms/GTK references; scoped AppKit preview |
| Distribution | Selected Terminal/Desktop components; portable/installed-use forms; current historical selector kept separate |
| Input | Exact local source format/game version/content/world fixture; custody and allowed effects when real material is used |
| Evidence | Source/tree, provider/resources, package digest, driver/oracle version, host, result and retained artifacts |
| Status | Implementation, integration, machine/package proof, experience, authority and support remain separate |

An unavailable required host is blocked. A supported negative test passes only by observing the specified refusal and absence of prohibited effects. A fixture can establish semantics; it cannot substitute for a required
real-game route. N/A needs an approved applicability reason, not an empty result.

## 2. Required risk scenarios

| Scenario | Independent observation / success condition | Primary owner |
|---|---|---|
| Workspace migration interrupted around visibility/receipt writes | Restart inspects actual version/files; safe resume or bounded rollback; foreign state unchanged | FacMan workspace |
| Installation changes after readiness or plan | Revalidation refuses stale input; no launch or write occurs from stale authority | FacMan + relevant provider |
| Setup source/staging substituted | Source/target/plan ownership mismatch is detected; no guessed overwrite or destructive cleanup | USK |
| Entry extraction interrupted | Verified entries reused only under matching identity; partial entry restarted/discarded by declared law | USK |
| Disk full / journal failure / cancellation near activation | Truthful visible generation and operation state; retained recovery route; no false success | USK |
| Active game leases a generation during update or cleanup | Running process keeps required files; cleanup refuses or retains referenced generations | ULK + USK coordination |
| Payload completes, shortcut/registry phase is interrupted | Restart discovers both phases and pre-existing state; deterministic completion or compensation | Setup effect owner |
| Modpack reconstruction from a clean offline root | Exact lock/settings reconstructed; missing material explained; no hidden network use | FacMan content |
| Save changes while backup is being taken | Consistent backup produced under a stated strategy, or explicitly refused/inconclusive | FacMan worlds |
| Selected save mismatches game/content or was converted | Correct compatibility result; preserved original; no false promise from installation rollback | FacMan worlds/readiness |
| Spawn acknowledgment lost, frontend dies, PID reused | No blind duplicate launch; durable operation inspection and stable process identity | ULK/session + FacMan |
| Old/new clients and concurrent workspace writers | Negotiated compatibility or clear refusal; no lost update or silent future-state rewrite | Application/transport owners |
| Wrong or corrupt runtime resources / missing GUI runtime | Activation refuses incompatibility; independent diagnostics/maintenance remains available | Composition/maintenance |
| Hostile filenames, mod metadata and logs | Rendering cannot inject terminal controls; bounded redacted support export preserves intended identity | Terminal/support |
| Small window + enlarged/expanded text; active operation + DPI/theme change | Real controls remain usable; focus, warnings, cancellation and recovery are reachable | Native adapters |

A test oracle must not merely ask the production function whether its own action succeeded. Inspect filesystem, process or journal outcomes through independent observations, and include negative controls for the oracle itself.

Distinguish restart recovery, same-volume visibility, multi-file recovery, OS restart and actual power-loss guarantees. Record limitations instead of using “transactional” as an undifferentiated claim.

## 3. Interface quality

Human CLI must finish ordinary tasks without handwritten JSON. JSON/RPC must remain prompt-free and preserve framing, exits and documented accepted-versus-terminal behavior. TUI modes must complete the same outcomes
without routing users through Advanced or switching to another frontend.

Required terminal stress includes independent stream redirection, EOF, broken pipes, slow consumers, empty arguments, leading-dash operands, Unicode/native paths, bounded paste/events, control injection, resize and focus
restoration. Colour suppression is tested independently of renderer selection. Handled cleanup is tested; power loss and uncatchable termination are not represented as cleanup guarantees.

Native evidence has separate semantic, input, accessibility and visual parts. Accessibility Invoke does not prove a key binding or hit target. A screenshot does not prove a mutation. Use actual production widgets and
reducers; review changed goldens and test assertions deliberately. Test named X11/native Wayland profiles separately when admitted.

Keep System Native recovery reachable through malformed preferences, damaged resources and long/expanded labels. Customization cannot hide severity, change readiness, alter action meaning or remove recovery.

## 4. Resource and performance qualification

Keep the reported 1,000-mod/10,000-save/100-snapshot fixture as scoped historical evidence until its original receipt is inspected. Reuse it only when its inputs remain applicable.

Before numerical budgets become binding, record the metric, reference host, corpus, cold/warm definition, repetitions, percentile and variability. Measure time to usable interaction, input feedback, scoped queries, total
process memory, queue growth, setup throughput and post-start stalls. Bound metadata, journals, codec state, histories, caches and concurrency as well as payload buffers.

Immediate failures include unbounded growth, unsafe memory/size arithmetic, a stuck cancellation/recovery path or a frozen required interface. Proposed timing numbers in supplied prose remain calibration candidates, not
achieved performance or automatically ratified gates.

## 5. Evidence states and release gates

| Gate | Exit |
|---|---|
| Engineering slice | Bounded behavior and paired failure/recovery tested; ordinary interface and help updated; source reviewed/integrated as applicable |
| Application / terminal / reference desktop checkpoint | All required outcomes for that checkpoint proven with exact applicability; no implied promotion of other axes |
| Feature-complete engineering candidate | Required implementation and integration complete; engineering package campaigns cover the scope; release blockers absent |
| Final candidate machine acceptance | Intended version/source/providers/resources fixed; authorized trust steps completed; exact final delivery files tested and retained |
| Experience acceptance | Actual required human observations on those delivery identities; failures and inconclusive results retained |
| Public Beta / RC / normal release | Applicable publication/trust/support rules satisfied; complete accepted assets published and checked after download |

“No release blockers” includes unresolved data loss, ownership/authority bypass, known P0/P1 defects and incomplete advertised required outcomes. Lower-severity limitations must be visible and consistent with claims. An
unexplained intermittent failure on a required critical path remains unresolved; a green rerun alone does not close it.

A candidate is not created by renaming accepted Alpha files to Beta. Reserve the candidate's intended version, select source, construct reproducible unsigned payloads, apply approved signing/notarization/container steps,
then hash, qualify and accept final files. Follow actual platform packaging order; the invariant is acceptance of the final delivered identity.

RC and plain 0.1 have new version-bearing bytes where applicable. Repeat candidate binding and affected verification. Public tags and assets are immutable. Keep accepted bytes in durable custody outside disposable
task/build roots, with a retrieval check; a hash alone is not retained evidence.

## 6. Economical regression and experience work

During implementation, run targeted tests for the changed responsibility. Run all required checks at integration boundaries. Broaden campaigns when changed providers, persistence, packaging, transport, native adapters or
unresolved failures justify them.

For reuse, compare the actual source/provider/resource/toolchain/profile/corpus/oracle input closure. Preserve the old record and document applicability to the new candidate. Source equality alone does not prove delivery
equality, while an unrelated documentation change does not require every old archive experiment to be repeated.

Prepare small human sessions around comprehension, keyboard/screen-reader use, safe destructive decisions and recovery confidence. Use early feedback on prototypes for discovery and final required observations for
acceptance. Automated trees or model screenshot judgments cannot be relabelled human experience.
