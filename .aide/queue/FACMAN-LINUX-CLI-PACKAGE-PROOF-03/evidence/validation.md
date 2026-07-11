# Validation

Result: LOCAL GATES PASS; TARGET LINUX PACKAGE PROOF PENDING EXACT-SHA CI.

## Local proof

- Full native Windows build: PASS.
- Native CTest: PASS (9/9).
- Complete Python suite: PASS (220/220, zero skips).
- Strict checks: PASS (23 commands, 61 schemas, 89 refusal codes, 27 refusal
  goldens, 7 release profiles, 7 package skeletons).
- Linux proof contract/static tests: PASS (3/3).
- AIDE Lite portable validation: PASS.
- AIDE changed-file verification: PASS (37/37 in scope at review time).
- Source format and `git diff --check`: PASS.

## Target gate

The Linux proof driver deliberately refuses this Windows host. The exact
implementation revision must pass `linux-native` on the declared Ubuntu 24.04
x64 runner before ELF, glibc, dependency, tarball extraction, relocation,
read-only-root, or Linux runtime claims are promoted. The target run must have
zero required skips and emit a schema-valid evidence document plus the exact
artifact SHA-256.

Exact revision `1b5ec68468c6ea09ef6d615ae8819b38e641d3af` reached every
Linux baseline gate, including native tests, the sanitizer archive corpus and
fuzz proof, Python, strict checks, and compatibility packages, but failed the
new package-proof step in run `29156193096`. The mutation fixture named a
documentation file excluded by the intentionally minimal Linux payload. The
repair targets the packaged `docs/release/PACKAGE_LAYOUT.md`; it does not
weaken or skip the modified-payload refusal.

Replacement revision `daf14a16eff6b665018df5eede3de0f3bf6c65a4` again passed
every Linux baseline gate before failing the new package proof in run
`29156309202`. A source audit found that the CLI compatibility mapping used to
construct the Universal Setup verification request did not yet recognize the
new Linux profile. The repair adds that exact profile/target/linkage mapping;
Universal Setup remains the verification authority.

Revision `3f3e4264f3a2bdb515b4c79add85be6546ce7260` passed the same
baseline and reached the relocated/external-workspace smoke in run
`29156444395`. The test placed its declared external workspace under the
package-parent path while separately requiring that path never appear in
command output. The repair uses a distinct temporary root, preserving both
the external-workspace assertion and the package/source path-leak refusal.

## Authority boundary

The package remains unsigned and unpublished. This WorkUnit does not execute
Factorio and does not enable `run.execute`, real Factorio isolation, Safe beta,
setup mutation, networking, credentials, dynamic plugins, signing, tagging,
release creation, or publication.
