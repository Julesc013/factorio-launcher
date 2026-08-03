# FacMan Windows instance-isolated Play revalidation 04 — superseded before observer self-test

Date: 3 August 2026

WorkUnit:
`FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-04`

State: `superseded_before_observer_self_test`

## Disposition

Jules explicitly suspended revalidation-04 and directed that its accepted
external stage be preserved as superseded-before-observer. The mutable queue
record is archived with result `PENDING`.

This is not a candidate failure, not an evidence-attempt result, and not a
human `Pass`, `Fail`, or `Inconclusive` verdict.

```text
candidate qualification        accepted and unchanged
stage closure                  exact
last admission                 blocked_by_pending_file_rename
observer self-test             not started
observer capture               not started
WPR                            idle
prepare                        false
baseline                       false
permit                         false
Factorio execution             false
human verdict                  unset
route authority                false
authority promotion            false
```

## Preserved stage binding

The accepted stage remains at its exact external path:

```text
C:\Users\Jules\AppData\Local\Temp\facman-revalidation04-stage-final2\
FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-04
```

The line break is presentation only.

```text
files                         16
bytes                         63,878,999
missing                       0
unexpected                    0
reparse points                0
qualification binding SHA    4f3cf5a5ab0e1da72c1314f98aca4d64dbe36fe24d46a26b8358f4eaca041971
staged-candidate SHA-256      9f41704032df9f54edc29f42a97cbd11e40347d1d3946fc2c43a3ae2ccf9e0ec
coordinator config SHA-256    eb3e6f124b64d6a57851a1c25f02d3bc1587669eea3c8c9e8724b6cc2fa17c94
artifact manifest SHA-256     10782444335c8f9e08da51a7f88a15523f049e4c40d7cb47a9e1e689259093f1
qualification digest         eaea8e2bbc03268f49f0fa8c077e329edae317c3757ef42a628a05da06cf1788
staged-candidate digest       060bbeaea354bc39a9601208e89b8a2fe066cdeef0ffffb2e0174514838e4249
```

The repository operation did not rename, move, edit, prepare, or execute the
external stage. Its retained bytes are historical evidence only.

## Admission record

The last read-only admission refused progression because pending rename
operations remained queued for Windows Amcache and Microsoft Edge Update
locations. The check was not weakened or bypassed. No registry value was
cleared and no queued filesystem operation was applied manually.

## Authority and programme boundary

The archived record grants no observer, `prepare`, permit, execution, verdict,
route, signing, or publication authority. Resuming the retained stage as an
active revalidation-04 attempt is prohibited.

No successor revalidation WorkUnit and no multi-repository convergence
WorkUnit is activated here. The programme stands by for further owner detail;
the existing Windows release-candidate and preview runtime/package lanes are
unchanged.
