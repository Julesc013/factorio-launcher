# Validation

Result: PASS, including exact-SHA zero-skip Linux target proof.

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

Final revision `93edfdc59865e4a07f261bdabb61c6e2db6d0f99` passed CI run
`29156543059`: Linux native CTest 9/9, sanitizer archive proof, complete Python
221/221, strict checks, portable compatibility packages, and the new Linux
target proof with zero required skips. Windows native/package, macOS archive,
and AppKit compile-only jobs also passed. Security run `29156543070` passed;
schema run `29156192783` passed the unchanged 61-schema/package surface at the
implementation revision.

The Linux artifact is
`facman-0.1.0-dev.contract-linux-cli-x64-portable.tar.gz`, 798340 bytes, SHA-256
`b69ce3b9a4cda455e79f354c85873f0e17af281e26057c2537a511d49ab1cbed`.
It is unsigned, unpublished, and scoped only to the recorded Ubuntu 24.04 x64
runner, glibc 2.39, GCC 13.3, Binutils 2.42, and inspected dependencies.

## Authority boundary

The package remains unsigned and unpublished. This WorkUnit does not execute
Factorio and does not enable `run.execute`, real Factorio isolation, Safe beta,
setup mutation, networking, credentials, dynamic plugins, signing, tagging,
release creation, or publication.
