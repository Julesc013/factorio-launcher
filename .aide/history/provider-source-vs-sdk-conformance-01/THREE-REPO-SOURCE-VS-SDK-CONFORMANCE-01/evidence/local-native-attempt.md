# Local canonical-provider conformance attempt

Date: 2026-08-05

Classification: diagnostic environment evidence; not a canonical conformance
pass and not provider-adoption authority.

## Inputs

- FacMan branch: `task/facman-provider-convergence-01`
- FacMan pre-attempt committed head: `6d049881ac2ae2fbe4010ea784ede458c7554383`
- Universal Launcher: `1cafe4054297cc11e02458b83d230db0cd064471`
- Universal Launcher tree: `47018102de4b9fd20af9f77acd4e1e35e51590f3`
- Universal Setup: `32488fc13bd2439f9f6e52e83a97f6da345a7650`
- Universal Setup tree: `12fe757b1fc2ae78768a8cf912d03835f46ca65b`
- Generator: Ninja
- C compiler: GCC 15.2.0
- C++ compiler: G++ 15.2.0
- Configuration: Release

Both provider inputs were clean local clones of the exact canonical `main`
commits, with exact HTTPS `origin` URLs and matching `origin/main` refs.

## Result

`FAIL — execution environment`

The harness completed its initial exact Git/remote/ref/tree custody checks and
then entered Universal Launcher's existing full SDK self-conformance runner.
CMake identified GCC successfully, but Ninja could not start
`C:\Windows\system32\cmd.exe` for the compiler/linker probe. Windows returned
`The requested operation requires elevation`.

This reproduces the already-known managed-host native child-process denial. It
does not identify a provider, FacMan, CMake-interface, or conformance-harness
defect. The exact full matrix remains assigned to the Linux and Windows hosted
workflow.

## Raw diagnostic identities

- Failure observation: 718 bytes,
  SHA-256 `aea6710af04c25e8d86fd0ee7dc5148de6358fcd5d68dc0ca788f564210fa24c`
- Failing provider self-conformance log: 3,488 bytes,
  SHA-256 `42ebf5cce3e2e91dd680995311b4a7e31ff97701f2c5fa97e49eeb3b43ad240d`

The raw files remain diagnostic, host-specific evidence outside the source
tree. This normalized record contains no credential, developer secret,
Factorio execution evidence, Setup mutation, permit, signature, publication,
or route authority.
