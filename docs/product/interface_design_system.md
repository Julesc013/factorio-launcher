---
document_id: FACMAN-INTERFACE-DESIGN-SYSTEM
schema_version: "1.0"
status: governing-draft
created: 2026-07-29
last_reviewed: 2026-07-29
canonical_plan: release/index/plan.v1.toml
appearance_baseline: system-native
product_appearance: oem-plus-when-qualified
classic_profiles:
  - classic.windows.winforms
  - classic.macos.appkit
  - classic.linux.gtk3
modern_profiles:
  - modern.windows.winui
  - modern.macos.swiftui
  - modern.linux.qt6-kirigami
---

# FacMan interface design system

## Executive rule

> **Portable semantics, native presentation, constrained branding, and
> explicit capability adaptation.**

FacMan is not one visual skin stretched over six frameworks. It is one product
model, one command and operation model, one set of page and semantic-action
identities, one constrained appearance and extension model, and one
accessibility and recovery standard projected through six native shells.

The classic line is:

- WinForms on Windows;
- AppKit on macOS;
- GTK 3 on Linux.

The optional modern line is:

- WinUI 3 on Windows;
- SwiftUI for macOS;
- Qt Quick Controls with Kirigami on Linux.

The mandatory `1.0` Qt projection is Qt 6 Widgets. It is a separate
cross-platform traditional desktop shell; Qt Quick/Kirigami remains a later
KDE-focused adaptive projection rather than the universal Qt requirement.

Each shell must look, read, navigate, focus, announce, resize, and recover like
an application native to its target platform. Product identity belongs in
bounded FacMan surfaces such as the Launch Deck, page identity, instance
artwork, status, and empty states. It does not replace system controls or the
operating system's interaction language.

This document defines product and architecture policy. It does not claim that
all profiles are implemented, supported, accessible, or release-qualified.
Those claims require the compatibility and evidence registries described by the
planning operating model.

## 1. Separate the four design decisions

Four concepts must never be collapsed:

1. **Product semantics** — what the page, state, action, refusal, operation, and
   recovery mean.
2. **Framework** — the implementation APIs and control technology.
3. **Design authority** — the platform HIG and interaction conventions users
   expect.
4. **Capability profile** — what a specific OS, framework version,
   architecture, display environment, and package can actually provide.

Examples:

- AppKit and SwiftUI are different implementation frameworks governed by the
  Apple HIG for macOS.
- WinForms is a native desktop framework without an intrinsic modern Fluent
  design language; it can still use responsive layout, DPI scaling, native
  controls, and Windows desktop conventions.
- The current GNOME HIG primarily describes GTK 4 and Libadwaita. Its general
  usability principles inform GTK 3, but its components are not a literal GTK 3
  specification.
- GTK 3 supports both header-bar and traditional desktop arrangements. A
  header bar is a profile choice, not an architectural mandate.
- Qt 6 supplies multiple UI stacks and styles. Qt alone does not make a shell
  KDE-native, GNOME-native, Windows-native, or Material.
- Mica, SF Symbols, symbol effects, modern navigation containers, materials,
  and other features are capability-gated enhancements, not universal
  framework promises.

The shell profile therefore records at least:

```text
profile_id
platform
architecture
framework
framework_version
minimum_os
design_authority
navigation_profile
appearance_modes
capabilities
fallbacks
accessibility_stack
qualification_tier
evidence
```

## 2. Design authorities and intended roles

| Framework | Governing authority | FacMan role | Primary interaction shape |
|---|---|---|---|
| AppKit | Apple HIG for macOS | Classic native Mac shell | Menu-complete, resizable, information-dense desktop |
| SwiftUI | Apple HIG for macOS | Modern adaptive Mac shell | Sidebar/split-view Mac desktop |
| WinForms | Windows desktop UX and Win32 conventions | Classic native Windows shell | Menu/tool/status desktop utility |
| WinUI 3 | Fluent Design and current Windows app guidance | Modern adaptive Windows shell | Responsive navigation and list/detail |
| GTK 3 | GTK 3 behavior and selected general GNOME principles | Classic Linux/X11 shell | Cross-desktop menu/notebook or stack utility |
| Qt 6 Widgets | Platform desktop conventions plus Qt Widgets guidance | Mandatory 1.0 Qt shell | Dense native-style cross-platform desktop utility |
| Qt Quick + Kirigami | KDE HIG, Kirigami, and Qt Quick conventions | Modern Linux/Wayland shell | Adaptive KDE-oriented desktop |

Qt Widgets is the selected mandatory `1.0` Qt profile. Qt Quick/Kirigami is an
optional later modern Linux profile. The two stacks must not be mixed casually
in one shell merely because both are Qt.

## 3. Shared semantic architecture

The architecture shares meaning, never widgets:

```text
Universal Launcher / Universal Setup / Factorio product binding
                              |
                              v
                 command and operation contracts
                              |
                              v
                  product presentation service
                              |
                              v
          immutable view snapshots and action descriptors
                              |
              +---------------+---------------+
              |                               |
              v                               v
        classic adapters                 modern adapters
       /       |       \                /       |       \
 WinForms   AppKit   GTK 3          WinUI    SwiftUI   Kirigami
                              |
                              v
                           CLI / TUI
```

No `Control`, `NSView`, `GtkWidget`, `FrameworkElement`, SwiftUI `View`,
`QObject`, `QWidget`, or `QQuickItem` crosses the presentation boundary.

No shell reads domain stores to reconstruct truth. The presenter supplies an
immutable snapshot with explicit identity, revision, freshness, selection,
available actions, operation references, and structured refusal or recovery
state.

### Initial semantic records

Keep the first shared contract intentionally small:

```text
ShellSnapshot
NavigationNode
PageSummary
InstanceListView
InstanceSummaryView
ReadinessView
LaunchDeckView
ActionDescriptor
PlanReviewView
OperationView
RecoveryView
NotificationView
ThemeCapabilities
```

Later resource collections, details, and form descriptors must be earned by
real page pressure. Do not design a universal future-page schema before the
first journey proves the vocabulary.

### Action descriptor

Every visible operation-bearing action maps to a registered semantic identity:

```text
action_id
command_id
label_key
description_key
role
availability
refusal
effects
risk
confirmation_policy
default_action
context
keyboard_role
accessibility_label_key
```

The shared model says what the action means. The platform adapter decides where
and how that semantic role appears.

| Role | AppKit | WinForms | GTK 3 | WinUI 3 | SwiftUI | Kirigami |
|---|---|---|---|---|---|---|
| Settings | App menu and separate window | Menu or settings form/page | Menu and preferences dialog/page | Navigation page | Settings scene/window | Settings page/dialog |
| Destructive | Destructive sheet role | Destructive dialog action | Destructive response | ContentDialog destructive action | Destructive button role | Destructive action |
| Cancel | Native sheet order | Windows dialog order | GTK response order | Close/cancel role | Cancel role | Platform action order |
| Complete commands | Global menu | MenuStrip | Menubar/GMenu | Menus and shortcuts | Commands/menu | Menubar or adaptive menu |
| Primary Play | Default push button | Default button | Suggested-action button | Accent button | Prominent button | Prominent action |

Literal shortcuts, button order, control size, menu placement, and standard
labels belong to the platform adapter. Semantic action identity, effects,
refusal, confirmation, and result do not.

## 4. Primary journeys are hand-designed

Metadata-driven command forms are useful for:

- Advanced command exploration;
- development-only commands;
- diagnostics;
- administrative operations;
- compatibility fallback;
- newly registered experimental commands.

They are not the primary product experience.

The following surfaces require deliberate native task design:

- instance list and selection;
- instance summary and exact environment;
- readiness and blocked-readiness explanation;
- Launch Deck and Play preview;
- plan review and confirmation;
- Activity and operation inspection;
- interrupted-operation recovery.

Generic forms may call the same commands under Advanced. They may not choose
the primary journey, hide effects, weaken refusal, reinterpret outcomes, or
become the only path merely because they are inexpensive to generate.

## 5. Classic shell profiles

The classic profiles share page and action identities:

```text
Home
Updates
Installations
Mods
Instances
Accounts
Activity
Settings
Launch Deck
```

Their exact placement differs:

| Feature | WinForms | AppKit | GTK 3 |
|---|---|---|---|
| Main menu | In-window menu bar | Global menu bar | Traditional menubar |
| Top pages | Tabs or classic selector | Segmented/tab/toolbar navigation | Notebook or stack switcher |
| Settings | Form, category page, or dialog | Separate Settings window | Preferences dialog/page |
| Primary action | Default Windows button | Default Mac push button | Suggested-action button |
| Persistent status | StatusStrip | Status/activity area | Status/activity area |
| Dialogs | Windows ordering | Sheet and Mac ordering | GTK response ordering |
| Icons | System roles plus FacMan | Template images plus FacMan | Symbolic theme icons plus FacMan |

Classic compatibility and legacy-platform qualification are independent.
AppKit design can be excellent without macOS 10.9 support, and a macOS 10.9
build can be technically compatible without being release-qualified.

## 6. AppKit profile

### Interaction model

A native AppKit shell uses:

- the global menu bar for the complete command surface;
- a standard resizable `NSWindow`;
- `NSToolbar`, segmented navigation, or tab controllers for frequent page or
  contextual commands;
- `NSTableView` and `NSOutlineView` for dense resource views;
- `NSSplitViewController` for master/detail;
- sheets for window-contextual modal work;
- standard open/save panels;
- keyboard shortcuts as first-class commands;
- a separate Settings window opened conventionally with Command–Comma;
- system fonts, colors, focus, control behavior, and accessibility.

Recommended shell:

```text
global menu bar
standard resizable NSWindow
toolbar, segmented, or tab page selection
native content area
persistent Launch Deck
status and Activity access
separate Settings window
```

### AppKit mappings

| FacMan concept | AppKit mapping |
|---|---|
| Installation/instance hierarchy | `NSOutlineView` |
| Dense collection | `NSTableView` |
| Master/detail | `NSSplitViewController` |
| Frequent command | `NSToolbar` |
| Contextual confirmation | Sheet |
| File/folder choice | `NSOpenPanel` / `NSSavePanel` |
| Primary Play | Default push button |
| Long operation | Progress plus Activity surface |
| Complete commands | Global menu bar |

### Older macOS capability profile

The current documented compatibility target is macOS 10.13. The same capability
approach applies to any separately approved 10.9 exploration: an older AppKit
deployment does not imitate the current HIG with unavailable APIs. It declares
capabilities:

```text
supports_system_symbols
supports_dark_appearance
supports_vibrancy
supports_modern_toolbar_items
supports_new_navigation_components
supports_symbol_effects
```

The compatibility fallback uses standard window chrome, ordinary controls,
Auto Layout, system fonts and available colors, bundled template icons, tables,
outlines, and restrained content artwork. SF Symbols, current materials,
symbol effects, and modern navigation are enhancements only when available.

The Mac shell is not a pixel-equivalent WinForms port. It preserves the product
meaning and lets macOS place menus, Settings, sheets, shortcuts, and toolbar
commands where Mac users expect them.

## 7. SwiftUI for macOS profile

SwiftUI is a declarative implementation framework, not a separate Apple design
language and not inherently mobile. A Mac SwiftUI shell follows macOS
conventions:

- resizable desktop windows;
- menu commands and keyboard shortcuts;
- desktop-density lists and tables;
- pointer interaction;
- sidebars and split views;
- separate Settings;
- multiple windows only where they deliver real value;
- inspectors for contextual detail.

Recommended shell:

```text
sidebar or NavigationSplitView-style structure
  Instances
  Installations
  Mods
  Updates
  Accounts
  Activity
detail content
optional inspector
toolbar actions
responsive Launch Deck
Settings scene/window
```

### Deployment strategy

For an older minimum such as macOS 11:

- isolate version-dependent navigation in one shell adapter;
- use compatible navigation arrangements on older systems;
- enable newer split navigation, materials, symbols, and effects only when
  available;
- keep availability checks out of product pages;
- keep semantic page and action models independent of the container.

The modern line may raise its minimum version when newer navigation APIs become
essential. The AppKit line carries older-system coverage; SwiftUI need not
inherit every historical constraint.

Standard controls supply baseline accessibility metadata, but the profile must
still validate labels, values, actions, focus, navigation, enlarged text,
contrast, reduced motion, and VoiceOver behavior.

## 8. WinForms profile

### Interaction model

The WinForms shell follows traditional Windows desktop conventions:

- standard title bar and system menu;
- `MenuStrip` for broad command access;
- `ToolStrip` for frequent page actions;
- `StatusStrip` for persistent state;
- tabs, split containers, lists, trees, and grids;
- access keys, accelerators, visible focus, and logical tab order;
- default and cancel buttons;
- delayed commit for modal configuration;
- native file and folder dialogs;
- resizable forms and useful state restoration.

Recommended shell:

```text
MenuStrip
TabControl or classic page selector
page-specific ToolStrip
native main content
persistent Launch Deck
StatusStrip and Activity access
```

### Responsive layout

WinForms is not an absolute-layout framework. Use:

- `Dock`;
- `Anchor`;
- `AutoSize`;
- `TableLayoutPanel`;
- `FlowLayoutPanel`;
- nested bounded `UserControl` components;
- font or DPI auto-scaling;
- minimum sizes;
- proportional rows and columns.

Avoid fixed coordinate layouts, deeply nested table layouts, fixed control
heights tied to one font, clipped localized dialogs, and owner drawing when a
standard control is sufficient.

### WinForms mappings

| FacMan concept | WinForms mapping |
|---|---|
| Navigation | `TabControl` or standard-button selector |
| Installations/instances | `ListView`, `TreeView`, `DataGridView` |
| Master/detail | `SplitContainer` |
| Commands | `MenuStrip` and `ToolStrip` |
| Persistent status | `StatusStrip` |
| Settings | Resizable native form or category dialog |
| Plan review | Resizable modal form |
| Validation | `ErrorProvider` plus inline explanation |
| Long operation | Modeless Activity surface |

### DPI, accessibility, and themes

Automatic font/DPI scaling must be consistent across the form hierarchy and
tested at representative display scales. Standard controls, system fonts,
system colors, access keys, `AccessibleName`, `AccessibleDescription`,
`AccessibleRole`, and correct `TabIndex` remain the baseline.

System Native uses Windows visual styles, `SystemFonts`, `SystemColors`, native
focus, and contrast behavior. A custom dark appearance on legacy Windows would
require broad owner drawing and additional contrast work, so it is not the
official native baseline or an automatic OEM+ requirement.

## 9. WinUI 3 profile

WinUI 3 implements current Windows desktop and Fluent patterns. It is a desktop
framework that can be adaptive and touch-capable; it does not make FacMan a
mobile application.

Recommended shell:

```text
NavigationView
responsive list/detail pages
CommandBar
InfoBar
ContentDialog
contextual TeachingTip only when justified
adaptive Launch Deck
Activity center
```

Width adaptation:

```text
wide:
  navigation | list | detail or inspector

medium:
  compact navigation | content

narrow or touch:
  overlay navigation | one content page
  touch-sized primary Play action
```

### Fluent materials

- Mica is a persistent base/window material only where the Windows version
  supports it.
- Acrylic belongs to transient surfaces such as flyouts and menus.
- Smoke may emphasize a modal background.
- Solid-color fallbacks are mandatory for unsupported systems, contrast
  themes, reduced transparency, and low-resource conditions.

Do not use Acrylic as the entire application background.

Use system type resources and the current Windows type ramp rather than
hardcoding a font file and size. Use theme resources, contrast dictionaries,
UI Automation, keyboard navigation, access keys, shortcuts, and native focus.
Hardcoded colors and templates must not bypass contrast-theme behavior.

## 10. GTK 3 profile

The GTK 3 shell uses native GTK 3 behavior and selected general GNOME
principles. It does not copy GTK 4 or Libadwaita component prescriptions.
Qualification must account for GNOME, Xfce, MATE, Cinnamon, and other GTK
desktop environments.

For the classic cross-desktop X11 profile:

```text
GtkApplicationWindow
GtkMenuBar or GMenu-backed menubar
GtkNotebook or GtkStack/GtkStackSwitcher
GtkPaned and model-backed list/detail content
persistent Launch Deck
status and Activity access
```

A header-bar profile may exist for GNOME-oriented presentation. It is not the
only shell shape and is not a requirement for GTK 3.

### GTK theming

GTK user themes, fonts, focus, and control states remain authoritative for
ordinary controls. Application CSS is narrow and scoped:

```text
.facman-launch-deck
.facman-status-ready
.facman-product-banner
.facman-instance-summary
```

Do not apply global rules to `button`, `entry`, `*`, fonts, focus, or all
scrollbars. Raw user-provided GTK CSS is not a FacMan theme format.

Standard GTK widgets provide ATK-backed accessibility behavior. Custom widgets
require explicit roles, states, names, actions, relationships, keyboard
behavior, and assistive-technology validation.

## 11. Qt 6 profiles

Qt 6 is not one design system.

### Qt Widgets

Qt Widgets suits traditional dense utilities with menus, toolbars, tables,
trees, forms, keyboard/mouse interaction, multi-pane windows, and settings
dialogs. It uses layout managers and `QStyle`.

For the mandatory `1.0` Qt shell:

- use `QPalette`, `QStyle`, platform metrics, and system icons;
- use `QProxyStyle` only for narrow changes;
- avoid broad application QSS;
- preserve right-to-left and accessibility behavior.

### Qt Quick Controls and Kirigami

Qt Quick suits adaptive layouts, touch, animation, and GPU-backed
presentation. Qt Quick Controls provides multiple styles; Linux does not
automatically mean Breeze or GNOME-native.

The optional post-`1.0` modern Linux profile is Qt Quick Controls plus Kirigami
and the KDE HIG because it provides:

- adaptive desktop/narrow layouts;
- coherent KDE navigation and commands;
- C++ backend integration;
- semantic colors and units;
- KDE icon themes;
- explicit user control;
- a "simple by default, powerful when needed" product fit.

Use Qt Quick layouts, stable models, Kirigami semantic colors and units, and
platform integration. Raw QML is executable and is never a user-theme payload.

Qt high-DPI coordinates do not remove the need for correctly scaled custom
rendering and assets. Standard Widgets and Quick Controls provide accessibility
interfaces; custom controls require explicit interfaces and events.

## 12. Appearance model

Strict native behavior and arbitrary themeability cannot both be claimed. FacMan
uses three appearance modes with different promises.

### System Native

System Native is:

- always installed;
- always selectable;
- the compatibility and accessibility qualification baseline;
- the automatic fallback after theme failure;
- available through a startup safe-mode mechanism.

It uses:

- system window chrome;
- system menus and dialogs;
- system fonts and control metrics;
- system focus, selection, and input behavior;
- system light, dark, and high-contrast behavior where supported;
- system icon roles;
- no custom control painting unless technically necessary and justified.

### OEM+

OEM+ is the preferred FacMan product identity where its profile is qualified.
It retains native controls and behavior while branding bounded product
surfaces:

- application icon;
- page header or product banner;
- product accent where the platform permits it;
- selected-instance and modpack artwork;
- empty-state illustrations;
- status badges and product-specific status symbols;
- Launch Deck;
- update illustration;
- About surface;
- optional bounded content texture.

OEM+ may be the normal first-run appearance only when System Native remains
immediately available and the profile passes the same accessibility and
interaction checks. OEM+ is not a full custom repaint of the toolkit.

### Custom theme

Custom themes are optional, data-only packages. They are not described as
strictly native. They must preserve:

- accessible names and roles;
- keyboard and pointer behavior;
- visible focus;
- status meaning through text, icon, role, and color;
- warning and confirmation prominence;
- readable contrast;
- safe-mode recovery.

An invalid theme is rejected. Accessibility failure is not accepted as user
choice.

### Qualification claims

| Mode | Native interaction claim | Accessibility claim | Brand customization | Safe-mode role |
|---|---|---|---|---|
| System Native | Strongest | Release baseline | Minimal | Recovery target |
| OEM+ | Native controls with bounded brand | Must equal baseline before support | Product surfaces | Falls back to System Native |
| Custom theme | No strict native-appearance claim | Mandatory validation constraints | Allowlisted tokens/assets | Bypassed in safe mode |

## 13. Semantic theme system

Theme resolution order is:

```text
platform-native defaults
  -> FacMan semantic branding
  -> permitted user-theme tokens and assets
  -> platform capability adaptation
  -> accessibility, contrast, motion, and transparency enforcement
```

Later stages always win. A theme cannot override accessibility enforcement or
claim an unsupported platform capability.

### Token vocabulary

The initial semantic token vocabulary is:

```text
color.window
color.content
color.surface
color.selection

color.text.primary
color.text.secondary
color.text.disabled
color.link

color.accent.product
color.accent.interactive

color.status.ready
color.status.warning
color.status.blocked
color.status.error
color.status.running
color.status.recovery

metric.density
metric.group_spacing
metric.content_spacing
metric.corner_emphasis

motion.enabled
motion.short_duration
motion.long_duration

icon.play
icon.install
icon.instance
icon.mods
icon.account
icon.activity
icon.warning
icon.recovery
```

Token values may be:

```text
native
inherit
product-default
explicit-value
```

Ordinary control tokens remain `native` by default.

### Platform mapping

| Profile | Native mapping |
|---|---|
| AppKit | Semantic `NSColor`, system fonts, template images |
| WinForms | `SystemColors`, `SystemFonts`, Windows visual styles |
| GTK 3 | Theme style context plus narrowly scoped classes |
| WinUI 3 | `ThemeResource`, accent resources, contrast dictionaries |
| SwiftUI | Semantic `Color`, environment values, system symbol roles |
| Qt Widgets | `QPalette`, `QStyle`, platform icon theme |
| Kirigami | `Kirigami.Theme`, standard units, KDE icon themes |

The cross-platform format stores meaning. It does not store platform CSS, QSS,
XAML, QML, Swift, C#, Objective-C, or widget templates.

### Theme package

Proposed package:

```text
theme/
  manifest.toml
  tokens.json
  icons/
  artwork/
  licenses/
```

Manifest:

```text
theme_id
version
schema_version
author
license
supported_shell_profiles
required_capabilities
fallback_theme
asset_hashes
maximum_asset_dimensions
maximum_total_size
```

Theme packages may not contain:

- C#, Swift, Objective-C, JavaScript, QML, or native code;
- arbitrary XAML;
- raw GTK CSS;
- unrestricted Qt style sheets;
- remote URLs;
- executable commands;
- dynamic libraries;
- shell scripts;
- arbitrary layout replacements;
- unbounded SVG or image features;
- path traversal or external references.

Platform-specific semantic token overrides may be accepted. Platform-specific
executable styling is not.

### Theme validation and safe mode

At startup:

1. Parse and version-check the manifest.
2. Validate supported profiles and required capabilities.
3. Validate paths, hashes, formats, dimensions, and total size.
4. Reject traversal, links, remote references, and prohibited content.
5. Decode within explicit time, memory, and pixel budgets.
6. Construct an isolated staging representation.
7. Enforce platform and accessibility overrides.
8. Activate atomically only after validation.
9. Fall back to System Native on any failure.
10. Record a bounded failure without loading the same crashing theme again.

A startup modifier or recovery file bypasses all custom themes. Theme failure
must not prevent access to Activity, diagnostics, Settings, or recovery.

The existing `facman.ui.theme.v1` files are implementation reality, not proof of
this future package contract. `THEME-V1-01` owns schema, migration, capability,
budget, and safe-mode decisions.

## 14. Extensibility trust classes

“Mod” is not an acceptable umbrella term for every extension.

### Game-content mods

Factorio mods, modpacks, and modset locks are product content managed by the
Factorio binding. They do not execute inside FacMan.

### Themes

Themes are declarative visual tokens and assets. They have no command,
filesystem, network, setup, process, or credential authority.

### Presentation contributions

Presentation contributions are declarative additions such as:

```text
navigation item
resource list
detail section
settings section
status card
form
action shortcut
diagnostic renderer
```

They reference only registered data sources, actions, commands, schemas,
localization keys, and icon roles. They cannot provide arbitrary in-process
code, invent operation semantics, or bypass admission.

### Provider connectors

Mod Portal, package-source, account, external-store, and remote-server
connectors should eventually be out-of-process and capability-scoped. A
connector receives only minimum ports and never acquires setup, process, or
raw-credential authority.

### First-party static modules

Trusted product functionality compiled into the FacMan composition remains the
primary v1 extension mechanism.

Each class has its own schema, capability set, lifecycle, evidence, and
revocation. Promoting one class does not authorize another.

## 15. Frontend authority and action safety

A frontend never implements an authority-bearing operation:

```text
user selects semantic action
  -> shell submits registered command and context
  -> admission validates capabilities, freshness, and effects
  -> permanent owner creates an exact plan
  -> shell renders structured plan review
  -> user confirms
  -> authority provider independently revalidates
  -> operation receives durable identity
  -> shell observes progress and events
  -> terminal outcome or specific recovery requirement
```

The shell may:

- collect intent;
- display state, freshness, evidence, effects, and refusal;
- collect typed input and confirmation;
- request cancellation by operation identity;
- display progress, terminal outcomes, and recovery.

The shell may not:

- issue setup authority;
- construct raw process commands;
- edit installation files;
- store account secrets;
- reinterpret an unknown outcome as success;
- skip plan review because a theme or contribution requests it;
- infer cancellation from a closed window or disconnected transport.

Remote content is sanitized data. It never executes in the privileged launcher
process.

## 16. Performance architecture

The UI process owns:

- rendering;
- input and focus;
- native shell integration;
- bounded presentation-state caching;
- lightweight sorting and filtering.

Application services own:

- filesystem scanning;
- archive inspection and decoding;
- hashing;
- dependency resolution;
- network access;
- setup planning;
- process supervision;
- support-bundle creation.

### Immutable snapshots

Presentation snapshots include:

```text
revision
resource identity
freshness
page state
selection
available actions
operation references
```

The shell replaces or diffs snapshots. It does not recompute domain truth.

### Lazy and incremental work

- Construct pages on first use.
- Make the initial shell interactive before loading news.
- Load images on demand.
- Query large collections incrementally.
- Bound Activity history and logs.
- Do not parse an entire log when one line arrives.
- Do not recompute all instances for one unrelated change.
- Cancel obsolete presentation queries by identity.

Use toolkit model/view or virtualization:

- AppKit table/outline data sources;
- WinForms virtual list/grid modes;
- GTK list/tree models;
- WinUI virtualized collection controls;
- SwiftUI `List` or `Table` with stable identity;
- Qt `QAbstractItemModel` and incremental `fetchMore()`.

### Live console

The console uses:

```text
bounded ring buffer
structured event store
severity and category filtering
batched UI updates
pause auto-scroll
event coalescing
disk retention policy
```

Do not append every byte directly to a rich-text control on the UI thread.

### Embedded web content

The classic shell must not require Chromium to display news. Use a structured,
sanitized, cached feed and open full articles in the system browser. This
reduces startup time, memory, package size, attack surface, and old-system
compatibility burden.

## 17. Reliability and recovery

Every long-running action carries:

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

Frontend lifecycle policy:

| Event | Required behavior |
|---|---|
| Page closes | Operation continues or receives an explicit cancellation request by ID |
| Main window closes during game | Configured launcher behavior applies; supervision remains truthful |
| Frontend crashes | Durable operation remains inspectable |
| Transport times out | Outcome becomes unknown or recovery-required, never implicitly cancelled |
| Theme fails rendering | Restart or recover in System Native safe mode |
| Backend unavailable | Existing state remains readable; actions show structured unavailability |
| Workspace changes | Snapshot and dependent plans become stale |
| Installation changes externally | Readiness and launch plans become stale |

Transport order:

1. direct transport for normal native shells;
2. process RPC for compatibility and diagnostics;
3. persistent local service only if evidence proves operations must outlive
   frontends or serve multiple clients.

Do not introduce a daemon for symmetry.

## 18. Accessibility is a release property

Every supported shell proves the same primary journey with its platform
accessibility stack. Required checks include:

```text
keyboard-only navigation
screen reader
system high-contrast or contrast theme
large fonts or text scaling
200% display scaling
right-to-left layout
reduced motion
reduced transparency where supported
color-blind-safe status
visible focus
logical tab order
accessible operation announcements
```

Platform validation:

| Platform | Required primary tools |
|---|---|
| macOS | VoiceOver and Accessibility Inspector |
| Windows | Narrator, Accessibility Insights, contrast themes |
| GTK | Orca, AT-SPI/ATK, and a high-contrast theme |
| Qt/KDE | Qt accessibility bridge with Orca/AT-SPI |

Automated checks do not replace manual validation of the release-blocking
positive and failure journeys.

Readiness is never green alone. Warning is never yellow alone. Failure is never
red alone. Every semantic status has text, icon, role, and accessible state.

Custom controls require explicit accessibility and performance justification,
native role mapping, keyboard behavior, focus behavior, scaling evidence, and
assistive-technology evidence.

## 19. FacMan visual identity

Keep native:

- title bar and window controls;
- menu bar;
- file and folder pickers;
- checkboxes and radio buttons;
- text boxes and combo boxes;
- scrollbars;
- focus rings;
- list/table selection;
- context menus;
- dialog ordering;
- keyboard behavior.

Brand in OEM+:

- application icon;
- Home or page header;
- instance artwork;
- Launch Deck;
- product accent;
- status symbols;
- empty states;
- modpack artwork;
- update illustration;
- About window;
- optional bounded content texture.

Avoid:

- custom window chrome;
- fake platform controls;
- universal custom scrollbars;
- custom-drawn text entry;
- full-window textures behind dense text;
- platform-inappropriate button order;
- one font forced onto every OS;
- replacing familiar system commands with one custom icon set;
- one fixed spacing scale imposed on all toolkits;
- animation that changes workflow meaning;
- decorative materials without solid, contrast, and reduced-transparency
  fallbacks.

## 20. Enforceable architecture invariants

1. No toolkit type crosses the presentation boundary.
2. No frontend directly accesses installation, setup, process, or credential
   authority.
3. Every frontend action maps to a registered semantic action or command.
4. Every supported command has normalized result and refusal semantics across
   transports.
5. Primary journeys use hand-designed native views; generic forms remain
   Advanced.
6. System Native is always available and cannot be removed by a theme.
7. Themes contain data and bounded assets only, never executable code.
8. Accessibility, high contrast, reduced motion, and reduced transparency
   override theme choices.
9. Platform-specific command placement is allowed; semantic identity remains
   stable.
10. Literal shortcuts and button ordering belong to platform adapters.
11. Unsupported visual capabilities degrade without changing workflow
    semantics.
12. Remote content cannot execute within the privileged launcher process.
13. Closing a window or transport does not imply operation cancellation.
14. Custom controls require explicit accessibility and performance evidence.
15. Classic compatibility and modern development remain separate
    qualification lanes.
16. Framework name alone never implies a design language, platform tier, or
    capability.
17. OEM+ branding may style bounded product surfaces but may not replace native
    control behavior.
18. Themes, presentation contributions, provider connectors, game mods, and
    first-party static modules remain separate trust classes.
19. An accessibility failure invalidates an appearance-mode qualification.
20. A theme failure must be recoverable without loading that theme.

These rules should become lint, schema, conformance, or journey checks as the
relevant contracts mature.

## 21. Smallest useful implementation program

The program is staged so interface ambition does not expand C1.

### Stage 1 — minimal semantic UI core

Owned by `INSTANCE-VIEW-MINIMUM-01` after C1 definition:

```text
NavigationNode
InstanceListView
InstanceSummaryView
ReadinessView
LaunchDeckView
ActionDescriptor
OperationView
RecoveryView
ThemeCapabilities
```

Build one hand-designed reference GUI for C1. Do not design every future page.

### Stage 2 — classic component galleries

Owned by `FACMAN-C1P` after reference-GUI proof. Build a gallery for WinForms,
AppKit, and GTK 3 proving:

- native controls;
- layout resizing;
- DPI and text scaling;
- localization expansion;
- keyboard focus and command access;
- accessibility metadata;
- System Native and bounded OEM+;
- theme failure and safe mode;
- readiness, operation, refusal, and recovery states.

The gallery is evidence, not a product shell.

### Stage 3 — three-platform classic journey

Implement the same fixture-backed semantic journey:

```text
open FacMan
  -> list instances
  -> select instance
  -> display exact environment
  -> show readiness
  -> preview Play
  -> execute fixture process or show refusal
  -> display Activity
  -> complete or recover
```

Run the positive and paired failure path on WinForms, AppKit, and GTK 3. Record
native adaptations rather than chasing pixel identity.

### Stage 4 — theme v1

Owned by `THEME-V1-01`. Permit:

- semantic colors;
- product icon roles;
- bounded artwork;
- density preference;
- bounded platform token overrides.

Defer:

- arbitrary layouts;
- scripts or code;
- raw CSS, QML, XAML, or QSS;
- custom fonts;
- custom controls.

### Stage 5 — classic page expansion

Expand only after the primary semantic journey is stable:

```text
Instances
Activity and Recovery
Installations
Mods
Updates
Accounts
Home
Settings
```

Each page earns shared records through concrete cross-shell pressure.

### Stage 6 — optional modern projections

Owned by `MODERN-PROJECTIONS-01` after C1P and theme v1:

```text
WinUI 3
SwiftUI for macOS
Qt Quick Controls + Kirigami
```

The optional modern line is adaptive, touch-capable, responsive, and
material-aware. It is a second native projection of stable semantics, not a
reskinned classic shell, and does not replace the mandatory Qt Widgets `1.0`
projection.

### Presentation contributions

`PRESENTATION-CONTRIBUTIONS-01` remains Later until a real consumer proves that
first-party static composition is insufficient. It must not become a pre-C1
plugin framework.

## 22. Qualification evidence

A shell/profile is not supported because it builds. Qualification records:

- profile identity and capability manifest;
- framework, OS, architecture, package, and composition identity;
- HIG/convention review;
- System Native screenshot and interaction evidence;
- OEM+ deltas and native-control inventory;
- appearance safe-mode proof;
- positive and paired failure journey results;
- keyboard-only result;
- screen-reader result;
- scaling and localization result;
- contrast, motion, and transparency result;
- operation-lifecycle and frontend-crash result;
- large-list and live-console performance result;
- support owner and known exclusions.

Theme evidence records manifest/schema identity, asset hashes, decode budgets,
path and external-reference rejection, prohibited-content rejection, fallback,
crash-loop prevention, accessibility overrides, and platform-token mapping.

Any change to the semantic contract, shell adapter, toolkit version, platform
capability, theme schema, package composition, or accessibility mapping
invalidates affected evidence.

## 23. C1 boundary

This design does not add six release GUIs to C1.

C1 requires:

- CLI plus one hand-designed reference GUI;
- one selected framework/HIG/platform capability profile;
- shared semantic actions and immutable snapshots for the primary journey;
- native controls and platform conventions;
- System Native recovery appearance;
- bounded OEM+ only if qualified;
- keyboard, names/roles, focus, scaling, and contrast checks appropriate to the
  selected lane;
- truthful operation and recovery behavior.

C1 excludes:

- classic three-platform parity;
- modern shells;
- arbitrary or executable themes;
- presentation contribution frameworks;
- custom controls without necessity;
- a universal widget abstraction;
- pixel-identical cross-platform presentation.

C1P owns classic three-platform semantic parity. Theme v1 follows stable
classic evidence. Modern projections follow stable semantics and appearance
contracts.

## 24. Reference authorities

These primary authorities informed this policy:

- [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)
- [AppKit documentation](https://developer.apple.com/documentation/appkit)
- [SwiftUI documentation](https://developer.apple.com/documentation/swiftui)
- [Windows desktop application design](https://learn.microsoft.com/windows/apps/design/)
- [WinForms desktop guidance](https://learn.microsoft.com/dotnet/desktop/winforms/)
- [WinUI 3 documentation](https://learn.microsoft.com/windows/apps/winui/winui3/)
- [GNOME Human Interface Guidelines](https://developer.gnome.org/hig/)
- [GTK 3 documentation](https://docs.gtk.org/gtk3/)
- [KDE Human Interface Guidelines](https://develop.kde.org/hig/)
- [Qt Widgets documentation](https://doc.qt.io/qt-6/qtwidgets-index.html)
- [Qt Quick Controls styles](https://doc.qt.io/qt-6/qtquickcontrols-styles.html)
- [Qt accessibility](https://doc.qt.io/qt-6/accessible.html)

Framework and platform documentation evolves. A profile must pin the exact
minimum OS, framework/toolchain, design guidance revision where material, and
capability evidence used for its release claim.
