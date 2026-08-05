---
document_id: FACMAN-HUMAN-INTERFACE-CONSTITUTION
schema_version: "1.0"
status: governing
created: 2026-08-05
last_reviewed: 2026-08-05
appearance_baseline: system-native
related_policy:
  - docs/product/interface_design_system.md
  - docs/product/operational_ux.md
  - docs/product/facman_winforms_c1_shell.md
---

# FacMan human interface constitution

## Constitutional rule

> **Users act on understandable resources. Consequence determines
> engagement. Every operation remains observable. Closing a window is not
> cancellation. Failure is reversible, recoverable, or explicitly unresolved.
> Native shells share meaning, not widgets.**

This document defines the durable interaction law for FacMan and for the
Universal Launcher and Universal Setup semantics that FacMan presents. It
applies to the CLI, TUI, WinForms, AppKit, GTK, and any later native
projection. It is not a feature roadmap, a widget specification, or a support
claim. The broader shell and appearance policy remains in
[`interface_design_system.md`](interface_design_system.md).

## 1. Authority remains explicit

An interface collects intent and presents owner-produced truth. It does not
manufacture authority. These distinctions are mechanical:

```text
download complete         != package trusted
setup plan                != mutation authority
launch plan               != process authority
technical qualification  != human verdict
human Pass                != route promotion
route promotion           != arbitrary execution
artifact digest           != publisher identity
publication               != support
```

A shell may display state, freshness, effects, evidence, refusal, progress,
outcome, and recovery; collect typed input and explicit confirmation; submit a
registered semantic action; and request cancellation by operation identity.

A shell may not construct raw privileged commands, issue setup or process
authority, edit an installation, retain account secrets, reinterpret an
unknown outcome as success, bypass plan review, or infer cancellation from a
closed window or disconnected transport.

## 2. Core interaction laws

| Law | Required consequence |
| --- | --- |
| **Intent is explicit** | Execution, setup, account, network, signing, and publication effects are never hidden behind inspection or navigation. |
| **Resources precede commands** | People act on Instances, Installations, Profiles, Packages, and Operations rather than internal command identifiers. |
| **System conventions win** | Native controls, menus, focus, fonts, colours, dialogs, button order, and shortcuts follow the target platform. |
| **One meaning, many projections** | CLI, TUI, and GUIs consume the same semantic actions, refusals, outcomes, and recovery identities; they do not share widget code. |
| **Consequence determines engagement** | Confirmation and revalidation strength scale with the effects and reversibility of the action. |
| **Feedback is continuous** | The current phase, possible effects, progress, operation identity, and terminal or unresolved state remain inspectable. |
| **Close is not cancel** | Window, page, and transport lifetime remain independent from backend operation lifetime. |
| **Failure remains truthful** | Failure is reversed, recoverable by an exact reference, or explicitly unresolved; it is never silently converted to success. |
| **Complexity is progressive** | The primary journey shows the decision and safe next action; raw records and generic command forms remain under Advanced. |
| **Capabilities are honest** | Unsupported actions are absent or explicitly unavailable, with a stable reason and safe next action. |
| **Appearance is platform-owned** | System Native is the mandatory accessibility and recovery baseline; branding is confined to bounded product surfaces. |
| **Testing is contextual** | Claims bind an exact OS, framework, architecture, package, display context, accessibility stack, and positive and failure journey. |

System status is never conveyed by colour alone. Readiness, warning, failure,
running, recovery, and unknown outcome each require text, semantic role, and
accessible state.

## 3. Effect and engagement classes

The effect class describes consequence, not visual prominence. A higher class
cannot inherit the admission policy of a lower class merely because both use a
button or command.

| Class | Typical operation | Required engagement |
| --- | --- | --- |
| **E0 — inspect** | Inspect an instance, installation, package, or operation. | Immediate and read-only. Preserve the observed identity and freshness. |
| **E1 — navigate or project** | Sort, filter, select, expand, or change a local view. | Immediate and reversible without changing product state. |
| **E2 — bounded local preference** | Rename an owned instance or change a presentation preference. | Explicit action, visible result, and undo or restoration where useful. |
| **E3 — owned content change** | Apply a modset, restore a save, or replace owned content. | Exact effects review, snapshot or equivalent rollback point, explicit confirmation, and post-change verification. |
| **E4 — installed-state mutation** | Install, repair, move, update, downgrade, or uninstall. | Exact Universal Setup plan, target identity and ownership, effects review, explicit approval, provider revalidation, durable operation identity, and recovery. |
| **E5 — external trust or publication** | Use credentials, publish, sign, or administer a remote system. | Separate authentication, narrowly scoped authority, explicit destination and effects, and an auditable terminal outcome. |

Repeated generic warnings are not engagement. Confirmation must identify the
resource, effect, owner, and recovery consequences relevant to its class.

## 4. Operations outlive presentations

Every long-running operation exposed by a shell carries at least:

```text
operation_id
attempt_id
owner
phase
effects_may_have_occurred
progress
terminal_outcome
recovery_reference
```

The interface obeys these rules:

- closing a page or window leaves the operation running unless the user makes
  an explicit cancellation request by identity;
- a frontend crash does not erase a durable operation;
- a transport timeout produces an unknown or recovery-required outcome, not
  an implicit cancellation;
- backend unavailability leaves existing inspectable state visible and makes
  unavailable actions explicit;
- workspace, installation, provider, policy, or evidence changes stale every
  dependent snapshot and plan;
- progress reports the current phase and effects truth rather than an
  unqualified spinner.

Technical refusal remains exact but is progressively disclosed as:

```text
short summary
plain-language explanation
safe next action
expandable evidence
exact diagnostic code
```

## 5. Native semantic projections

FacMan has one product identity, semantic command system, compatibility model,
capability vocabulary, and conformance suite. It may have different binaries,
runtime closures, providers, native shells, package projections, and
qualification records for different targets.

Framework controls never cross the presentation boundary. The product-owned
presentation state supplies immutable, revision-bound resource, readiness,
action, operation, refusal, and recovery truth. Platform adapters decide
control selection, command placement, shortcut, focus order, dialog order,
spacing, and native capability fallback.

No profile claims compatibility merely because it compiles. System APIs,
runtime and loader closure, CPU floor, packaging, clean-host behavior, and the
full contextual validation record determine the support claim.

## 6. Classic WinForms C1 profile

The current classic Windows reference profile is a Windows 10 and Windows 11
x64 `.NET Framework 4.8` WinForms product surface. It is not one executable for
Windows XP through Windows 11 and grants no legacy-Windows support claim.

### Native construction

- Activate Common Controls v6 in the packaged executable.
- Retain standard WinForms and Win32 controls, ordinary window chrome, and
  native file and folder dialogs.
- Use system rendering for `MenuStrip`, `ToolStrip`, and `StatusStrip` and use
  system fonts, colours, focus, selection, and contrast behavior.
- Avoid broad owner drawing, custom chrome, simulated historical Windows
  skins, custom scrollbars, and fixed bitmap text.
- Keep Instances, Installations, Activity, and one compact Launch Deck as the
  primary C1 resources. Put options, diagnostics, generated command forms, and
  raw evidence behind conventional menus or Advanced surfaces.

### Responsive layout and DPI

- Use `AutoSize`, `Dock`, `Anchor`, `TableLayoutPanel`, and
  `FlowLayoutPanel`; replace release-critical fixed-size dialogs.
- Allow long localized text to wrap or resize without clipping.
- Use one documented WinForms application-configuration DPI model throughout
  a related form hierarchy; do not mix incompatible scaling modes.
- Prove usable layout and visible actions at 100%, 150%, and 200% scaling.

### Activity, refusal, and accessibility

- A button click is not operation completion; Activity renders backend-owned
  phase, identity, effects, outcome, and recovery.
- Closing the main window does not invent cancellation or success.
- Preserve exact refusal codes while presenting a comprehensible summary and
  next action.
- Provide logical tab order, access keys, conventional shortcuts, visible
  focus, accessible names, roles, values, descriptions, and state.
- Support keyboard-only completion, Windows contrast themes, Narrator and
  Accessibility Insights inspection, and status that never relies on colour
  alone.

System Native is the required recovery appearance. Bounded FacMan branding may
decorate the application icon, page identity, instance artwork, Launch Deck,
status symbols, empty states, and About surface, but it does not replace native
control behavior.

## 7. Validation contexts

An interface claim is valid only for its recorded context and both its
positive and paired failure journey. At minimum, record:

```text
source, package, and composition identity
operating system and architecture
framework and runtime closure
provider and semantic-contract identities
display scale, font scale, and localization expansion
keyboard, focus, and accelerator behavior
screen reader and accessibility-inspector result
contrast theme and non-colour status result
reduced motion/transparency where supported
operation interruption, frontend close/crash, and transport timeout
stale evidence and external state change
malformed input and structured refusal
backend unavailable and recovery-required behavior
```

For the WinForms C1 release lane, the required contextual matrix includes
Windows 10 and Windows 11 x64, non-administrator use, relocation, 100%, 150%,
and 200% display scaling, keyboard-only traversal, contrast themes, Narrator or
equivalent screen-reader inspection, long-text layout, Last Run, relaunch, and
operation/recovery inspection.

Automated accessibility metadata, screenshots, and compilation do not replace
manual validation of the release-blocking positive and failure journeys.

## 8. C1 boundary

C1 applies this constitution to one exact Windows reference journey. It does
not require a complete Home/Instances/Library/Activity redesign, every
secondary window, custom themes, WinUI, an XP-specific shell, Vista or Windows
8 variants, or complete AppKit/GTK parity.

Nothing in this constitution authorizes Factorio execution, installed-state
mutation, credentials, signing, publication, a human verdict, or route
promotion. Those remain separately admitted operations owned by their exact
product, provider, evidence, and authority records.
