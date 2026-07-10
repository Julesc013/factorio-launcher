# FacMan R2 Local-Alpha Proof Checkpoint

This checkpoint records the promoted R2 local power-user alpha proof. It is a
reproducible comparison point, not a signed release, installer publication, or
v1.0 readiness claim.

> Superseded safety note: the later `FACMAN-TRUTH-FLOOR-01` audit found that the
> controlled executable did not prove real Factorio write isolation and that
> known-corpus bundle tests did not prove general diagnostic sanitization.
> Execute and diagnostic bundle export are quarantined in current builds. This
> checkpoint remains historical evidence, not current capability authority.

## Identity

- Checkpoint tag: `facman-r2-local-alpha-proof-0`
- Proof level: R2 local power-user alpha
- Promoted FacMan merge: `45a233422f4fd31fe3821e023454ba1501baeffb`
- Fresh-checkout test stabilization: `b479bd1a8af0c01a4b525251f2f51b47e0089525`
- Universal Launcher main: `99d069988cd94b40dfca4284794348fb5db621d9`
- Universal Setup main: `ef4da02ffcf2e26b95f01dd2c33b9ba154255158`

The tag target includes the checkpoint documentation and should be used as the
operator-facing baseline for future R3 comparisons. The promoted merge remains
the architectural R2 promotion point; the follow-up stabilization commit keeps
the Windows fresh-checkout redaction tests line-ending tolerant without changing
product behavior.

## Completed Proofs

- Architecture baseline and retired-root validation.
- Cross-repo boundary proof for `factorio-launcher`, `universal-launcher`, and
  `universal-setup`.
- Native CLI/TUI/daemon scaffold build.
- WinForms and AppKit shell compile proof.
- Frontend command-surface and command-parity contracts.
- Release/distribution contracts and validators.
- Package manifest validation and package skeleton generation/validation.
- Deterministic read-only Factorio discovery fixtures and ownership
  classification.
- Local Factorio mod ZIP metadata parsing, dependency parsing, lockfile
  generation, verification, export, and invalid ZIP refusals.
- Save backup, clone, export, import, malformed-save refusals, and existing
  target refusals.
- Diagnostic redaction policy, runtime redaction, diagnostic bundle export,
  doctor bundle output, secret corpus fixtures, redaction reports, and no-leak
  tests.

## Deferred

- Real Mod Portal networking.
- Factorio account login and credential-store implementation.
- Universal Setup mutation from FacMan.
- Managed Factorio installs.
- Server/dev execution.
- Auto-update.
- Signed installers, MSIX, DMG, AppImage, notarization, and package
  publication.
- Modern GUI feature lanes beyond current shell compile proofs.
- AI recommendation or opaque automation behavior.

## Validation Commands

The R2 promotion and diagnostic redaction work used these local gates:

```powershell
py -3 tools\source_format_check.py
py -3 tools\package_manifest_check.py
py -3 tools\package_layout_check.py
py -3 tools\package_skeleton_build.py --out build\package-skeletons
py -3 tools\package_skeleton_check.py --root build\package-skeletons
py -3 tools\strict_check.py
py -3 -m unittest discover -s tests -v
dotnet build apps/gui/windows/winforms/FacMan.WinForms.csproj
cmake -S . -B build/native-smoke
cmake --build build/native-smoke
ctest --test-dir build/native-smoke -C Debug --output-on-failure
py -3 tools\repro_workspace_smoke.py --require-clean --build --python "py -3"
py -3 .aide\scripts\aide_lite.py commit check --range origin/dev..dev
git diff --check
```

The three public repositories should be rechecked from fresh sibling clones
with:

```powershell
py -3 tools\repro_workspace_smoke.py --require-clean --build --python "py -3"
```

The checkpoint pass requires the sibling checkout layout to contain:

```text
<workspace>/
  factorio-launcher/
  universal-launcher/
  universal-setup/
```

## Known Limitations

- Package proof is still skeleton/layout proof, not unsigned built artifact
  proof.
- Package roots have not yet proven `facman --version`, `doctor --json`, or
  `product inspect --json` from outside the repo tree.
- The runtime/content/contract locator has not yet been proven from a packaged
  root with a separate writable workspace.
- Windows WinForms, macOS AppKit, and native CLI/TUI/daemon shells are compile
  or scaffold proofs, not complete user-facing GUI product flows.
- Discovery is fixture-backed and explicit-root only; real Steam VDF, Windows
  registry, macOS Spotlight, and Linux package-manager discovery remain
  deferred.
- Local mod ZIP behavior is offline and fixture-backed; Mod Portal download and
  account-token behavior remain deferred.
- Universal Setup remains separate and owns destructive installed-software
  mutation; FacMan does not install, repair, or uninstall Factorio through this
  checkpoint.

## Historical Next Phase

The checkpoint originally described R3 Safe Beta as starting with unsigned
local package artifacts:

```text
FACMAN-BUILT-PACKAGE-ARTIFACT-01
FACMAN-PACKAGE-RUNTIME-SMOKE-01
FACMAN-DIAGNOSTIC-UX-POLISH-01
FACMAN-RUNTIME-CLIENT-BOUNDARY-01
```

Do not use this checkpoint as justification for Mod Portal networking, setup
mutation, server/dev execution, signed package publication, auto-update, or new
GUI feature work.
