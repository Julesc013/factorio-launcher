# Threat Model

This threat model defines the safety boundary for FacMan's pre-beta proof
gates. It covers local inputs and honest operator mistakes as well as
deliberately hostile workspace content.

## Trust Zones

| Zone | Default trust |
| --- | --- |
| Source tree and reviewed build inputs | trusted for development |
| Built unsigned package | integrity-checkable, not publisher-authenticated |
| Workspace files and imported manifests | untrusted |
| Imported paths, archives, identifiers, and filenames | untrusted |
| Steam or other foreign-owned Factorio installs | readable, never setup-mutable |
| Operator-supplied Factorio executable | executable only after explicit approval and preflight |
| Diagnostic source files | sensitive and potentially hostile |
| Universal Setup authority | unavailable to the normal launcher process |
| Network and credential providers | unavailable until separately enabled |

## Protected Assets

- files outside the selected FacMan workspace
- foreign-owned installs and Steam-managed state
- saves, mods, instance state, and existing exports
- credentials, tokens, cookies, and account material
- package output directories and build inputs
- audit and integrity records

## Threats and Failure Modes

- path traversal through identifiers, absolute paths, drive prefixes, UNC
  paths, dot segments, links, junctions, or reparse points
- silent overwrite or merge of persistent state
- deletion of an output tree FacMan did not create
- time-of-check/time-of-use path substitution
- malformed or oversized JSON, INI, archive, or diagnostic input
- partial writes, interruption, stale locks, and incomplete transactions
- secret disclosure through multiline or unfamiliar structured formats
- resource exhaustion through deep, numerous, or oversized files
- false success, contract drift, or a package claiming unused components

## Enforced Principles

1. Raw identifiers never become filesystem paths directly.
2. Managed writes prove containment at the point of use.
3. Persistent creation is no-clobber unless replacement is explicit.
4. Recursive cleanup requires a recognized ownership marker.
5. Unproven dangerous capabilities refuse instead of approximating success.
6. Read-only commands receive no write-capable workspace initialization.
7. Unsigned hashes establish consistency only, not publisher authenticity.

Handle-relative operations should be preferred for security-sensitive writes
where the platform permits them. Lexical checks alone are not sufficient for
an existing tree containing links or reparse points.
