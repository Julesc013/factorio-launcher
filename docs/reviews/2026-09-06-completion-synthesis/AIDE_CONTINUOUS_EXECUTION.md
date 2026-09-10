# AIDE continuous implementation: feasibility and smallest useful activation

6 September 2026 · Proposed operating arrangement · **Not activated**

## Decision

Use AIDE to preserve the plan, task state, context and evidence while coding workers implement bounded changes. Aim for continuous progress across worker sessions, with automatic selection of the next ready slice and
durable recovery after interruption.

The inspected AIDE system is not yet a turnkey unattended coding engine. Enabling policy flags would not supply the missing execution machinery. Build or admit the smallest runner needed for this programme; do not make
the whole AIDE runtime, Workbench or future platform a prerequisite to FacMan.

The first programme endpoint should be **complete 0.1 engineering and machine/package qualification, with the exact candidate acceptance packet ready**. Required human experience and publication remain explicit
subsequent gates. Future optional roadmap entries are not an endless queue to activate automatically.

## What the new week plan improves

Retain its four distinct predicates: may start, may integrate, may declare complete, may release. Add the integration/release predicates to existing WorkUnit and gate evaluation, without creating a second canonical backlog.

Retain both packaged exemplars and independent world backup/restore. Retain the seven setup interruption/foreign-replacement cases. Beta.1 should contain the full admitted local feature set; later betas repair defects.
Reserve correction capacity rather than promising exactly three betas or a Beta date.

Treat 7–13 September as preferred work windows. A scheduler must select actual ready work, not execute a Thursday task solely because it is Thursday. The document's instruction to adopt the plan is a proposal in an
attachment, not an authority grant from the current user message.

## What exists locally

The main AIDE checkout was inspected at local HEAD `7d8bf19d878fd9ad29859a6cba4b7de64ad80ecc`, with no local changes reported. Its README is conservative and some implementation has advanced beyond the overview; the
following source boundaries are more specific.

| Component | Inspected capability | Limit relevant to this request |
|---|---|---|
| FacMan AIDE Lite | Context, task/governance helpers, evidence and advisory outcome analysis | Controller policy explicitly forbids an autonomous loop and model/provider/network calls |
| AIDE registered process provider | Immutable registered process invocation, preconditions, receipts and bounded execution | Not an arbitrary worker launcher; current source declares cancellation unsupported |
| AIDE LocalProcessExecutionHost | Executes one allowlisted reference worker in a bounded fixture workspace | Explicitly excludes general worker harness, scheduler and repository mutation |
| AIDE local Service | SQLite objects/events/artifacts/idempotency/cursors for local use | Not a persistent background scheduler or model-calling service |
| AIDE durable WorkerRun slice | Composes local service/trust/process-host observations | Fixture-backed temporary service state; explicitly excludes AI workers, scheduler, leases, supervisor, persistent service and target mutation |
| FacMan development delegation | Design for independent control/implementation/assurance | Standing dev integration and isolated-lab delegation are not activated in the inspected files |

These are source observations, not newly rerun AIDE acceptance tests. A code module or acceptance record for a narrow fixture does not establish a general long-running implementation service.

## Minimal worker loop

```text
observe relevant source, plan and authorization
→ select the next admitted dependency-ready slice
→ acquire durable ownership of that slice and its workspace
→ assemble bounded context and invoke the admitted coding worker
→ record the actual patch and worker outcome
→ run affected tests and required independent assurance
→ integrate through the currently authorized mechanism
→ verify the integrated source and applicable package evidence
→ update canonical task/outcome records and checkpoint
→ select the next ready slice
```

If a task becomes blocked, preserve its state and resume trigger, then select an independent ready task. If no ready work exists, enter a recorded wait state with bounded backoff and wake conditions. Do not busy-poll,
create filler work, or call the programme complete merely because the next action is unavailable.

Use the existing `release/index/plan.v1.toml` for FacMan execution intent, target-local `.aide/queue/` records for admitted work, and AIDE's existing protocol/evidence objects. Treat BACKLOG F-IDs as the dated crosswalk
they are. Preserve references to each repository's own source of truth instead of copying AIDE's source queue or memory into FacMan.

## Required runner capabilities

1. **Durable dispatch and recovery.** Persist attempt identity and intended effect before dispatch. On restart, reconcile the existing worker/process/patch before retrying. Survive supervisor death and machine restart
  without duplicate work or invented success. Enforce one writer for the same protected workspace/resource and fence stale workers.
2. **An admitted coding-worker adapter.** Use a specific available agent host through a reviewed contract. Bind allowed paths, source, context, tool access and output. The current reference-worker fixture is not this
  adapter. Configure any necessary network/provider access and credential references explicitly; do not expose raw credentials in packets or logs.
3. **Test and assurance coordination.** Persist test-job identity, exact source/head/tree, result and retained artifacts. Resume asynchronous checks; review handwritten persistence/archive/process/ABI/security code
  independently. Record the actual reviewer class. A model review is not a human usability verdict.
4. **Bounded integration.** Reobserve the actual PR/base/head/checks and active authority immediately before integration. A moved head invalidates its approval binding. Preserve stacked dependencies and the separate
  provider promotion → generated package → FacMan adoption path. No policy rewriting or failed-gate waiver to make progress.
5. **Operational limits and stop control.** Enforce explicitly configured cost, concurrency, disk, time/resource and retry limits. No unlimited paid run is implied. Provide verified pause/cancel and graceful
  worker/process handling; the current process provider's lack of cancellation is a real qualification gap. Recovery after interruption is more useful than promising that interruption can never happen.
6. **Progress detection.** Report actual outcomes, changed evidence, blockers and next action. Repeated same-root-cause failures route to diagnosis/assurance rather than endless retries. Preserve failed attempts. A
  changed assertion or golden cannot silently make an old failure disappear.

Reuse current primitives where they meet these guarantees. Keep the first runner single-machine and narrowly scoped; remote hosts can supply named test results without requiring a new distributed development platform.

## Activation boundaries

Existing user/session authorization remains effective within its scope. The unactivated delegation tables do not negate separately authorized ordinary edits. They do show that a new standing unattended programme cannot
assume every future merge, provider promotion or laboratory action is permitted.

| Area | Needed before unattended use |
|---|---|
| Programme | Adopted 0.1 scope, exact repository/WorkUnit mapping, done predicate and current source observation |
| Worker | Named supported host/adapter, authorized model/network path if needed, tested invocation/result contract |
| Integration | Feasible exact-green dev integration and provider-main promotion through actual policy; resolve the max-one-unpromoted checkpoint rule where it obstructs the intended flow |
| Labs | Named Windows/Linux/macOS hosts, exact local game/source custody, disposable roots/effects, reset and evidence export |
| Operations | Explicit resource/spend limits, state/artifact retention, restart owner and working stop mechanism |
| Final gates | Named human experience/release owner; current signing/publication/support policy retained until separately changed |

Prepare concrete inputs before asking for a missing approval. Obtain standing bounded delegation once where appropriate, then reuse it within scope. Do not ask after every ordinary patch. Do not interpret a permission to
test one game input as permission to modify real user saves or publish a release.

FacMan's current `AGENTS.md` says provider/model/network calls and Gateway forwarding remain forbidden until a reviewed target queue item enables them. Its controller policy lists `autonomous_loop` as forbidden. The main
AIDE operating law also requires queue admission for Runtime/provider work. This request's feasibility assessment does not silently remove those boundaries.

The main AIDE repository's `.aide/policies/review-gates.yaml` additionally requires: “Wait for explicit human review before continuing.” Its listed gates include changes to its queue/autonomy policy, permission widening
and integration beyond a local commit. A reviewed standing-delegation amendment would need to define which routine transitions can proceed automatically; an agent cannot relabel its own review as the required human
review. This AIDE-source policy was inspected in the main AIDE repository; no same-named policy file exists in FacMan's imported policy directory.

## First implementation item and acceptance

Map one bounded **continuous-worker pilot** to the actual AIDE queue and a FacMan target item after inspecting the relevant current queue. Do not invent an active WorkUnit ID or implement out of order from this document.
Build the generic runner in AIDE or admit an existing suitable host; keep FacMan-specific outcome selection and evidence in FacMan.

The first pilot should use one isolated, low-impact FacMan task and an independently reviewed result. Before scaling, prove:

- Worker success, refusal, timeout, crash and malformed output produce truthful states.
- Supervisor death before dispatch, after dispatch and after patch creation can be reconciled without duplicate execution or data loss.
- Duplicate/stale claims cannot both write; changed source invalidates stale execution/review inputs.
- Failed tests block integration; independent ready work can proceed.
- Budget/disk limits and operator pause/cancel work; ongoing children are accounted for.
- Evidence survives task-root retirement and can be retrieved by its recorded identity.
- One real authorized worker creates a useful patch, validation runs, review/integration uses the legitimate mechanism, and the next admitted slice is selected automatically.

Passing a mock runner test is necessary but insufficient for the last condition. Do not broaden the runner into a general remote service, UI suite or universal agent platform to finish this pilot.

Ordinary currently authorized FacMan implementation can continue in bounded agent sessions using AIDE's existing context and evidence while this runner is developed. There is no need to wait for AIDE's entire roadmap.

## Meaning of continuous and done

Continuous means progress resumes across worker/context/process boundaries without requiring the user to type “continue” after every completed slice. It does not guarantee uninterrupted compute, available hosts,
unlimited quota, or the absence of required human observations.

| State | Behaviour |
|---|---|
| Ready engineering work exists | Continue selecting and completing admitted slices |
| One task is blocked | Record its exact blocker and work on independent ready outcomes |
| Infrastructure temporarily unavailable | Checkpoint and retry on bounded policy; resume when available |
| All remaining work needs a specific external input/decision | Wait with an explicit resumable state and concise actionable report |
| Complete 0.1 machine/package gate and acceptance packet | Record engineering endpoint accurately; enter required experience/release workflow |
| Human verdict or publication is required | Use the actual authorized actor; never manufacture the verdict or promote by timeout |

The same system can later service 0.1 and implement admitted 0.2/0.3/0.4 work. Each train needs a new bounded scope and its required capability/credential/host admission. Optional 0.5+ ideas do not expand the active goal
automatically.

## Source references

- [FacMan AIDE controller policy](../../../.aide/policies/controller.yaml)
- [FacMan project instructions](../../../AGENTS.md)
- [FacMan autonomy policy](../../../release/index/autonomy_policy.v1.toml)
- [FacMan branch policy](../../../release/index/branch_policy.v1.toml)
- [AIDE source overview](D:/Projects/AIDE/aide/README.md)
- [AIDE durable WorkerRun implementation](D:/Projects/AIDE/aide/core/service/durable_worker_run.py)
- [AIDE local process host](D:/Projects/AIDE/aide/core/execution/local_process_host.py)
- [AIDE registered process provider](D:/Projects/AIDE/aide/core/execution/registered_process.py)
- [AIDE human review gates](D:/Projects/AIDE/aide/.aide/policies/review-gates.yaml)

The two new supplied documents were read in full. No worker loop, scheduler, service, provider call, policy activation, branch change or release action was started by preparing this assessment.
