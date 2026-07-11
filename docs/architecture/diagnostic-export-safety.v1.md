# Diagnostic Export Safety v1

`diagnostics.export` is a typed FacMan application operation. The CLI parses
`--instance` and `--out`, invokes the canonical Universal Launcher command ID,
and renders the typed result or refusal. It owns no traversal, redaction,
archive, or recovery policy.

## Source boundary

Collection begins from one managed instance root and four allowlisted child
roots: `config`, `logs`, `crash`, and `script-output`. Existing traversal
limits remain authoritative: no-follow, maximum depth, file count, per-file
bytes, total bytes, and elapsed time. A limit that prevents complete traversal
refuses the export; ordinary policy omissions remain explicit in
`reports/omissions.v1.json`.

Every reviewed source is reopened relative to its allowed root. Windows uses
wide-path handles, refuses reparse/multiple-link sources, checks volume and
file ID, and denies writer/delete sharing while reading. POSIX opens each path
component with `openat` and `O_NOFOLLOW`, then checks device, inode, link count,
type, size, ownership, mode, and timestamps with `fstat`. Both adapters read
under a byte limit and compare relevant handle metadata after the final byte.

The bundle records a SHA-256 pseudonym of the platform identity. Raw volume,
file ID, device, inode, workspace, install, and instance paths are not bundle
metadata.

## Format boundary

The reviewed collected formats are:

- known FacMan JSON manifests;
- `config/config.ini`;
- `config/server-settings.json`;
- `.log` and explicit `.txt` diagnostics below `logs`, `crash`, or
  `script-output`.

Unknown and archive formats are omitted, not copied. Malformed reviewed JSON
or INI refuses the whole export. Binary content under a reviewed text name,
unredacted credential-like fields, or a remaining machine-private absolute
path also refuses. Adding another format requires a named classifier and an
adversarial test; there is no arbitrary-text fallback.

## Output and recovery boundary

Only redacted bytes enter an owned payload staging directory. The production
archive writer creates deterministic deflate output in a second owned staging
directory and validates its central directory, entries, CRCs, and resource
limits before commit. Commit is no-clobber and same-volume.

The bounded workspace journal records `diagnostics.export` from `requested`
through `complete`, including source/staging identities, expected redacted
hashes, and the destination-volume commit strategy. After commit, FacMan
reopens the final ZIP through the production reader, streams the typed manifest
back, and checks its exact bytes and entry count before closing the journal.

Faults before commit leave no target. Faults after commit leave a structurally
complete target and an incomplete journal for explicit recovery inspection.
No recovery path deletes a target merely because journal finalization stopped.

## Claim limit

This proves the reviewed local diagnostic bundle path on supported local
filesystems. It does not prove arbitrary formats, shared/network filesystems,
publisher authenticity, real Factorio execution, Safe beta, setup mutation,
signing, release, or publication. Native GUI diagnostic export remains
deferred; this WorkUnit adds no GUI feature breadth.
