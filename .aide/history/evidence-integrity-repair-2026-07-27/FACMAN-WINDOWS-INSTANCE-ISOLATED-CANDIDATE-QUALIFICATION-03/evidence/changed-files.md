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

## Qualification-to-revalidation handoff

- `tools/play_staged_candidate.py`
  - owns the closed final-workspace staged-candidate record;
  - binds the immutable qualification, exact workspace, root-independent
    Instance spec, path-bound Instance binding/readiness, complete projection
    digests, and false authority fields.
- `tools/instance_isolated_verdict_coordinator.py`
  - validates operation identities before expensive work;
  - accepts relocation only while deriving the final path-bound identities;
  - writes and reloads the exact staged-candidate binding;
  - requires `prepare` and human-record commands to consume the closed v2
    coordinator configuration.
- `tools/gate4c_verdict_preflight.py`
  - reproduces the staged workspace identity instead of comparing it to a
    different qualification root;
  - includes the staged-candidate digest in preflight closure.
- `tests/test_instance_isolated_verdict_coordinator.py`
  - covers relocation, exact rebinding, binding tamper, operation identity,
    closed configuration, and stage output.
- `docs/architecture/instance-isolated-verdict-harness.md`
  - documents the two-stage qualification/final-workspace identity chain.

## Scope exclusions

- Historical checkpoints, policy baselines, accepted policy digests, prior
  evidence packets, provider histories, and verdict records are unchanged.
- No product runtime, capability, route authority, permit, observer, Factorio
  process, Setup mutation, signing, or publication change is included.

## Final evidence and state handoff

- FacMan PR #92 published and merged the staged-candidate handoff repair after
  the exact-head security-policy, code-security, and complete six-job hosted
  CI matrix passed.
- A fifth empty-clone reconstruction produced the final remote-source-closure
  report for FacMan `2c393acf838dd432d37f8acce50d01f91bfd28ca`.
- A new qualification root produced and reloaded the immutable v2
  qualification binding.
- A new revalidation-02 root ran coordinator `stage` only and produced:
  - the exact qualified artifact copy;
  - a closed staged-candidate binding for the final workspace;
  - coordinator configuration v2;
  - no prepared launch or evidence session.
- Canonical project state and AIDE queue truth advance from candidate
  qualification to revalidation-02 `staged_not_prepared`.
