# Terminal/frontend foundation checkpoint

Status: locally qualified task branch; human review and hosted exact-head proof
remain required.

## Identity and scope

- WorkUnit: `FACMAN-TERMINAL-FRONTEND-FOUNDATION-01`
- branch: `task/facman-terminal-frontend-foundation-01`
- exact base: FacMan `dev@54b188c0b2d4ab62c1d948cd1c548489fbe8c8b7`
- canonical provider: ULK `main@1cafe4054297cc11e02458b83d230db0cd064471`
- observed canary provider: ULK `dev@e6de83ad1e1a2c646d31eb2ca68aa5cddb323b4a`
- Setup pin: `32488fc13bd2439f9f6e52e83a97f6da345a7650`

The tracked provider lock is unchanged. No FacMan product path consumes the ULK
dev candidate in this WorkUnit.

## Result

One required `facman` console artifact now routes bounded human CLI, normative
CLI JSON (`--json` or `--format json`), explicit `facman tui`, and the bounded
`facman --rpc` stdio alias. The TUI host is a callable library linked into the
CLI. The old `facman-tui` executable is off by default, opt-in compatibility
only, and prohibited from product packages.

`FrontendSession` supplies normalized direct/process/service transport identity,
request/operation/attempt correlation, cancellation, progress, timeout,
backend/provider negotiation, immutable snapshot revision, and redacted
correlation evidence. It owns no product state or terminal outcome.

`TerminalCapabilities` observes TTYs, size, TERM/dumb state, NO_COLOR, UTF-8,
VT/ConPTY, redirected streams, and safe/plain mode. The project-owned linear
renderer is mandatory. No full-screen adapter was admitted; FTXUI remains a
candidate pending exact offline, licence/SBOM, portability, accessibility,
security, compatibility, performance, and rollback qualification.

The generated Advanced command explorer remains available through
`facman tui --advanced`; ordinary product pages remain for
`FACMAN-SAME-BINARY-TUI-PARITY-01`.

## Local evidence

- MSVC 19.51, Windows SDK 10.0.26100, warnings-as-errors: full native build pass.
- CTest Debug: 36/36 pass, including frontend-session, TUI, terminal-capability,
  ABI, runtime-package, and installed-SDK smokes.
- Python discovery: 1,006 tests pass with eight intentional skips.
- focused Python terminal/package/layout suite: 24/24 pass.
- repository strict validation: pass, including 344 schemas and 127 commands.
- Windows portable TUI developer package: one `bin/facman.exe`, 453 files
  verified, arbitrary-CWD and empty-PATH smoke pass, TUI command census 122.
- package classification: dirty-source developer evidence only; unsigned,
  unpublished, unsupported, and not release eligible.

The first full Python discovery attempt exposed task-environment and truth-model
migration defects. The actionable failures were repaired; a second run proved
the code/contract corpus and identified only a misbound package-build root in
the invocation. The corrected final run passed all 1,006 discovered tests.

## Compatibility map

| Historical development invocation | Canonical invocation |
| --- | --- |
| `facman-tui --interactive` | `facman tui` |
| `facman-tui --list --json` | `facman tui --list --json` |
| `facman-tui --command ID ...` | `facman tui --command ID ...` |
| `facman rpc --stdio` | `facman --rpc` or the preserved form |
| `facman CMD --json` | unchanged; `--format json` is equivalent |

## Authority boundary and next cut

Real Factorio execution, private archives, Setup mutation, ULK repinning,
daemon/service admission, network listeners, signing, tags, releases,
publication, and support promotion remain false.

The next independent product cut is ordinary same-binary TUI parity. The next
provider cut is an exact FacMan consumer canary against ULK dev followed by the
normal human-gated ULK dev-to-main promotion. Provider adoption and Last Run
authority cutover remain blocked until that promotion is canonical.
