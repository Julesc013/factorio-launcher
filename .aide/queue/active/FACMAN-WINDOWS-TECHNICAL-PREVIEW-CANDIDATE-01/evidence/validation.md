# Validation

## Accepted source

- PR #174 exact head `cbba55662f496603daa329f06117b06918dd8a23`
  passed its clean-clone qualification and merged to protected `dev` as
  `39cf8341d92524cd3a0b7dafbb626bd41514e79e`.
- The merge tree is `b79efe195878dab46235c012f3112b3728ec319c`
  and is byte-identical to the accepted task tree.
- Protected-dev CI, code security, schema, policy, and synthetic provider TCK
  completed successfully.
- PR #176 merged the ancestry-only `main` synchronization to protected `dev` as
  `049091b71c64774dee32a5c43b8e22430f587284`; both parents, `main` ancestry,
  and the unchanged `b79efe195878dab46235c012f3112b3728ec319c` tree were
  verified. The candidate then merged that protected ancestry without changing
  its qualified content tree.

## Integrated candidate validation

- Session lifecycle focused native presentation and TUI tests pass; focused
  WinForms/TUI Python contracts pass with expected platform skips.
- Release archive, staging, compiler, assurance, structure, and resolution
  tests pass, including deterministic ZIP/TAR.GZ, no-clobber, substitution,
  stale-sidecar, and unsupported-target negative controls.
- The 2.1.14 route packet validator and its negative controls pass without using
  a private Factorio artifact or widening execution authority.
- CI trigger/concurrency proof and workflow validators pass; required protected
  and pull-request contexts remain emitted while task-branch push duplication
  is removed.
- The combined locked Python selection reports 74 passes and one expected
  Windows symlink-privilege skip. All 358 schemas validate.
- Exact clean ULK `5479939ca5cbc9ee0f901608a92012778b4752ae` and USK
  `d2a2aae7e61c47035c92334b0522143b4fea3880` provider clones satisfy the
  architecture-fitness and dependency-revision gates.
- The first enclosing strict run passed every implementation, provider,
  package, schema, security, and route gate. Its only failures were source
  formatting and source-closure bookkeeping that still assumed the
  pre-candidate queue/main state; the exact failed gates and 40 enclosing tests
  pass after the bounded truth repair.

The enclosing strict gate passes on exact integrated head
`f4cb2e58175295c5e2a90cf5bbb00651cc5ae640`, tree
`3d8e6aebb4d71082c0a2b01ec51e82441bc69e34`. The ancestry-only merge at
`643debc2589ff86fab3c4748418bb8cb17e53f79` preserves that exact tree. No pass
is claimed for all 29 rows, a native candidate build, a real Factorio route, or
a human accessibility verdict.

The first hosted PR #177 Linux and Windows native jobs exposed only three stale
revision constants: the tests still named pre-promotion `main` and pre-sync
`dev`. The constants now bind `main` at `22d54a6c6a844f93db2d86dabcc35284bb074986`
and reviewed `dev` at `049091b71c64774dee32a5c43b8e22430f587284`.
Both exact failed modules and strict validation pass locally. The enclosing
promotion suite reaches 1,126 tests locally and stops only because this
qualification worktree has no `build/native-smoke/Debug/facman.exe`; the hosted
job constructs that required binary before running the same suite.

The onboarding inspection follow-up passes both focused native/TUI tests,
WinForms compilation with zero warnings or errors, 22 focused Python and
cross-frontend tests, AIDE Lite, and diff checks. Canonical v2 CLI verification
passes intact-stage and one-byte-drift controls; its enclosing release/backend
selection reports 38 passes and one expected symlink-privilege skip.

Three exact `b8f6901c` source roots built through the stable `Q:` topology are
byte-identical: `facman.exe` `3c16149265b260c84cab52c0855c1d7f56211b35f7a1701a2d38892e171ebdbf`,
canonical ZIP `50ca2a8df4abffbddb1df87a01d932f9841fafd7bf7b5db227567c3e6a1ef720`,
SPDX `b8559d770991d71b7b03bc009743174d250df3b710b35a1835c7b66b4006369e`,
and provenance `b1e562bca84a75410f2da840c19ccb3919e3d760d271e347c32fb0656accff60`.
Every staged native verifier passed 405 files with build/package and
contract/build identity matches. This is qualification evidence for the exact
`b8f6901c` source, not yet the final frozen candidate receipt.
