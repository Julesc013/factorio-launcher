# Validation

Result: local PASS; exact-SHA cross-platform CI pending.

## Behavior proven locally

- `mods.import`, `modsets.lock`, `modsets.verify`, and `modsets.export` are
  canonical registered commands routed through ULK, FLB, and typed Factorio
  application operations.
- The CLI only normalizes aliases and renders the shared typed result for these
  commands.
- Deflated `info.json` metadata is streamed through the production archive
  core before import copies any bytes.
- Import verifies source stability, staged content, metadata, and SHA-256, then
  performs an owned no-clobber commit without changing the source archive.
- Lock and verify reject missing, hash-drifted, metadata-drifted, duplicate,
  incompatible, malformed, unsafe, and over-budget archives.
- Export uses the production deflate writer, deterministic entry order,
  self-verification, and owned no-clobber commit.
- Valid-shaped dry-run write requests refuse without mutation; verify remains
  read-only.
- Command graph metadata, effects, schemas, availability, owner, dispatch, JSON
  output, and human rendering agree.

## Local gates

- Full native build: PASS.
- Native CTest: PASS (9/9).
- Complete Python suite: PASS (199/199).
- Strict checks: PASS (17 commands, 54 schemas, 76 refusal codes, 20 command
  goldens).
- AIDE Lite test: PASS.
- `git diff --check`: PASS.

## Authority boundary

No Mod Portal networking, remote resolution, credential handling, save or
instance transfer, transaction recovery, diagnostic export, `run.execute`, Safe
beta, setup mutation, signing, tagging, release, or publication capability is
promoted by this WorkUnit.
