# Archive Runtime

`facman_archive_static` is the product-neutral production ZIP boundary used by
later FacMan data-path WorkUnits. It owns ZIP metadata agreement, entry/path
policy, resource budgets, streamed CRC-checked reads, extraction planning, and
staged reproducible writing. Factorio save, mod, instance, and diagnostic
semantics do not belong here.

The reader independently parses classic and ZIP64 end records, central and
local headers, ZIP64 extras, and data descriptors before asking the pinned
Miniz implementation to stream and CRC-check entry content. This independent
layer is intentional: Miniz supplies compression mechanisms, while FacMan owns
the fail-closed product policy and the tiny forced-ZIP64 agreement proof noted
in the dependency admission record.

Extraction creates a new marked staging directory and removes that directory
on any failure. The writer likewise creates only a new owned staging root,
streams regular source files in deterministic archive-path order, caps output
bytes while writing, finalizes the archive, and reads the result back through
the production inspector. This layer does not rename or commit an archive to a
user target; transaction and consumer WorkUnits own that later authority.

Current limitations are deliberate:

- only ZIP stored and deflate methods are accepted;
- encrypted and multi-disk archives refuse;
- source-file identity stability and final-target transaction durability are
  consumer responsibilities proven in later R3.3 WorkUnits;
- the legacy CLI and mod parsers remain until their typed-route parity gates
  pass, and the strict archive-core checker constrains their current locations.
