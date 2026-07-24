# Gate 4C evidence-only verdict harness

## Boundary

The Gate 4C harness is an operator-only native test artifact. It is not
installed, registered as a command, or reachable through the normal FacMan
CLI, TUI, WinForms, or AppKit surfaces.

It can exercise only the frozen candidate:

```text
Windows x64
Factorio 2.0.77
standalone non-Steam
menu
hermetic
explicit empty mod lock
no account, credential, network, Setup, or alternate intent
```

The harness cannot change the frozen policy, prepare an installation, enable a
public route, or write a human verdict into the native candidate packet. Every
native packet retains:

```text
human_verdict = unset
grants_authority = false
product_route_available = false
```

The evidence finalizer cannot manufacture a human observation. It can derive
an evidence-only verdict only after validating two separately supplied,
packet-bound human attestations. That derived verdict never mutates either
native packet and never promotes authority.

## Why this artifact exists

Gate 4B proved the candidate with fake supervisors and independent synthetic
providers. Gate 4C needs a narrow bridge from the same reviewed runtime APIs to
one real interactive process:

```text
fresh ready preflight
→ stable protected/writable baselines
→ exact plan review
→ one-use authenticated permit
→ independent provider revalidation
→ ETW observer active before the process boundary
→ reviewed process supervisor
→ stable post-run comparison
→ native hash-closed technical packet
```

Launching `factorio.exe` manually would bypass those controls and cannot
produce Gate 4C evidence.

## Artifacts

`tools/gate4c_verdict_evidence.py`

- Captures stable baselines from the medium-integrity coordinator and refuses
  incomplete or unreadable protected domains.
- Creates one exact operation-owned temporary closure.
- Captures stable no-follow filesystem manifests and registry value sets.
- Binds the native harness, Python interpreter, evidence tools, baseline,
  classification roots, candidate artifacts, source evidence, machine,
  principal, and policy.
- Compares the exact protected scope after quiescence.
- Can combine two independently verified native packets with two exact human
  observations and derive only `Pass`, `Fail`, or `Inconclusive`.

`tools/gate4c_verdict_session.py`

- Starts the reviewed WPR profile only inside a prepared operation closure.
- Attributes filesystem and registry mutations to the exact Factorio tree and
  the FacMan launch-provider process.
- Uses process lifetime intervals so a recycled child PID is not accepted.
- Treats observer loss, unresolved targets, and attribution gaps as
  inconclusive evidence.
- Encodes observations in the canonical order required by the reviewed C++
  decoder.

`facman_gate4c_verdict_harness`

- Is built only when tests are enabled.
- Refuses ordinary invocation.
- Self-verifies its binary and every supporting evidence artifact.
- Requires one exact hash-closed plan-approval artifact before each permit.
- Keeps one UAC-approved, verdict-scoped observer broker alive across the
  fresh observer self-tests and both launch observations.
- Uses `CandidatePermitIssuer`,
  `HermeticCandidateLaunchProvider`,
  `PlatformProcessSupervisor`, and
  `BoundArtifactCandidateEffectObserver`.
- Persists process output separately from lifecycle truth.
- Binds the exact inherited Gate 4B automated-control proof; it does not claim
  that the interactive session reran that synthetic matrix.
- Never records a human verdict.

## Verdict 03 procedure

Build the exact merged tooling revision into the task-owned root:

```powershell
cmake -S . `
  -B 'E:\Temporary\FacMan\FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-03\verdict-harness\build' `
  -G 'Visual Studio 18 2026' -A x64 `
  -DFACMAN_BUILD_TESTS=ON `
  -DFLAUNCH_UNIVERSAL_LAUNCHER_ROOT='D:\Projects\Universal\universal-launcher' `
  -DFLAUNCH_UNIVERSAL_SETUP_ROOT='D:\Projects\Universal\universal-setup'

cmake --build `
  'E:\Temporary\FacMan\FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-03\verdict-harness\build' `
  --config Release --target facman_gate4c_verdict_harness
```

Stage the exact reviewed Gate 4B candidate and fresh disposable workspace with
`tools/gate4c_verdict03_coordinator.py stage`. Then start the complete
coordinator from a normal, non-elevated terminal:

```powershell
& '<task-root>\verdict-harness\build\Release\facman_gate4c_verdict_harness.exe' `
  --run-verdict03 '<task-root>\operator\verdict03-config.json'
```

The coordinator causes one UAC prompt for the exact reviewed observer broker.
That broker runs one fresh elevated observer self-test before each launch,
controls WPR for both observations, accepts only the closed
`start/status/finish/abort` surface, and exits after launch two. The coordinator
remains medium integrity throughout. It creates each quiet-host attestation,
preflight, baseline, and session only after the corresponding fresh self-test.

For each launch, the coordinator prints the exact plan and waits for a separate
canonical approval artifact bound to its plan digest. No phrase typing is
required. After each normal game exit it waits for a packet-bound human
observation artifact. The second baseline, plan, and permit are all fresh.

The first launch human observation covers:

```text
normal menu observed
no save inferred
disposable game created
save completed
returned to menu
normal exit
last-run evidence accurate
```

The second launch uses a new operation, new baseline, and new permit. It covers:

```text
normal menu observed
no save inferred
saved game visible
returned to menu
normal exit
last-run evidence accurate
```

Each launch requires fresh blocker-clearing evidence. A prior ready packet is
not reused after its lease expires.

## Verdict law

The finalizer first asks the native runtime to revalidate each lifecycle packet
with stable no-follow reads. It then requires:

- One exact instance and machine binding across both launches.
- Two distinct operations, permit IDs, and permit-claims digests.
- Exact first- and second-launch human observation schemas.
- The same provider-scoped human reviewer.
- Native packets that still carry no verdict or authority.

The derived result is:

```text
Fail
  when either technical packet contains fail evidence
  or the human reviewer observes a false frozen invariant

Inconclusive
  when either technical packet is not eligible for human review
  or a required human invariant cannot be established

Pass
  only when both technical packets are eligible
  and every human invariant is true
```

The final verdict record is evidence only:

```text
grants_authority = false
product_route_available = false
```

A `Pass` still requires a separate exact-route authority-promotion WorkUnit.
