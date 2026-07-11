# Remaining Risks

- The package claim must stay scoped to the exact Linux runner, architecture,
  libc/toolchain baseline, sibling revisions, and inspected dependency set.
- Project-static linkage does not imply a completely statically linked Linux
  executable; system dynamic dependencies must be named honestly.
- A Windows host can validate profile/schema logic but cannot supply the
  authoritative ELF, libc, RPATH, or Linux runtime proof.
- `run.execute`, real Factorio isolation, Safe beta, setup mutation, signing,
  release, and publication remain outside this WorkUnit.
