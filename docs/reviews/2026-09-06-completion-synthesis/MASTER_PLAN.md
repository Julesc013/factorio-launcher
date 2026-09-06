# FacMan: the recommended completion plan

**Assessment date:** 6 September 2026, Australia/Sydney.
**Status:** advisory synthesis grounded in the supplied files and selected local source.
**Execution authority:** unchanged; `release/index/plan.v1.toml` remains canonical.

## 1. Judgment

The architecture is sufficiently coherent to finish the product. Keep its semantic ownership, the same-binary terminal design, and the corrected release allocation. Change implementation where evidence identifies a
defect or a costly boundary; an architecture freeze must not freeze defects.

The previous plans are not the best executable form yet. Their main weaknesses are repeated authority prose, stale integration statuses, large bundles described as immediately actionable, and completion dependencies
being mistaken for start dependencies. Their repeated agreement is also largely agreement among summaries of the same evidence.

The recommended improvement is a finite programme with two early packaged exemplars, incremental native consumers, explicit failure oracles, and a bounded next queue. This is the best-supported direction from the
available evidence. There is no measured basis for claiming a mathematically optimal schedule, a completion percentage, or a reliable Beta date.

The product promise is simple:

> Select an isolated Factorio environment, understand whether it is ready, prepare it when necessary, play, and recover or reconstruct it without losing user data.

## 2. What is already decided, and what is actually observed

The local checkout is `8fee0d0d2cde9d3dd2065d7624b0a45c820db800`, tree `9bccadbfdb4ced62754370f4d98e3880141d7bae`. Its history contains the merges of #246, #247 and #248. Local `main` is
`4683ecd9a1b9ead5eb84be152760d12583da0f0e`. These are local Git observations, not fresh remote observations.

The integrated [master plan](../../product/master_plan.md) and [delivery_train table](../../../release/index/plan.v1.toml) already encode:

- Complete local application and terminal workflows on declared Windows, Linux and macOS targets in 0.1.
- Complete WinForms and GTK3 reference desktops before final 0.1.
- AppKit preview in 0.1, acquisition in 0.2, hosting in 0.3, AppKit graduation in 0.4.
- Terminal/Desktop composition, with an actual portable and installed-use path for each.

The delivery-train status still says pending integration, and workspace recovery remains the active WorkUnit. Those records need evidence-aware closeout. Their stale status does not mean their code must be reimplemented
or that all their acceptance obligations have passed.

The active release selector still describes the distinct Alpha.5 candidate, three product profiles and eight assets. It has publication, signing, tagging, human acceptance and support activation false. Preserve that
historical qualification boundary. It is not inherently a contradiction that the future release contract is broader than an older candidate.

The supplied 1,532 Python tests, 41 native tests, 13 hosted contexts and large scale fixture remain reported evidence; they were not rerun. ULK #18 and USK #27/#28 must be reobserved before any provider action. Full 0.1
completion is not established.

## 3. Freeze the local product, precisely

Use the existing J01–J12 identifiers. Expand their outcome checklists only where the integrated contract requires it, and resolve ambiguous capabilities explicitly rather than accumulating every example from every report.

| Journey | Required local outcome |
|---|---|
| J01 First run/workspace | Create/open/inspect; migrate supported state; inspect and recover interrupted work; bounded rollback |
| J02 Installation library | Discover, identify, classify, register read-only, select and explain drift |
| J03 Managed installation | Install accepted local material; verify, repair, local update, rollback/downgrade disposition and safe removal |
| J04 Instances | Complete the admitted create/select/clone/configure/compare/archive/import/export lifecycle with round trips |
| J05 Configuration | Supported presets, layers, overrides, validation and effective-value provenance |
| J06 Content/modpacks | Local import, resolve, exact lock, diff/apply/verify/rollback and offline reconstruction |
| J07 Worlds/saves | Inspect, consistent backup/snapshot, restore/fork, associate, bundle round trip and retention |
| J08 Readiness/Make Ready | One current backend judgment; understandable, revision-bound local preparation and partial-completion reporting |
| J09 Play/session | Real menu and selected-save routes, supervision, stop, Last Run, relaunch and uncertainty recovery |
| J10 Recovery | Truthful recovery across workspace, setup, content, world and session ownership domains |
| J11 FacMan maintenance | Portable/installed use, verify/repair, local-package update/rollback, uninstall and preservation |
| J12 Diagnostics/support | Useful diagnosis, safe startup, identity/capabilities, bounded redacted export and offline help |

Do not infer universal support for installation moves, cross-volume migration, arbitrary source formats, every historical Factorio version, every compositor, or every filesystem. Name the admitted forms. An unadmitted
operation needs an honest refusal; an admitted required operation cannot be silently removed to make a gate pass.

Every ordinary applicable outcome must work through human CLI, JSON/RPC, fullscreen TUI and linear TUI. WinForms and GTK require native ordinary workflows. Advanced is for experts, not a substitute for required workflow
design. macOS terminal completeness is independent of AppKit's preview status.

The terminal must run its own help, diagnostics and workflows without loading a GUI toolkit or requiring a display. Launching graphical Factorio still has the game's own display prerequisites.

The target matrix must bind OS build, architecture, runtime, filesystem, terminal capabilities, toolkit/display backend, distribution form and source format. Start from the selected Windows x64, Ubuntu 24.04 x64/X11 and
macOS Intel candidate families; verify exact floors before stronger claims. Native Wayland and additional architectures require their own explicit admission and evidence.

## 4. Preserve the ownership boundaries

| Owner | Permanent responsibility |
|---|---|
| FacMan | Factorio meaning, workspace, instances, configuration, content/world intent, readiness, workflows and presentation |
| Universal Launcher | Generic runnable/session lifetime, process identity, outcomes and authoritative Last Run |
| Universal Setup | Installed-software ownership, materialization, verification, transactions, generations, repair and recovery |
| Frontend adapters | Controls, focus, navigation, local selection and rendering over typed results/actions |
| Release composition | Exact provider/resource/component/profile selection and package identity |

Keep the existing `FrontendSession` and typed presentation seam. Complete consumer adoption rather than adding another universal interface above it. Rendering must not dispatch effects. Frontends retain resource IDs and
UI preferences, not competing readiness or terminal-result authorities.

Not every filesystem write belongs to USK. FacMan owns its workspace and product-domain transactions. Each owner records its effects; the product correlates their operations. Make Ready is orchestration and may partially
complete. It must not promise a global atomic commit across separately owned journals.

Shared code needs a current consumer and a meaningful invariant. A fourth implementation repository, full generic provider workbenches, a new global schema family, mandatory resident daemon or renderer/toolkit migration
has no demonstrated place on the current critical path.

## 5. Prove two exemplars early

### A. Existing installation and session

Use an identified packaged build and an exact local game input, registered read-only. Create an owned isolated instance, inspect readiness, launch to the real menu in an authorized lab, exit, inspect Last Run, relaunch,
lose the frontend/transport and recover the actual outcome.

Pair the happy path with installation drift after readiness, uncertain dispatch, frontend death, and negative game-route controls. Observe process identity and filesystem effects independently. A menu screenshot alone is
insufficient.

This exemplar does not depend on completing managed installation or a documentation-only ULK PR. It depends on the actual process/session implementation, package, input and permitted lab. Engineering execution discovers
defects; final release execution later binds final delivery bytes.

### B. Managed installation and recovery

From admitted local material, plan an owned fresh target, stream and verify entries, activate a verified generation, detect damage, repair, interrupt, restart, recover, roll back and remove. Check preserved data independently.

USK branch implementation and noncanonical canaries can develop before provider promotion. Canonical FacMan adoption and final product proof require the accepted provider package and separate lock change. A canary result
is useful without being release evidence.

Converge the exemplars only after they work independently: managed installation → configured instance → exact content/world → Play → local update → recovery. This finds process and setup failures much sooner than waiting
for the entire product to converge first.

## 6. Finish provider lifecycle at the smallest useful boundary

Refresh the real USK stack. If #27/#28 remain open, integrate in their actual ancestry order, preserve the base branch until the dependent branch is safely retargeted, regenerate source-bound metadata and review the
changed delta. Handle ULK's truth-only closeout independently.

The minimum useful restart policy is entry-based: reuse verified completed entries whose identity still matches; restart an incomplete entry from its bound source; refuse changed source, ownership or staging. Arbitrary
mid-Deflate resumption is not required unless separately justified.

Complete generation activation, rollback retention, cancellation around commit, process/session leases and safe cleanup. Revalidate source and target identity after acquiring the relevant locks. Verify real admitted
source formats, offsets beyond 4 GiB, many-entry metadata pressure, disk full and journal failures. Fixed payload buffers do not prove bounded total process memory.

Promote a coherent consumed USK subset under the provider's actual rules, produce installed package/ABI/header identities, and adopt through a separate FacMan lock change. Keep unchanged canonical ULK inputs unless an
actual runtime or contract dependency requires their change. Do not tie two provider promotions together for administrative symmetry.

## 7. Complete terminal and native interfaces incrementally

Capture existing grammar, aliases, RPC framing, exits, wait defaults and packaged invocation before refactoring. Keep `facman`, `facman --rpc`, `facman tui` and the separate GUI role. Draft command spellings and schemas
in older reports are proposals, not compatibility authority.

Preserve the integrated NO_COLOR repair. Colour, renderer, Unicode, motion and assistive preferences are separate. Both TUI modes need ordinary task parity; capability detection determines where fullscreen can run.

Test redirected streams independently, no machine prompts, quoting/empty arguments/`--`, native-path representation, broken pipes, slow readers, bounded events, terminal-control injection, grapheme/cell clipping, resize,
paste and focus. Acceptance, terminal success, cancellation request, actual cancellation and unknown outcome remain distinct. Observation deadlines must not accidentally determine backend operation lifetime.

Build the native laboratory now from production controls and reducers. Add an API/CLI/PTY/native driver as each slice becomes testable. A missing Mac host does not block a Windows gallery or Linux-free fixture work. Add
independent effects, real keyboard/pointer tests, accessibility traces, screenshots and timings.

Prioritize WinForms completion while GTK consumers stay current. They do not technically depend on one another. Keep AppKit's preview building and semantically aligned. Each completed domain should reach its ordinary
desktop controls before integration defects accumulate across the whole application.

System Native is the reliable baseline. OEM+ adds restrained product identity to FacMan-specific surfaces while preserving native focus, text entry, menus, warnings and contrast. Bounded preferences should have
preview/apply/revert and safe startup. Broad executable themes, arbitrary styling engines and plugin ecosystems are later work.

## 8. Give installation and maintenance equal product priority

The setup source inspection confirms that native integration is performed after `self_setup::execute` returns a receipt. It also shows integration receipts and immediate compensation attempts. Therefore the defect is not
accurately described as “no receipts.” The unresolved boundary is durable ownership and recovery across the payload and native-integration phases, especially process death and pre-existing registrations.

Create a focused failure reproduction and fix the owning layer. Require explicit ownership, previous-state preservation, deterministic resume/compensation, and verification around shortcuts, uninstall registration and
their receipts. USK may own typed effects or delegate to an admitted native authority; neither a frontend nor a bootstrap should silently invent another installation engine.

Keep maintenance independently runnable when the installed GUI or resources are broken. Use an external verified handoff for self-replacement. A minimal bootstrap/recovery path must work without an optional GUI
prerequisite; richer native presentation can sit above the same operation model.

Terminal and Desktop are component selections. Desktop includes the terminal component and one native GUI. Terminal omits GUI payload and has a real installation/maintenance path. Preserve current package formats until a
reviewed producer/selector transition. Derive the asset count from those admitted profiles; eight, eleven and fourteen describe different inventories, not competing eternal rules.

Bind resources to the executable's accepted compatibility identity and generate a closed runtime inventory. Keep mutable user state out of immutable application payloads. Preserve the acyclic identity order: resources →
executable expectation → unsigned stage → signed components/containers → external delivery manifest.

## 9. Use explicit start and completion dependencies

The [TODO](TODO.md) separates `start_after` from `close_after`. A frontend page can start when its typed scenario is stable; complete frontend qualification waits for the required backend outcomes. A world backup can
start before the modpack solver finishes; full content-linked world reconstruction waits for both.

Every implementation slice should leave an executable public outcome, a paired failure/recovery case, usable interface feedback and applicable documentation. Close a slice with integration and package evidence at the
appropriate boundary; do not promise full release acceptance for every small PR.

Use at most one major provider/persistence migration. Recommend one main product focus and one interface/verification focus alongside it, subject to the existing plan's WIP limit. These are areas of work, not an
instruction to launch autonomous agents. Work can proceed sequentially with one implementer.

Keep the next queue to six selected outcomes in this proposal. This is a display preference, not a replacement for the repository's existing ready/WIP limits. Every selection names the missing prerequisite and next
observable exit. Stop repeating an unchanged blocked check when another permitted task can advance.

## 10. Make quality and release evidence finite

[ACCEPTANCE.md](ACCEPTANCE.md) defines outcome, profile, interface, package and scenario coverage. Preserve existing state vocabulary and orthogonal implementation, integration, machine, package, experience and support
fields. Unknown is not pass; N/A needs a scoped reason.

Document actual process-crash, restart and power-loss claims separately. Test mixed clients, stale plans, active-generation cleanup, corrupt state/resources, support redaction and consistent saves. Installation rollback
cannot promise that an older game loads a save converted by a newer version.

Use existing performance fixtures. Calibrate startup, usable feedback, scoped queries, total memory and lifecycle throughput on named hosts before imposing numerical thresholds. Require bounded growth, working
cancellation and no unexplained stalls now. Do not copy attractive timing numbers from reports as achieved results or arbitrary release gates.

Use targeted tests during changes, full required checks at integration boundaries, broader risk campaigns on affected inputs, and final delivery tests on candidate bytes. Evidence reuse requires an explicit
dependency/applicability check. Changed validators and oracles deserve scrutiny because they can produce false green results.

Prepare trust, artifact retention, support and human-test arrangements early. Construct the intended Beta version before testing it; signing, packaging, version edits or a different source produce a different delivery
identity. Accept and publish those exact files. RC and normal release candidates need their own binding and affected requalification.

Preserve actual human observations as human; automation and model review are different evidence classes. Existing session authorization remains effective within its scope. Ask only for a concrete missing decision when
the next dependent action needs it, after preparing its reviewable inputs. A blocked release action does not block ordinary authorized engineering.

## 11. Finish the planning work once

Assimilate the recommendations into the existing plan, readiness matrix, provider locks, package producers/selectors and interface tests. Preserve old receipts. Generate status views from authoritative records; do not
make a tracked file contain the hash of its own containing commit.

The existing plan-view check passes even though some integrated work still appears active. That establishes projection consistency, not semantic integration closeout. The repair belongs in source records with the
appropriate evidence, then regeneration.

Track closed required outcomes, unresolved severe defects, dependency wait time and evidence invalidations. Forecast only after the exemplars and first native scenario reveal actual throughput and remaining work. Keep
0.5–0.8 as an admission portfolio rather than a speculative feature schedule.

The first implementation block should leave one concrete product or lifecycle result plus a reproducible native scenario, or exact actionable blockers. Another comprehensive architecture document is not its success criterion.
