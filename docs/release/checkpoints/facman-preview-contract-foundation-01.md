# FacMan Preview contract foundation checkpoint 01

Date: 12 August 2026

State: `foundation_complete_canary_stopped_package_candidate_local_only`

## Exact parentage and authority

The task branch is `task/facman-preview-contract-foundation-01`, stacked from
the exact Phase C head
`731f1d8024c2846e8cb1710ccbcc29c7efff8dfb`. Canonical `origin/dev` remained
`4da0bf2c4c1df92d8e3a4d2d7eae39ebf65cba2f` throughout construction. PRs
#133, #134, and #135 were not modified or merged.

The accepted stable provider inputs used for FacMan production builds remained:

- Universal Launcher `1cafe4054297cc11e02458b83d230db0cd064471`;
- Universal Setup `32488fc13bd2439f9f6e52e83a97f6da345a7650`.

No protected branch, route, provider lock, tag, release, signature, publication,
Factorio process, private archive, or Setup mutation was written or executed.

## Delivered foundation

### Normative CLI machine contract

Every machine-mode result now emits one top-level
`facman.transport_response.v2` object. Payload-only/list-only bypasses were
removed, invalid syntax is enveloped, stdout is reserved for the single JSON
result, diagnostics remain on stderr, and the bounded exit law is shared by
direct and RPC clients:

- `0`: success;
- `1`: product refusal, unavailable/not-found/conflict, or cancellation;
- `2`: invalid arguments;
- `3`: recovery required;
- `4`: outcome unknown;
- `5`: transport or internal failure.

Goldens, native projection tests, package consumers, and the WinForms identity
harness consume the normalized envelope.

### Bounded 1.0 projections

The milestone matrix now requires CLI JSON, bounded human CLI, WinForms,
AppKit, and GTK. Ordinary-product TUI status and Qt require separate admission;
neither was redesigned or admitted by this task.

### Callable application/presentation service

`presentation.query` and `presentation.action` expose immutable scoped
snapshots, backend revisions, typed action descriptors and blockers, expected
revisions, request/idempotency keys, and durable operation identifiers. A
narrow six-state Last Run provider seam is present. Production deliberately
uses an unavailable provider; only tests use the fixture provider. Existing
JSON/TOML workspace authority remains unchanged.

The service is registered and callable through direct, RPC, and CLI paths but
is engineering-only. WinForms, AppKit, and GTK production adapters and their
local Last Run caches were not switched.

### Windows WinForms Technical Preview target

The existing release compiler now resolves
`windows_winforms_technical_preview_x64` with WinForms, the static native CLI,
contracts, Factorio product content, licences, exact source/provider custody,
and all execution, Setup, signing, and publication authorities false.

The production native and WinForms identity boundaries recognize the v2
`manifest/stage.v1.json` layout directly. Both recompute its canonical digest,
verify the exact file closure, bind the clean implementation and accepted
provider revisions from embedded resolution records, enforce embedded-static
linkage, and refuse enabled or authorized capabilities. The WinForms boundary
also retains stable no-follow handles across dispatch and suspended-process
image binding. Legacy package recognition remains available only for existing
profiles.

This proves unsigned integrity and custody, not publisher authenticity or
support.

## Atomic canary decision

No canary branch was created. A repository-supported source override could
consume the ULK task source for engineering proof, but all three native
frontends did not coherently switch to the new service in this WorkUnit. The
production stop law therefore applied: independent foundations landed while
the current production presentation paths and frontend-local caches remained
unchanged.

Consequently, the new all-frontend fake-process journey and its full fault
matrix were not claimed complete. The pre-existing three fixture journeys (23
steps), fake-process native tests, and presentation service tests remain green;
they are foundation evidence, not atomic adapter-parity evidence.

## Route evidence

`facman-route-version-decision-dossier-01.md` retains 2.0.77 as the only
defined future execution route and 2.1.14 as archive/materialization evidence.
It records the exact missing evidence and grants no route change or execution.
The private archive was not accessed.

## Validation record

The foundation was exercised on Windows x64 with the exact stable provider
worktrees above:

- strict repository check: pass;
- Debug native CTest: 39/39 pass;
- shared-provider Debug and Release CTest: 40/40 pass in each configuration;
- WinForms Release build with warnings as errors: pass;
- WinForms command-client, transport-hardening (38 cases), backend identity,
  C1 shell, and runtime smoke checks: pass;
- AppKit/GTK source and fixture/live-shell checks: 27 pass; native runtime
  qualification remains external to Windows;
- release compiler tests: 25 pass; all four target resolutions validate;
- complete Python aggregate before the final package adapter: 996 run, zero
  failures/errors, eight explicit environment/optional skips;
- focused built-package suite after the shared WinForms build: 18 pass, one
  optional missing `ulk_shared` install-tree skip;
- v2 stage verification: 386 entries, pass;
- packaged native `product.inspect`: verified, build/package and contract-set
  identities match;
- production WinForms package harness: exact handshake, full namespace lease,
  suspended native image, hardlink, junction, and substitution refusal pass;
- Unicode relocation with an empty `PATH` and arbitrary working directory:
  pass;
- two independently written deterministic ZIP projections: byte-identical;
- archive inspection and exact resolution verification: pass.

The eight aggregate skips were one optional install-tree component, one
not-yet-built shared WinForms artifact (subsequently closed by the focused
suite), five Windows symlink/reparse privilege cases, and one opt-in R37
performance run. None was silently converted to pass.

All final source-tree validation is rerun at the exact draft-PR head. Package
evidence is retained outside the repository under
`D:/Projects/Factorio/.evidence/facman-preview-contract-foundation-01/` and is
not a published release asset.

## Known limits

- The ULK session/Last Run task SHA is not a stable FacMan provider release and
  does not replace the production lock.
- No frontend consumes the dormant service in production yet.
- No authoritative Last Run cutover occurred.
- The complete all-frontend fake-process fault journey remains a later atomic
  WorkUnit.
- Real Factorio execution, managed installation, signing, publication, and
  ordinary TUI/Qt product work remain unavailable or out of scope.
- Hosted identifiers and conclusions are recorded in the draft PR after the
  branch is pushed; this report does not predict them.
