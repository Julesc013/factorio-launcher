# FacMan Windows instance-isolated Play revalidation 04 — staged

Date: 1 August 2026

WorkUnit:
`FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-04`

State: `staged_not_prepared`

## Disposition

Qualification-05 passed against the exact reviewed repair integration and the
coordinator created one accepted immutable stage. This checkpoint records
staging only:

```text
operator                    unassigned
operator assignment         required
observer self-test          not started
observer run directory      absent
WPR                         not started
prepare                     false
baseline                    false
observer capture            false
permit                      false
Factorio execution          false
human verdict               unset
route authority             false
authority promotion         false
```

No result here is a human `Pass`, `Fail`, or `Inconclusive`.

## Source and qualification binding

```text
FacMan
8f495d63b412a3af5a22305d9d8b424efd4303d2

Universal Launcher
7fc25340623131ba86c08dca4fb8a43b18a4520d

Universal Setup
3048128963dc718a7c38c1cfcdda9e813a23b0db

remote closure report SHA-256
6877cab671a97179a20dcacde424caaf8e94d1c5275a1dd7a4bda5ecb143e4ba

qualification schema
facman.play_candidate_qualification_binding.v4

qualification report schema
facman.instance_isolated_candidate_qualification.v4

qualification digest
eaea8e2bbc03268f49f0fa8c077e329edae317c3757ef42a628a05da06cf1788

qualification report digest
8c85d1e5c5bdb5f643bbda7699b7bcdacd21e172934e252c469105af2e3f1324

qualification binding file SHA-256
4f3cf5a5ab0e1da72c1314f98aca4d64dbe36fe24d46a26b8358f4eaca041971
```

## Exact accepted stage

The canonical absolute stage path is:

```text
C:\Users\Jules\AppData\Local\Temp\facman-revalidation04-stage-final2\
FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-04
```

The line break is presentation only. Every later action must bind the single
complete path. Selection by parent scan, prefix, modification time, relative
path, glob, or interactive guessing is prohibited.

Inventory:

```text
file count                  16
total bytes                 63,878,999
missing files               0
unexpected files            0
reparse points              0
top-level directories       artifacts, operator, source, workspace
```

Binding identities:

```text
qualification copy
artifacts\qualification-binding.v4.json

qualification copy SHA-256
4f3cf5a5ab0e1da72c1314f98aca4d64dbe36fe24d46a26b8358f4eaca041971

historical v3 copy
absent

staged-candidate digest
060bbeaea354bc39a9601208e89b8a2fe066cdeef0ffffb2e0174514838e4249

staged-candidate file SHA-256
9f41704032df9f54edc29f42a97cbd11e40347d1d3946fc2c43a3ae2ccf9e0ec

coordinator config SHA-256
eb3e6f124b64d6a57851a1c25f02d3bc1587669eea3c8c9e8724b6cc2fa17c94

artifact manifest SHA-256
10782444335c8f9e08da51a7f88a15523f049e4c40d7cb47a9e1e689259093f1
```

Workspace bindings:

```text
instance spec digest
4cae0b49f6b3f85cf9defdfe7e0c57ff9d0ed855e9cc81a54e1cef05400bea79

staged instance binding digest
4d913849fef719234ba54036ece3830a690e51fce841b4fa1586252743b1fa62

staged readiness digest
7de1b51d2bbb40e2bc360f0076407e1d68a130bc3635e6a2840a9e8288705822
```

## Exact route and operations

```text
platform              Windows x64
Factorio              2.0.77
distribution          standalone non-Steam
launch intent         menu
isolation mode        instance_isolated

launch 1 operation
gate4c-instance-isolated-bae3edc4-8176-4677-b91d-32297a1aa5ab

launch 2 operation
gate4c-instance-isolated-29723835-2fae-4e8a-8e53-75a12878f2ac
```

The stage observed session 1 at medium integrity. Its reviewer-principal and
SID digests are:

```text
principal digest
5a6651c9c5221f226f4e4b12d35151450ff0c64732200446eb80363748af0f61

SID digest
8d7de340764c8e4e40499835f54b1f357fbc3837e032fa38339d636c8f8504fd
```

This is not an operator designation.

## Diagnostic stage preserved but not admitted

An earlier outer capture timed out while its Windows child continued to run.
The child eventually created a complete-looking 16-file directory, but the
end-to-end coordinator result stream was not captured. It is preserved only
as diagnostic material at:

```text
C:\Users\Jules\AppData\Local\Temp\facman-revalidation04-stage-final\
FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-04
```

Its operation IDs are not reused:

```text
gate4c-instance-isolated-8fd23c7e-e358-481c-9e29-1b3283c931f8
gate4c-instance-isolated-cd2eb04e-43e5-4abe-83c6-c230f6cb95eb
```

No file from that root is admitted to the accepted stage. The accepted
`stage-final2` run used new operation IDs, captured exit code zero and the
complete result object, and passed the frozen configuration reload.

## Next authority boundary

The next sequence is:

```text
explicit operator designation for revalidation-04
→ protected-resource coexistence declaration
→ fresh volatile checks
→ separately authorized elevated observer self-test
→ exact closed three-claim attestation
→ separate exact prepare authorization
→ execution-state lease
→ prepare
```

None of those actions is authorized by this checkpoint. Qualification-05,
revalidation-04, and every historical chain must remain immutable. Only after
two independently evidenced launches may a human record exactly `Pass`,
`Fail`, or `Inconclusive`; a later `Pass` does not itself promote a route.
