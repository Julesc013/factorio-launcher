# Revalidation-04 superseded before observer self-test

## Disposition

On 2026-08-03 Jules explicitly suspended revalidation-04 and directed that
the accepted external stage be preserved as `superseded-before-observer`.
This is an owner-directed lifecycle disposition, not a candidate failure and
not a human `Fail` or `Inconclusive` Play verdict.

```text
candidate qualification        accepted and unchanged
stage closure                  exact
operator designation           accepted for revalidation-04 only
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

The last read-only admission stopped on pre-existing pending rename
operations affecting Windows Amcache and Microsoft Edge Update locations.
No registry value was cleared, no queued operation was applied manually, and
no authority-bearing phase began.

## Preserved accepted stage

The stage remains outside the repository and was not renamed, moved, edited,
repaired, prepared, or executed as part of this suspension.

```text
root
C:\Users\Jules\AppData\Local\Temp\facman-revalidation04-stage-final2\FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-04

files                         16
bytes                         63,878,999
reparse points                0
qualification binding SHA    4f3cf5a5ab0e1da72c1314f98aca4d64dbe36fe24d46a26b8358f4eaca041971
staged-candidate SHA-256      9f41704032df9f54edc29f42a97cbd11e40347d1d3946fc2c43a3ae2ccf9e0ec
coordinator config SHA-256    eb3e6f124b64d6a57851a1c25f02d3bc1587669eea3c8c9e8724b6cc2fa17c94
artifact manifest SHA-256     10782444335c8f9e08da51a7f88a15523f049e4c40d7cb47a9e1e689259093f1
qualification digest         eaea8e2bbc03268f49f0fa8c077e329edae317c3757ef42a628a05da06cf1788
staged-candidate digest       060bbeaea354bc39a9601208e89b8a2fe066cdeef0ffffb2e0174514838e4249
```

The retained bytes are historical evidence only. They grant no observer,
prepare, permit, execution, verdict, route, signing, or publication authority
and must not be resumed as an active revalidation-04 stage.

## Programme boundary

No successor revalidation WorkUnit and no multi-repository convergence
WorkUnit is activated by this disposition. The existing Windows release
candidate and preview runtime/package WorkUnits remain the only active
implementation lanes while the programme stands by for further owner detail.
