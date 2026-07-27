# Changed files

## Universal Setup provider

- Universal Setup PR #18 added strict bounded single-disk ZIP64 archive
  inspection, 64-bit entry sizes and offsets, sentinel-required ZIP64 extra
  parsing, malformed/multi-disk refusals, a finite ten-minute hard ceiling,
  native tests, contract tests, and synchronized documentation.

## FacMan provider synchronization

- Current workspace and release dependency locks plus the component SBOM now
  pin Universal Setup `3048128963dc718a7c38c1cfcdda9e813a23b0db`.
- Dependency-lock validators, compliance checks, and routing tests expect the
  same exact pin.
- Stable evidence archive operations default to the provider's finite
  ten-minute ceiling, with a wrapper argument/timeout regression test.
- Historical M2-WU9 and M2-WU10 validators retain their exact accepted Setup
  revision without requiring the current workspace lock to remain frozen
  forever.
- Canonical qualification state records the superseded attempt and mandatory
  remote-only restart.

## Scope exclusions

- Historical checkpoints, policy baselines, accepted policy digests, prior
  evidence packets, provider histories, and verdict records are unchanged.
- No product runtime, capability, route authority, permit, observer, Factorio
  process, Setup mutation, signing, or publication change is included.
