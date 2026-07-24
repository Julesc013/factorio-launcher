# Verdict 03 post-run diagnosis

## Preserved source evidence

The complete source attempt remains retained and unmodified under:

```text
E:\Temporary\FacMan\FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-03
```

The diagnosis binds the original operation
`gate4c-verdict03-launch1-20260725a`, source revision
`885b9822809c4b3e91e784bdd7e3b8b261533901`, ETL SHA-256
`ffd0e7648bc43e08d95c87abc5f1ff016ac55c1168fc07047162aae8e16f56e6`,
and events CSV SHA-256
`37e0684e1aef8a39aece855d90cefa09344a08e55a09f662216e27ec16f64085`.

No Factorio process or WPR session was started during this diagnosis.

## Finding 1: lifecycle staging collision

The observer wrote `observation-result.json` below the runtime-owned
`candidate-artifacts` directory before
`persist_candidate_artifacts()` attempted its exclusive directory creation.
The runtime then correctly refused the already-existing target, leaving the
required lifecycle packet incomplete.

The correction gives observer-side artifacts the disjoint
`observer-artifacts` root. The runtime remains the only owner permitted to
create `candidate-artifacts`. A native regression fixture now creates observer
evidence first and proves that lifecycle persistence still succeeds.

## Finding 2: selected-installation write

The original ETW CSV directly attributes two successful `FileIoCreate` events
to Factorio PID `29512`:

```text
D:\Games\Factorio\2.0\bin\x64\NVIDIA Corporation
D:\Games\Factorio\2.0\bin\x64\NVIDIA Corporation\umdlogs
```

Both operations used create disposition `FILE_CREATE` and completed
successfully. The reviewed process request used the selected executable
directory as its current working directory, allowing the NVIDIA user-mode
driver to place relative diagnostic state inside the protected installation.

The correction binds the process working directory, `TEMP`, and `TMP` to:

```text
<workspace>\temporary\<operation-id>\process
```

That directory is within the exact `operation.temporary` writable resource.
The provider independently refuses any other working directory.

## Finding 3: incomplete file-object target evidence

Six original `FileIoWrite` records used pre-existing file objects whose names
were not present in the Verdict 03 trace. They remain unresolved when the
retained CSV is reprocessed. They are not filtered or reclassified.

The v6 observer profile adds the Windows kernel `DiskIO` keyword so future
traces contain `FileNameCreate`, `FileNameDelete`, and end-of-trace
`FileNameRundown` events. The translator now resolves pre-existing file objects
from a future rundown only when no create, close, or name-lifecycle boundary
permits object reuse between the effect and the rundown. Adversarial tests
prove that a reuse boundary preserves `unresolved_target = true`.

Microsoft documents that file-name and file-rundown events require the disk
file-I/O enable flag and that the rundown enumerates open files at trace end:

<https://learn.microsoft.com/en-us/windows/win32/etw/fileio>

The retained Verdict 03 evidence cannot be retroactively upgraded by the new
profile and remains `Inconclusive`.

## Finding 4: Registry target reconstruction

The retained trace contained one `RegSetInformation` event on a result KCB
whose name was not emitted as a KCB-create record. It immediately followed a
successful same-process, same-thread `RegOpenKey` for:

```text
\REGISTRY\MACHINE\SYSTEM\CurrentControlSet\Control\Cryptography\ECCParameters
```

The translator now accepts that handoff only for the immediately following
Registry operation on the same PID and thread. A failed open, different thread,
intervening Registry operation, or missing base identity remains unresolved.
End-of-trace KCB rundown fallback remains reuse-boundary checked.

Failed Registry operations are no longer reported as persistent effects.
Missing or malformed completion status remains an attribution gap.

## Finding 5: successful external Registry mutations

After the stricter target and completion handling, the retained trace still
contains 328 successful external Registry mutations attributable to the
supervised processes:

```text
Factorio:
  RegSetInformation  202
  RegSetValue         99
  RegCreateKey        26

FacMan harness:
  RegSetValue          1
```

The Factorio values include DirectInput device-instance state under the
interactive user's Registry hive. The harness-associated value is resolved by
KCB rundown to Windows Background Activity Moderator state and names the
Factorio executable.

These effects are not waived. The frozen policy states that any attributed
external Registry write is fail-eligible. Microsoft identifies
`RegSetInformation` as a key-metadata setting operation and `RegSetValue` as a
value setting operation:

<https://learn.microsoft.com/en-us/windows/win32/etw/registry>

The exact Factorio binary contains SDL's `SDL_DIRECTINPUT_ENABLED` hint. The
candidate's versioned minimal environment is advanced to
`factorio.menu-minimal.v2` and pins that hint to `0`, matching SDL's documented
way to disable DirectInput device detection:

<https://wiki.libsdl.org/SDL2/SDL_HINT_DIRECTINPUT_ENABLED>

This bounded correction is expected to prevent the observed DirectInput
device enumeration. It does not claim to prevent the Windows BAM update. A new
verdict must not be activated merely because the code builds: under the
unchanged policy, successful BAM or any other external Registry mutation
remains route-blocking.

## Finding 6: the frozen writable model does not match Factorio

Create requests are now paired with their `FileIoOpEnd` completion records.
Only successful `FILE_CREATED`, `FILE_OVERWRITTEN`, or `FILE_SUPERSEDED`
outcomes are treated as persistent create effects. A successful
`FILE_OPENED` result is an open, not a mutation; failed or missing completion
evidence is refused or produces an attribution gap.

Microsoft documents those values as the final `IoStatusBlock.Information`
result of a create/open request:

<https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntcreatefile>

After removing the false create positives, 195 successful forbidden effects
remain inside the FacMan-owned instance closure but outside the frozen
subdirectory allowlist. Factorio 2.0.77 legitimately writes these fixed
top-level objects beneath its configured `write-data` root:

```text
factorio-current.log
crop-cache.dat
player-data.tmp.json
achievements.tmp.dat
mod-list.json
.lock
temp/currently-playing-background/**
```

The Gate 4A policy permits selected subdirectories such as `config`, `mods`,
`saves`, and `state`, but it does not permit the exact instance root itself.
Factorio's real write-data layout therefore cannot satisfy the frozen writable
model without filesystem virtualization, reparse indirection forbidden by the
policy, or a separately reviewed policy revision.

Two additional successful creates occurred outside both the instance and the
selected installation:

```text
D:\NVIDIA Corporation
D:\NVIDIA Corporation\umdlogs
```

Changing the working directory prevents the equivalent installation-relative
pollution, but it does not prove that the NVIDIA driver will stop using a
current-drive-root-relative path.

These are product findings, not reasons to reinterpret the frozen criteria. A
normal-host route should be specified as `instance_isolated` with the exact
FacMan-owned instance closure writable and OS/driver-mediated effects
explicitly observed and disclosed. The stronger `hermetic` label requires an
enforced sandbox, container, disposable VM, or an equally strong mechanism
that can prevent the observed driver and Registry effects.

## Reprocessing result

The retained CSV, processed by the repaired translator, yields:

```text
effects                         611
unknown_process_identity       false
attribution_gap                false
unresolved_target              true

filesystem protected             2
filesystem forbidden           197
filesystem unresolved            6
registry forbidden             328

forbidden inside instance      195
forbidden outside instance       2
```

This is diagnostic output only. It does not replace, amend, or complete the
original packet, and it does not change Verdict 03 from `Inconclusive`.

## Repair validation

The repair was validated without starting WPR or Factorio:

```text
focused Python observer, verdict-session, and candidate tests    PASS (44)
full Python discovery suite with clean E: build                 PASS (429)
full native Windows Debug build                                 PASS
full native Windows Debug CTest matrix                          PASS (50/50)
strict repository validators                                    PASS
portable AIDE Lite validation                                   PASS
retained Verdict 03 trace reprocessing                          complete
```

All build products and validation logs are task-owned under:

```text
E:\Temporary\FacMan\FACMAN-GATE4C-VERDICT03-POSTRUN-REPAIR-01
```

No build tree or temporary evidence was created under the source repository.

## Disposition

The bounded implementation defects are repaired, but the frozen hermetic
route is not eligible for another verdict merely because the repair passes.
The retained evidence proves that the unchanged writable-resource model
excludes normal Factorio write-data objects and that a normal Windows host
permits OS/driver-mediated effects outside that model.

The next policy decision must be separate:

1. define an `instance_isolated` normal-host route whose exact FacMan-owned
   instance closure is writable and whose OS-mediated effects are observed and
   disclosed; or
2. add an enforced sandbox boundary before making another `hermetic` claim.

Neither decision is made by this repair, and no Play route or issuance
authority is promoted.
