# FacMan 0.1 alpha.5 truth remediation

Date: 2026-09-02

WorkUnit: `FACMAN-0.1-ALPHA5-TRUTH-REMEDIATION-01`

Lifecycle result: verified pending closeout. This is a nonterminal machine
verification state, not review, closure, beta allocation, or release authority.

## Executive result

The alpha.5 implementation is now described by one consistent source of truth.
The remediation fixes the semantic gaps found after the historical alpha.5
candidate closeout and gives 0.1 a linear, 1.0-shaped path through Alpha.6,
Alpha.7, feature freeze, and beta.1. It does not claim that the remaining
journeys, human gates, or release effects have passed.

The result is a modular-monolith foundation with one Factorio application core,
one presentation/terminal boundary, one ULK session/Last Run authority, one USK
setup boundary, generated command metadata, deterministic resources, six
product-package lanes, and explicit future admission gates. A rewrite is not
warranted; future work should continue by characterization, ratcheted extraction,
measured optimization, and exact package qualification.

## Delivered remediation

- Workspace migration inspect, plan, and apply are truthfully classified as
  implemented. The admitted apply law remains exactly two canonical actions,
  journaled, no-clobber, source-preserving, and bounded; public general
  recovery and rollback remain Alpha.6 work.
- `ulk.session.journal.v1` is the sole live Last Run authority.
  `presentation.query` is the product projection seam. Transient frontend view
  copies may render a completed response but are never persisted or consulted
  as authority or fallback, and no frontend reconstructs terminal outcomes.
  Compatibility GTK3/AppKit shells report unavailable until they adopt the
  typed query.
- `windows_product_x64` is independently validated as the shared-linkage
  product target. The separate WinForms technical-preview v2 target retains its
  embedded/static contract and distinct artifact identity.
- The Technical Preview census now cross-validates lifecycle, catalog, profile,
  target, artifact, command availability, Last Run, migration, and activation
  state. Generated census prose is line-bounded and checked in CI.
- Complexity budgets use the language-aware
  `lexical_decision_points_v2` metric across 28 production files. Python
  multiline strings/comments and C-family preprocessor decisions are handled
  deliberately, so the ratchet measures code rather than lexical noise.
- The beta readiness contract now makes native visual quality, platform design
  standards, localization, text expansion, keyboard/screen-reader behavior,
  accessibility, performance, security, and fault evidence exact package-bound
  gates. Human-only receipts cannot be satisfied by automation.
- Cancelled alpha.1, alpha.2, and alpha.3 human packets are retained as
  historical provenance and cannot satisfy the distinct beta.1 receipt.
- The canonical future graph is linear and non-authorizing:
  Alpha.6 workspace migration/recovery, Alpha.6 managed-install/package
  lifecycle, Alpha.7 content/world reconstruction, Alpha.7 fresh Play/session
  and GTK3/AppKit convergence, unallocated feature-freeze qualification, then
  exact beta.1 candidate acceptance.
- Windows external task roots are deterministically shortened, legacy owned
  roots remain cleanup-recognizable, provider Git operations enable long paths,
  and hygiene retains exact containment and ownership rules.
- Schema CI directly watches and validates generated metadata, the Technical
  Preview census, engineering-quality budgets, and beta-readiness contracts.
- Roadmaps, current state, README, architecture, product, support, package, GUI,
  CLI/TUI, build/distribution, and maintenance documentation now use the same
  support and authority vocabulary.

## Exact local validation

The complete external-root product gate passed on 2026-09-02:

```text
py -3 tools/dev.py verify-all product
```

- exact provider revisions: PASS;
- shared product and independent static release builds: PASS;
- native CTest suite: 41/41 PASS;
- WinForms .NET Framework 4.8 Release build: 0 warnings, 0 errors;
- Python promotion obligation suite: 1,463 tests, 0 failures, 0 errors;
- classified skips: 2 optional, 5 unsupported, 2 not applicable,
  0 required blocked, 0 unknown, 0 historical-only;
- promotion obligation gate: PASS;
- strict validation: PASS, including 400 schemas, 127 commands,
  247 refusal codes, 128 refusal goldens, package TCK, security, compliance,
  accessibility, source format, AIDE, release programme, readiness, engineering
  quality, and generated-state checks;
- deterministic resource pack: 600 entries and 2,233,690 bytes;
- resource content SHA-256:
  `4c9802f155c24f289c4d005d06b55bf1769cd939dbce62321875d5a21817827d`;
- resource-pack SHA-256:
  `ce95c45eb588fae9c0baee6199624e64d90cb872e71b6ba9945126c86c9dc10b`.

Before the full gate, 176 affected tests and all focused generators/validators
passed. After the AIDE lifecycle transition, 143 lifecycle-focused tests,
generated-state checks, strict validation, and AIDE validation/self-test also
passed. The final diff check is recorded in the task evidence.

## Product truth after remediation

The twelve beta journeys remain deliberately differentiated:

- 4 are implemented but not fully qualified;
- 6 are partially implemented;
- 2 are authority-blocked, with partial machinery but no accepted execution
  or mutation authority.

The current alpha.5 candidate proves architecture, compilation, packages, and
machine behavior for its exact historical revision. It does not prove current
source, complete ordinary journeys, native human quality, or public release.

Windows WinForms .NET Framework 4.8 remains the reference direction. GTK3 on
Ubuntu 24.04 x64/X11 and AppKit on macOS 13+ Intel have machine-qualified
packages whose GUI lanes remain semantic previews. Qt6 is a scaffold; WinUI
and SwiftUI are placeholders. Those later toolkits remain post-beta admissions.

## Qualification and authority boundary

Historical workflow run `33576140943`, attempt 1 qualifies only source
`a7a518dbfe2a6d54da7b9c84fbd318300265e31d` and tree
`1ebcd2b230ed188e021880ffa4c438de2ede655b`. This remediation revision and its
later dev/main synchronization merges require a fresh hosted product-candidate
run from final `main`; tree equality cannot extend revision qualification.

No Factorio process was executed. No live managed install was mutated. No
human verdict was fabricated. Beta allocation, tagging, signing, Apple
notarization, publication, and support activation remain false and require
separate explicit authority.

## Remaining release path

1. Integrate this verified remediation through the protected task-to-dev merge.
2. Promote exact dev to main and back-synchronize main to dev.
3. Run the product-candidate workflow exactly once for final main, verify its
   six products and evidence bundle, and preserve it in durable custody.
4. Complete the two Alpha.6 WorkUnits, then the two Alpha.7 WorkUnits.
5. Enter feature freeze only when J01-J12 are machine-complete.
6. Produce distinct exact-byte human receipts and separately authorize any
   beta allocation, tag, signing, notarization, publication, or support effect.

Apple Silicon/universal2, broader Linux/Wayland support, Qt6/WinUI/SwiftUI
product admission, network/accounts, automatic update, daemon/remote control,
public plugins/extensions, and server administration remain deferred. Pulling
them into beta before the ordinary journey and evidence gates close would
increase surface area without improving release truth.
