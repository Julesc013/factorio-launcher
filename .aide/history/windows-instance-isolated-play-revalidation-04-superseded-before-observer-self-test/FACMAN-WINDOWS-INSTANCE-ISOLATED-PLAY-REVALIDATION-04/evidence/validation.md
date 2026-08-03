# Revalidation-04 stage validation

## Accepted qualification

```text
FacMan source                 8f495d63b412a3af5a22305d9d8b424efd4303d2
Universal Launcher           7fc25340623131ba86c08dca4fb8a43b18a4520d
Universal Setup              3048128963dc718a7c38c1cfcdda9e813a23b0db
qualification digest         eaea8e2bbc03268f49f0fa8c077e329edae317c3757ef42a628a05da06cf1788
qualification binding SHA    4f3cf5a5ab0e1da72c1314f98aca4d64dbe36fe24d46a26b8358f4eaca041971
```

## Accepted stage

```text
root
C:\Users\Jules\AppData\Local\Temp\facman-revalidation04-stage-final2\FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-04

files                         16
bytes                         63,878,999
missing                       0
unexpected                    0
reparse points                0
staged-candidate digest       060bbeaea354bc39a9601208e89b8a2fe066cdeef0ffffb2e0174514838e4249
staged-candidate SHA-256      9f41704032df9f54edc29f42a97cbd11e40347d1d3946fc2c43a3ae2ccf9e0ec
artifact manifest SHA-256     10782444335c8f9e08da51a7f88a15523f049e4c40d7cb47a9e1e689259093f1
config SHA-256                eb3e6f124b64d6a57851a1c25f02d3bc1587669eea3c8c9e8724b6cc2fa17c94
frozen config reload          PASS
protected process inventory   empty after stage
```

The diagnostic `stage-final` root lost the outer result stream and is not
admitted. The accepted `stage-final2` run captured exit code zero and the
complete coordinator result with fresh operation IDs.

## Authority boundary

```text
operator              Jules
designation           accepted for revalidation-04 only
observer self-test    not started
WPR/ETW               not started
prepare               false
baseline              false
permit                false
Factorio execution    false
human verdict         unset
route authority       false
```

The designation authorizes recording Jules's operator identity and fresh
non-mutating volatile prechecks only. It does not authorize observer
acquisition, WPR/ETW capture, `prepare`, baseline capture, permit issuance,
Factorio execution, a human verdict, or route promotion.

## Repository closeout validation

```text
canonical project truth       PASS
canonical plan views          PASS
focused regression tests      PASS 72
full Python tests             PASS 580
Python test skips             315 optional/unsupported
schema validation             PASS 306
AIDE Lite portable suite      PASS
strict validation             PASS
provider pins                 exact qualification-05 clones
native build root             exact qualification-05 build
```

The first full Python invocation omitted the external provider and native
build-root bindings. It stopped with runner-precondition failures for missing
sibling repositories and `facman.exe`; no product or evidence failure was
reported. The accepted rerun explicitly bound the exact qualification-05
provider clones and native build and passed all 580 tests.
