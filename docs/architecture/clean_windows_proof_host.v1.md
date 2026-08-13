# Clean Windows proof host v1

This specification defines the resettable Windows x64 host required before a
separately authorized real-Play qualification. It provisions no host, reads no
private archive, executes no Factorio process, and grants no release authority.

## Isolation and identity

Use a dedicated VM or physically dedicated host whose system disk can be
restored to one read-only golden snapshot. A run identity binds:

- golden-image digest and snapshot identifier;
- Windows edition, build, servicing level, locale, time zone, and boot ID;
- firmware, Secure Boot, TPM, CPU, memory, system-disk, and hypervisor profile;
- exact repository commits, source trees, toolchain/SDK versions, dependency
  pins, candidate package digest, route ID, policy ID, and test-plan digest;
- operator authorization reference and monotonically unique run ID.

The proof account is non-administrator. Administrator bootstrap is a separate,
audited phase that ends before candidate or private input is attached. Developer
profiles, package caches, Git credentials, signing keys, production credentials,
game state, Steam state, and previous run state are absent from the sealed image.

## Lifecycle

```text
golden snapshot verified
→ isolated clone created
→ public toolchain/source inputs reconstructed and digested
→ network disabled and bootstrap credentials removed
→ candidate installed as non-administrator
→ approved private input attached read-only
→ preflight and negative controls
→ separately authorized route execution
→ bounded evidence collection and redaction
→ digest-only evidence export
→ private input detached
→ clone destroyed
→ golden snapshot reverified
```

Every transition is fail-closed and journalled outside the guest. Reusing a
guest after an incomplete run is forbidden. Reset means discarding the clone,
not deleting selected files in place.

## Inputs and network

Public source and toolchain acquisition may use an allowlisted bootstrap
network before the run is sealed. The execution epoch is network-denied unless
the immutable route explicitly requires and authorizes a named endpoint.

Private Factorio material is injected only after owner approval through a
read-only virtual disk or equivalent immutable mount. The orchestrator records
the approved archive digest and mount identity but neither exports the archive
nor places it in a build cache. The candidate receives only the path declared
by the route. Version substitution, archive mutation, Setup mutation, Steam
mutation, and ambient installation discovery are forbidden.

## Observation and negative controls

Before execution, prove that the observer can distinguish the target process,
process tree, executable identity, command line, working directory, configured
write roots, timeout, and terminal outcome. Required negative controls include:

- wrong archive digest, executable signer, product version, route ID, package
  digest, provider pin, and policy digest;
- writable or reparse-point private input;
- administrator launch, unexpected pre-existing Factorio/Steam process, stale
  workspace state, unexpected network reachability, and foreign write target;
- observer unavailable, evidence sink unavailable, clock discontinuity, guest
  restart, timeout, and ambiguous process outcome.

Each negative control must refuse before Factorio effects or classify the run
inconclusive. It must never be converted into a pass by absence of evidence.

## Evidence boundary

Evidence leaves the guest through a one-way, size-bounded export after redaction.
The export contains schemas, identities, timestamps, normalized outcomes,
observer facts, test results, and SHA-256 digests. It excludes private archive
bytes, executable bytes, saves, credentials, tokens, user paths, crash dumps,
raw memory, and unbounded stdout/stderr. A manifest binds every exported file;
an independently computed host digest verifies the bundle after transfer.

The proof host never has signing or publication credentials. A successful run
qualifies only the exact route/package/provider tuple named by its authorization;
it does not authorize another Factorio version, package, platform, publication,
or support claim.

## Provisioning acceptance

The WorkUnit is implementation-ready when automation can create and discard a
clone, emit the complete host identity, prove a non-administrator empty-state
baseline, reconstruct the exact candidate, disable bootstrap access, attach a
synthetic read-only input, pass all negative controls without Factorio, export a
redacted digest-only receipt, destroy the clone, and reproduce the baseline.

Real private-input attachment and Factorio execution remain separate human
gates after this acceptance suite is green.
