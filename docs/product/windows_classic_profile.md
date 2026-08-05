# FacMan Windows Classic product profile

Status: ratified post-C1 product direction; non-authorizing

## Purpose

FacMan Classic for Windows uses one product meaning, one shared Windows Forms
shell source, capability-selected platform adapters, product-level bundles,
and independently qualified operating-system claims.

This profile does not replace the current C1 shell or enter its release chain.
It prepares the successor Windows product direction after C1 is
release-proven. It grants no provider adoption, Setup mutation, Factorio
execution, signing, publication, support, or route authority.

The durable interaction law remains
[`human_interface_constitution.md`](human_interface_constitution.md). This
document owns only the classic Windows product projection. Project boundaries
and adapters are defined by
[`winforms_architecture.md`](../architecture/winforms_architecture.md).

## Product rule

```text
one classic Windows product projection
one semantic navigation model
one shared Form and control library

two principal managed host profiles
  x64 primary
  x86 compatibility

independent whole-product qualification
  XP SP3
  Vista SP2
  Windows 7 SP1
  Windows 8.1
  Windows 10
  Windows 11
```

Operating-system names belong in target, qualification, support, and release
records. They do not own ordinary Forms or UserControls. Default source
families named `Xp`, `Vista`, or `Win7Plus` are rejected.

## Current C1 preservation

The existing net48/x64 `C1ShellForm` remains the Windows 10/11 reference shell
until its exact Play route, package, clean-machine, and accessibility evidence
are complete. Its current five-tab projection, embedded fixtures, Advanced
explorer, and backend transport are characterized legacy inputs—not the
permanent successor navigation contract.

No post-C1 shell change may enter the active provider-convergence, pin,
source-closure, qualification, or Play-verdict candidate. Replacement occurs
only after semantic and packaged-product qualification.

## Semantic information architecture

The stable root identities are:

```text
home
instances
library
activity
```

`Library` is a stable internal identity; its displayed label remains subject
to observed user evidence. Settings, accounts, evidence, diagnostics, and
Advanced are contextual or secondary surfaces rather than peer product roots.

The classic projection uses conventional Explorer/MMC structure:

```text
MenuStrip
ToolStrip or contextual command row
SplitContainer
  navigation TreeView or navigation ListView
  selected page host
compact persistent Launch Deck
StatusStrip
```

Suggested hierarchy:

```text
Home
Instances
Library
  Installations
  Mods and Modpacks
  Updates
  Downloads and Cache
Activity
  Operations
  Running
  Recovery
  Console
  Diagnostics
```

A selected resource may use a local detail tab control for Overview, Content,
Saves, Configuration, History, and Advanced. That is scoped resource
navigation, not a second global information architecture.

## Interaction projection

The main window presents one ordinary primary action. A compact Launch Deck
shows selected instance, readiness, concise identity, primary action, and a
bounded secondary-action menu. Raw revisions, refusal codes, and evidence
identities are expandable details rather than primary workflow labels.

Refresh retains the last coherent snapshot and disables only actions whose
preconditions are stale. Closing a window never means operation cancellation.
Dialogs use layout containers, system metrics, native buttons, and reusable
validation rather than absolute coordinates.

Standard and Compact layouts must remain usable at 100%, 150%, and 200% DPI,
High Contrast, keyboard-only operation, and narrow effective work areas. The
successor compact-state objective includes 800x600-class effective layouts;
that objective is not a current support claim.

## Managed host profiles

The machine-readable planning source is
`release/index/windows_target_profiles.v1.toml`.

| Profile | Role | Managed host | Architecture | Objective |
| --- | --- | --- | --- | --- |
| `win_x64_c1` | Frozen current reference | net48 | x86-64 | Close Windows 10/11 C1 |
| `win_x64_primary` | Principal classic host | net48 | x86-64 | Independently qualify Windows 7 SP1 through Windows 11 |
| `win_x86_compat` | Principal compatibility host | net40 | x86 | Independently qualify XP SP3, Vista SP2, and later fallback |

The compatibility host is a hypothesis until the entire x86 closure passes.
Microsoft documents .NET Framework 4.0.3 as the final Framework line for XP
SP3, 4.6 for Vista, and 4.8 for Windows 7 and 8.1. Those operating systems are
no longer supported by Microsoft, so these facts define historical technical
ceilings, not FacMan support. Later 4.x Framework releases are in-place
updates, but running an application on a later CLR still does not prove its
native backend, provider, package, recovery, or Factorio route.

Visual Studio 2022 cannot build projects targeting .NET Framework 4.0 through
4.5.1. A net40 host therefore needs a pinned legacy build environment or
another reviewed reference-assembly toolchain, followed by execution on the
actual target hosts.

Authoritative external references:

- [Microsoft: .NET Framework versions and dependencies](https://learn.microsoft.com/en-us/dotnet/framework/install/versions-and-dependencies)
- [Microsoft: Install .NET Framework on Windows](https://learn.microsoft.com/en-us/dotnet/framework/install/on-server-2019)
- [Microsoft: Developer and targeting packs](https://learn.microsoft.com/en-us/dotnet/framework/install/guide-for-developers)

## Whole-product qualification law

A managed executable does not establish an operating-system claim. Every host
row independently proves the exact:

```text
WinForms host and presentation adapter
native FacMan backend
ULK and USK closure
CRT and private runtime closure
filesystem, path, Unicode, clock, and crypto behavior
process launch, containment, timeout, and recovery behavior
package verification and relocation
Factorio route compatibility
keyboard, accessibility, contrast, and DPI behavior
clean non-administrator journey
```

One package may hold different qualification and support states on different
operating systems. Compilation alone produces no support status.

## Product bundle law

Frontend, target, composition, package projection, support, and release
resolution are independent dimensions. The intended desktop bundles are:

```text
FacMan-<version>-win-x64-portable.zip
FacMan-<version>-win-x86-compat-portable.zip
```

Each is a complete product closure containing its shell, backend, admitted
TUI, provider runtime, contracts, licences, and recovery material. A setup
executable later installs the same resolved payload; it is a package
projection, not another frontend product. Per-user and system installation
are USK plan decisions and are not properties of a portable ZIP.

Headless and maintenance compositions remain explicit capability-reduced
products. A frontend-specific archive is not the default desktop product.

## Dependency order

All successor work remains in the canonical later horizon:

```text
Windows profile and release-record normalization
-> presentation snapshot seam
-> bounded shared component library
-> fixture-only shell v2
-> net48 live binding and qualification
-> x86 compatibility spike and per-host qualification
-> Setup maintenance shell after production-ready USK lifecycle
```

Every step preserves the old C1 shell until its replacement passes exact
semantic, packaged, accessibility, recovery, and live-product evidence.

