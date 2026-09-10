# Resource export outcomes

Export carries a per-call monotonic extraction observation through the actual CLI response builder.
The first destination creation attempt latches possible effects before the filesystem call. A
successful export reports completed with effects_may_have_occurred=true. Read-only list, verify and
inspection report completed with false. Proven pre-effect refusals retain
refused_before_effects/false.

A failure after that latch reports recovery_required/true, preserves the original error, and
supplies resources.export.inspect with explicit destination arguments. Operation and attempt IDs are
allocated before dispatch. No transaction ID is invented. A cleanup attempt does not turn historical
effects into a pre-effect refusal. The top-level effects event array remains unchanged; operation is
the authoritative attribution field.

The implemented local route is:

    facman resources inspect-export <absolute-destination> --json

It works with no available source pack or marker. Its closed payload schema is contracts/schema/resources/export-inspection.v1.schema.json. This is a local CLI route, not a newly registered backend/RPC command.

Inspection reports destination type and numeric identity only, using component-relative no-follow
metadata operations from a held parent. It does not enumerate or hash members, inspect a marker,
verify export completeness, correlate present objects to a past operation, or grant ownership. It
never authorizes retry, delete, resume, replacement or reuse. Present, absent, unsafe and
unavailable are observations, not recovery completion. Marker/member inspection remains follow-on
work.

Admission requires an absolute path of at most 4096 UTF-8 bytes, 64 components, and 255 native code
units per component. Dot components and ambiguous Windows component spellings refuse. Windows
supports local fixed DOS-drive paths; unsupported root spellings report unavailable. Links, reparse
points and non-directory ancestors are not traversed. The synchronous local filesystem calls are
checked against a two-second observation budget between calls; this is not a hard syscall deadline.
Numeric identities and the observed ancestor chain are sequential observations, not an atomic
pathname lease.

The extraction checkpoint remains an internal C++ test seam; shipping CLI callers cannot select
faults. The product extractor retains failures. The explicit-pack legacy extractor retains its
existing cleanup behavior, including its separately unresolved pathname-based cleanup authority.
Neither implementation gains an atomic namespace lease from the phase observation.

Causal native tests cover real product and explicit-pack writes, existing/invalid-parent pre-effect
refusals, marker collision, root/stream/standard/nonstandard callback failures, digest mismatch,
legacy cleanup, returned recovery metadata through the actual ULK validator, and actual
destination/ancestor link inspection. CLI tests check serialized operation fields against newly
observed files. The predecessor recorded successes fail the new independent attribution oracle.
Compilation and native execution require separately reviewed fresh source-bound plans; no previous
receipt qualifies this correction.

The command dispatcher owns the extraction observation across the inner export and outer reporting
handlers. A failure while constructing the first error report cannot replace that observation with a
fresh pre-effect result. If reporting cannot complete, an exception may escape without a machine
envelope; absent output is not proof of no effects. Internal checkpoints test the secondary
reporting failure and are unavailable as CLI options or environment variables.

Windows component admission runs before any native observation. It refuses DOS device basenames
case-insensitively, their extensions, COM/LPT superscript aliases, and reserved console names; valid
internal spaces and Unicode remain admitted. The pure policy is shared by the Windows observer and
native causal tests.
