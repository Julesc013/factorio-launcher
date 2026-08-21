# Release-resolution security review plan

Status: prepared; independent review not yet performed

WorkUnit: `FACMAN-RELEASE-RESOLUTION-SECURITY-REVIEW-01`

The release compiler is security-sensitive because it converts reviewed
product policy and observed source custody into package-stage truth. Local
functional validation is necessary but is not an independent adversarial
review. Release-candidate use remains blocked until a reviewer separate from
the implementation closes this plan against a clean, exact-head,
release-eligible candidate.

## Review matrix

| Surface | Required adversarial evidence |
| --- | --- |
| Canonical JSON and hashing | Cross-implementation vectors, Unicode and numeric edge cases, stable object ordering, explicit domain separation, and proof that the aggregate root is acyclic |
| Parsers and schemas | Depth, size, recursion, large integer, duplicate identity, unknown-field, malformed UTF-8, and resource-budget controls |
| Portable paths | Reserved Windows names, trailing dots/spaces, case folding, Unicode normalization and confusables, drive/UNC/device paths, traversal, prefix overlap, and platform separator variants |
| Filesystem custody | No-follow behavior, symlink/reparse/junction and hard-link substitution, stable identity across reads and copies, TOCTOU races, ownership, permissions, atomic publication, disk-full and interruption behavior |
| ZIP/TAR inspection | Duplicate and colliding entries, links and devices, encrypted ZIPs, data descriptors, ZIP64/PAX/GNU variants, sparse files, expansion and ratio bombs, malformed headers, trailing data, and archive replacement |
| Evidence and substitution | Path leakage, stale observations, wrong repository/remotes, dirty provider trees, observation replay, provider/package substitution, metadata/full-evidence confusion, and digest-domain confusion |
| Authority | No widening from adapter or package metadata; Setup mutation, execution, credential, network, signing, publication, support, and route authority remain false unless separately granted |

## Property and fuzz targets

The review must add bounded property tests and fuzz harnesses for canonical
serialization, source-observation normalization, dependency closure, path
normalization/ownership, resolution reload validation, stage construction and
verification, and directory/ZIP/TAR inspection. Each harness must enforce
input, time, memory, output-size, entry-count, and expansion budgets; retain a
minimized regression corpus; and demonstrate deterministic refusal rather than
crash, hang, partial publication, or authority widening.

## Exit criteria

The WorkUnit may close only when all high-severity findings are repaired,
remaining risks have named owners and explicit acceptance, the exact reviewed
source/root/toolchain identities are recorded, all unrestricted native lanes
pass, and the canonical plan records the independent verdict. Preparation of
this document is not that verdict.
