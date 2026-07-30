# FacMan Windows instance-isolated Play revalidation 03 — staged

Date: 31 July 2026

WorkUnit:
`FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-03`

State: `staged_not_prepared`

## Disposition

Qualification-04 passed against the reviewed repaired source composition and
the coordinator created one new exact stage. This checkpoint records staging
only:

```text
operator                    unassigned
operator assignment         required
observer self-test          not started
observer run directory      absent
WPR                         idle
prepare                     false
baseline                    false
observer capture            false
permit                      false
Factorio execution          false
human verdict               unset
route authority             false
authority promotion         false
```

No result in this checkpoint is a human `Pass`, `Fail`, or `Inconclusive`.

## Source and qualification binding

```text
FacMan
ab159b8ced48ecbaaa1d8f37bb1b4687c6b4c679

Universal Launcher
7fc25340623131ba86c08dca4fb8a43b18a4520d

Universal Setup
3048128963dc718a7c38c1cfcdda9e813a23b0db

remote closure report SHA-256
e6f9be1c563a06a8ef28a005e982e92dc52b41532b98b4cd2d08881dce1df56f

qualification schema
facman.play_candidate_qualification_binding.v3

qualification report schema
facman.instance_isolated_candidate_qualification.v3

qualification digest
49732ad3a785a1341f642b9cfd99c01a78bbb199f6a3ef8b88b8a7acd79d9868

qualification report digest
04efedc73010b6dc09c9c92c9b2f6f7499db9c7a23f5696e2bc1baaa772a137f

qualification binding file SHA-256
ea30efc379fc026d64e6a9611f941d2a68cf3caf527088b75f370d27af5271cd

qualification report file SHA-256
df9ee8e9730626fd1e9c209ecf56bff77652bea29d97a84359e18e18fa8520a1
```

## Exact stage

The canonical absolute stage path is:

```text
C:\Users\Jules\AppData\Local\Temp\facman-revalidation03-stage-final\
FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-03
```

The line break above is presentation only. All operator actions must bind the
single complete absolute path and must not select by prefix, parent scan,
modification time, relative path, glob, or interactive guessing.

Inventory:

```text
file count                  16
total bytes                 63,878,491
missing files               0
unexpected files            0
reparse points              0
top-level directories       artifacts, operator, source, workspace
```

Binding identities:

```text
qualification copy
artifacts\qualification-binding.v3.json

qualification copy SHA-256
ea30efc379fc026d64e6a9611f941d2a68cf3caf527088b75f370d27af5271cd

historical v2 copy
absent

staged-candidate digest
b2e8335fa372e8f796af939e426a0cc3c7f98a68497e8fe9326e8b7f1da5a35c

staged-candidate file SHA-256
7caa9fa1204f80f70b0b88935abc2ba99a7e41a030e672cb83f3da82af7c06c6

coordinator config SHA-256
31cf5523243130f8b13cb7df6dc3c93e5edade9bee0146fac7d0ad4bee22cc8e

artifact manifest SHA-256
fc2be64f4463d1c705aa766de8f34a8d95e13a273058e81e06f52db918ab96f9
```

The staged workspace has:

```text
instance spec digest
4cae0b49f6b3f85cf9defdfe7e0c57ff9d0ed855e9cc81a54e1cef05400bea79

staged instance binding digest
9cad1d259ed5c13618a761743206bcad7719e5f252ee14823f8361a033e92a0e

staged readiness digest
767f584639a2dfa23ca1d28f0b442aba8437b1b44513f4e1556b5c86f90f6212
```

## Exact route and operations

```text
platform              Windows x64
Factorio              2.0.77
distribution          standalone non-Steam
launch intent         menu
isolation mode        instance_isolated

launch 1 operation
gate4c-instance-isolated-6f6834a2-7773-49bb-85a4-985b555caf39

launch 2 operation
gate4c-instance-isolated-d5e2105a-46ba-4edb-a757-ce05657b0361
```

The stage observed the current bound Windows principal in session 1 at medium
integrity. That reviewer-principal binding is not an explicit operator
designation and grants no prepare authority.

## Stage invocation note

An initial invocation supplied the exact new task path before creating the
empty root. The frozen no-follow auditor rejected it as missing before any
stage artifact, config, workspace, evidence, or authority-bearing output was
created.

The corrected invocation:

1. preserved the diagnostic run log;
2. created the exact empty task root;
3. used a new isolated run-log directory;
4. used task-local TEMP/TMP;
5. set `PYTHONDONTWRITEBYTECODE=1`; and
6. reran only coordinator `stage` with the same unused fresh operation IDs.

It completed with empty stderr. This is a precondition correction before the
stage existed, not an in-place repair of candidate evidence.

## Validation

After staging:

```text
frozen config reload          PASS
qualification digest          exact
staged-candidate digest       exact
v3 binding filename           exact
v2 binding path               absent
source clones                 clean and detached
protected process inventory   empty
WPR                           not recording
prepare/evidence directories  absent
permit files                  absent
verdict files                 absent
```

The string `verdict` appears in the qualified harness filename; that executable
is a staged artifact, not a verdict record.

Repository closeout validation also passed:

```text
focused tests                  36
affected native               1/1
affected Python/package       63
full native                   57/57
full Python                   567
required/unknown skips        0 / 0
optional/unsupported skips    7 / 2
strict schemas                304
promotion gate                pass
```

The first affected and first two full promotion attempts exposed the existing
developer-runner gap: admitted package tests need a complete install graph,
and external archive proof binaries require explicit binding. They are
preserved as non-acceptance runs. The final run completed the disposable build
graph, explicitly bound the three exact archive proof/fuzz executables, and
passed with no required or unknown skip.

## Next authority boundary

The next sequence is:

```text
explicit operator designation for revalidation-03
→ protected-resource coexistence declaration
→ fresh volatile checks
→ fresh elevated observer self-test
→ exact closed three-claim attestation
→ separate exact prepare authorization
→ execution-state lease
→ prepare
```

None of those actions is authorized by this checkpoint. Revalidation-02, its
qualification, and its stage remain historical and immutable. The diagnostic
qualification-04 chain also remains preserved and must not be confused with
the accepted repaired chain.

Only after two independently fresh launches may a human record exactly
`Pass`, `Fail`, or `Inconclusive`. A later `Pass` does not itself promote a
route.
