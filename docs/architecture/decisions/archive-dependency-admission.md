# ADR: Production Archive Dependency Admission

Status: accepted for R3.3 implementation.

Date: July 11, 2026 AEST.

## Decision

Admit Miniz `3.1.2` at commit
`77d0dce8627735138c51770d1799a1ef48f2117d` as FacMan's one new R3.3
archive dependency. Vendor the official source-only release asset and link it
as the private static target `miniz_static`.

The official release asset SHA-256 is
`f0446d863f9c19926ad9483c523fdc42e42b8d4a6a431d27e09d49c79a140d9a`.
The downloaded asset was rehashed locally and matched the digest published by
GitHub's release metadata.

## Admission Matrix

| Requirement | Evidence and FacMan responsibility |
| --- | --- |
| Stored and deflate | Miniz ZIP reader/writer supports method 0 and `MZ_DEFLATED`; compile smoke writes deflate. |
| ZIP64 | Reader exposes ZIP64 state; writer supports automatic or forced ZIP64; compile smoke forces and reads ZIP64. |
| Data descriptors | Upstream validation compares optional descriptors with central-directory metadata. |
| CRC | Streaming extraction and archive validation compute and compare CRC-32. |
| Streaming input/output | Reader extraction iterators and callbacks plus writer read/write callbacks are available. |
| Central/local agreement | `mz_zip_validate_file` validates local headers, ZIP64 extras, descriptors, sizes, and CRC against the central directory. |
| Cross-platform static linkage | Upstream supports GCC, Clang, and Visual Studio as portable C; FacMan builds a private static library. |
| Unicode filenames | Names are preserved as bytes; FacMan will require canonical UTF-8 and enforce normalization collisions. |
| Encrypted entry refusal | Miniz exposes `m_is_encrypted` and refuses unsupported encrypted extraction; FacMan policy refuses before extraction. |
| External attributes | `mz_zip_archive_file_stat.m_external_attr` exposes entry attributes for link/device refusal. |
| Resource limits | FacMan must apply stricter preflight and streaming budgets before using upstream extraction APIs. |

## Admission Finding: Forced ZIP64 Validation

The admission smoke found that Miniz 3.1.2 can write, detect, inspect, and
extract a deliberately forced tiny ZIP64 archive, but
`mz_zip_validate_file(..., MZ_ZIP_FLAG_VALIDATE_HEADERS_ONLY)` rejects that
same artificial archive. Normal stored/deflate archives pass upstream's full
local-header, central-directory, extraction, and CRC validation.

This is a recorded upstream limitation, not a waived production test. The
R3.3 archive layer must independently validate ZIP64 local/central agreement
and the malicious ZIP64 corpus before any consumer migration. Upstream
validation remains an additional check where it succeeds; it is not FacMan's
sole executable authority.

## License and Provenance

Miniz is MIT licensed. The copyright and permission notice must remain with
source and binary redistributions; the exact upstream license is vendored and
summarized in `THIRD_PARTY_NOTICES.md`. The release contains source only and
has no runtime transitive dependency.

## Rejected Alternatives

- Extending FacMan's stored-entry ZIP code would require hand-writing deflate
  and ZIP64 and is prohibited by the R3.3 authority boundary.
- libzip and minizip-ng are capable alternatives but require a separately
  supplied deflate dependency in the Windows static build, exceeding this
  WorkUnit's one-dependency boundary.
- Opaque prebuilt binaries and runtime package-manager discovery are forbidden.

## Boundaries

Admission does not declare upstream ZIP convenience APIs safe for direct use.
FacMan's production archive layer must still enforce path grammar, collision
rules, budgets, overlap checks, deterministic metadata, owned staging, and
self-verifying commit. Encryption remains unsupported and must be refused.
