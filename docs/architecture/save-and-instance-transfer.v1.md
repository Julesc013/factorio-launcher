# Save and Portable Instance Transfer

The authoritative R3.3 commands are `saves.list`, `saves.backup`,
`saves.clone`, `instance.export`, and `instance.import`. The CLI owns only the
legacy spelling normalization (`export instance` and `import instance`) and
rendering. ULK receives the canonical command IDs, and FLB invokes typed
Factorio operations.

## Save truth boundary

Save inspection reports three independent facts:

- `archive_structurally_valid`: the production archive core accepted the ZIP
  structure, policy, CRCs, compression, and resource budgets;
- `factorio_save_recognized`: the archive contains a policy-safe
  `level-init.dat` entry;
- `deep_save_semantics_inspected`: always `false` in R3.3.

FacMan does not describe an arbitrary readable ZIP, or even a recognized
Factorio-shaped save, as semantically valid game state.

## Stable source reads

Backup, clone, and instance export open each source without following links,
capture file identity and relevant metadata from the open handle, require one
hard link, stream bytes from that handle into owned staging, and re-check the
same handle before accepting the snapshot. SHA-1 compatibility output and
SHA-256 authority are calculated from the exact staged bytes.

## Cross-volume strategy

Staging is always created under the destination parent. A source on another
volume is copied through its stable handle into that destination-volume
staging root, hashed, and structurally verified there. The final no-clobber
file or directory commit therefore remains within one volume and never assumes
that a cross-volume rename is atomic.

## Portable export and import

Instance export creates deterministic portable metadata, redacts the instance
and install roots, records a complete file-level SHA-256 closure, writes a
deflated archive through the production writer, and commits only the writer's
self-verified output.

Instance import validates the complete archive plan and declared hash closure
before output, extracts only into a marked owned staging directory, verifies
the staged tree, replaces portable tokens with the selected local install and
new instance root, and performs a no-clobber directory commit. Cleanup can only
target a recognized ownership marker.

An injected interruption before commit leaves no destination. An interruption
after the atomic directory commit leaves the complete destination plus its
ownership marker and returns `transaction_recovery_required`; the next R3.3
WorkUnit owns journaled inspection and recovery of that recognized state.

## Durability boundary

R3.3 save/transfer routing proves staged no-clobber visibility and source
identity, not power-loss durability across every filesystem. Journal flush,
directory flush, commit-uncertain reconciliation, and idempotent recovery are
owned by `FACMAN-WORKSPACE-TRANSACTION-RECOVERY-03`.
