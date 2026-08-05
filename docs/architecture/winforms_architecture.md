# Windows Forms architecture

Status: ratified post-C1 architecture; no implementation authority

## Boundary

The successor Windows line uses one shared shell implementation and two thin
managed hosts. Framework, CPU, API, package, qualification, and support are
separate dimensions. No operating-system-named source family is admitted.

The current `apps/gui/windows/winforms/FacMan.WinForms.csproj` remains the C1
net48/x64 executable. This document does not restructure it. The post-C1
migration must preserve a buildable, packageable, and testable C1 shell until
the successor is independently accepted.

## Initial bounded solution

```text
apps/gui/windows/winforms/
  FacMan.WinForms.sln
  src/
    FacMan.WinForms.Presentation/
    FacMan.WinForms.Shell/
    FacMan.WinForms.Platform/
  hosts/
    FacMan.WinForms.Net40/
    FacMan.WinForms.Net48/
  gallery/
    FacMan.WinForms.Gallery/
  tests/
    FacMan.WinForms.UnitTests/
    FacMan.WinForms.StructuralTests/
    fixtures/
```

The first production solution contains only:

```text
FacMan.WinForms.Presentation
FacMan.WinForms.Shell
FacMan.WinForms.Net40
FacMan.WinForms.Net48
```

`Platform` may remain a namespace in the shell assembly until dependency or
ownership pressure justifies a fifth production assembly. Gallery and tests
are not product payloads. A page, control, or adapter becomes a separate
assembly only for independent packaging, an enforced dependency boundary, a
real second consumer, or demonstrated compilation/ownership pressure.

## Shared shell contract

`FacMan.WinForms.Shell` targets the compatibility surface admitted by the
net40 host. Both hosts use the same Forms, UserControls, Designer files,
resources, semantic navigation identities, and action rendering.

Each visual type follows:

```text
Name.cs
Name.Designer.cs
Name.resx
```

with `Localizable = true`, system fonts and colours, standard WinForms layout
containers, native focus behavior, and no owner-drawn primary controls.

The net48 host injects enhanced platform services. The net40 host injects
compatibility adapters. Host projects contain entry point, manifest,
configuration where required, target-profile binding, and platform adapters;
they do not fork product pages.

## Presentation seam

The first immutable contract is intentionally small:

```text
ShellSnapshot
  identity, revision, freshness
  navigation
  selected_instance, readiness, launch_deck
  installations
  operations, last_run, recovery
  actions, notifications

SemanticAction
  snapshot identity and revision
  registered action identity
  typed arguments
  declared effects and authority requirement
```

Forms never call several backend commands and invent a combined truth, parse
unbounded arbitrary JSON in event handlers, infer Last Run authority, convert
unknown outcomes to success, or decide whether Play is authorized.

The compatibility-safe client boundary is event-oriented:

```text
immutable snapshot arrives
semantic action is submitted
operation update is observed
completion, refusal, or recovery is reported
```

The net48 adapter may use `Task` internally. The net40 adapter may use worker
threads, callbacks, `BackgroundWorker`, and `SynchronizationContext`. The
shared shell depends on neither transport implementation.

## Migration

```text
existing commands
-> compatibility presenter
-> ShellSnapshot v1
-> old C1 shell and successor fixture consume the same snapshot
-> backend-owned snapshot
-> remove compatibility presenter after equivalence evidence
```

`C1LivePresentationStore` remains the temporary adapter while the seam is
introduced. The compatibility presenter is deleted only after exact positive,
refusal, operation, interruption, recovery, and Last Run equivalence.

## Component pressure

The first shared library implements only components required by the accepted
fixture journey:

```text
FacManShellForm
NavigationControl
PageHostControl
ResourceListControl
ResourceInspectorControl
ProblemBannerControl
LaunchDeckControl
ClassicDialogBase
```

No catalogue of hypothetical pages, providers, or dialogs is pre-created.

## Current executable evidence

The current source project is one old-style net48/x64 WinExe. Its entry point
enables visual styles and compatible text rendering before opening
`C1ShellForm`. Its source manifest is `asInvoker`, names the Windows 10/11
compatibility GUID, and requests PerMonitorV2 awareness.

The source manifest does not itself establish a Common Controls v6 dependency.
That dependency, DPI behavior, imported native APIs, CRT, and provider runtime
closure must be inspected from the exact built and packaged executable before
any target or support claim.

## Admission gates

The fixture successor must pass keyboard, pseudo-localization, High Contrast,
DPI, compact-layout, problem/refusal, operation, and recovery corpora without
backend authority changes. Live binding follows only after fixture parity.
The net40/x86 host follows only after net48 successor qualification and must
prove the complete product closure on every claimed host.

This architecture grants no provider adoption, product execution, Setup
mutation, signing, publication, route promotion, or support claim.

