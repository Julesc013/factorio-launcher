# Archive stable lifetime

Status: implemented locally for R3.4 WorkUnit 5.

## Object lifetime and trust boundary

`inspect_archive` opens the untrusted archive once and stores that exact object
in the returned `Plan`. The retained platform handle and its captured identity
outlive metadata planning. `verify_entry`, `verify_all`, `stream_entry`, and
`extract_to_new_owned_staging` operate through that handle; none of them reopen
`Plan::archive_path`. Every Miniz reader initialization revalidates the retained
object before use.

The API intentionally separates these operations:

1. `inspect_archive` parses and policy-checks metadata without decompressing
   payloads.
2. `verify_entry` decompresses and validates one selected entry.
3. `verify_all` decompresses and validates the complete content set.
4. `stream_entry` verifies while delivering one entry to a bounded sink.
5. extraction verifies each entry once while writing durable exclusive files.

The archive pathname remains diagnostic metadata. Replacing it after inspection
cannot redirect a plan. The native smoke test renames the inspected archive,
creates different bytes at the old path, and proves streaming still returns the
original payload.

## Writer lifetime and durability

The writer opens every regular source during validation and retains those stable
handles until archive finalization. Size and identity are checked before and
after compression. A source-path replacement checkpoint proves that changing
the pathname after validation does not silently change the archived content.

Output is created exclusively inside an owned staging root, receives an
OS-level file flush, and flushes the containing directory where the platform
supports it. Publication uses the archive platform's exact no-clobber commit;
failure cleanup only removes an identity-matching owned object.

## Explicit consumer policies

| Policy | Archive bytes | Entries | Total expanded bytes | Read budget |
| --- | ---: | ---: | ---: | ---: |
| `ModArchivePolicy` | 2 GiB | 4,096 | 4 GiB | 30 s |
| `SaveArchivePolicy` | 4 GiB | 2,048 | 8 GiB | 30 s |
| `InstanceTransferPolicy` | 4 GiB | 20,000 | 12 GiB | 120 s |
| `DiagnosticBundlePolicy` | 32 MiB | 512 | 24 MiB | 10 s |
| `PackageArchivePolicy` | 4 GiB | 100,000 | 8 GiB | 120 s |

Mods, saves, instance transfer, diagnostics, and package-like modset exports
select named policies at their call sites. The generic `Limits` default remains
only as a compatibility surface for low-level probes and tests.

## Performance boundary

R3.3 did not preserve a comparable archive microbenchmark, so this change does
not invent a percentage improvement. Its operation count is strictly clearer:
metadata inspection performs zero payload decompressions; selected reads perform
one; extraction performs one per file; writer self-verification performs one
complete pass. The Windows Release native smoke covers stored, deflate, forced
ZIP64, replacement, corruption, and extraction in one run. A later benchmark
gate may pin distributions without changing this lifetime contract.

## Proof and remaining platform work

The WorkUnit proof consists of the native lifetime/corruption smoke, the Python
malicious and generated archive corpus, both deterministic mutation harnesses,
the archive architecture checker, full native CTest, and the strict repository
gate. Windows Release evidence is local. ASan/UBSan evidence remains a separate
Linux/macOS validation item and must not be inferred from the Windows run.
