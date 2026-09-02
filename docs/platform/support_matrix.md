# Platform Support Matrix

Repository-status reference date: 2026-09-02. External platform-source prose
was last reviewed on 2026-07-08 and does not itself grant a support claim.

Launcher support and Factorio runtime support are separate promises:

- launcher OS support: where FacMan itself can run
- Factorio runtime support: where the selected Factorio version can run
- managed instance support: where FacMan can safely isolate instances
- upstream support: what Wube currently documents for Factorio

FacMan app mode is also separate from Factorio install origin. Portable,
user-installed, and system-installed FacMan packages should expose the same
command graph where platform authority allows it. See
[../product/install_distribution_modes.md](../product/install_distribution_modes.md).

The first three evidence rows are exact-receipt-bound current whole-product
candidates. Machine qualification is recorded; human install, accessibility,
performance, real Play, publication, and support authority remain pending.
Remaining rows are legacy, component, compatibility, or laboratory evidence
lanes; they are not additional current product downloads.

<!-- FACMAN-SUPPORT-STATUS:BEGIN -->
## Current Proven Status

Compile, runtime, package, publication, and support are independent claims. The evidence revision is blank where no proof is claimed.

| Platform | Compile | Runtime | Package | Publication | Support | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| `windows_product_x64` | baseline_passed | exact_candidate_machine_qualified | exact_candidate_qualified | unpublished | unsupported_candidate_pending_manual_test | `a7a518dbfe2a6d54da7b9c84fbd318300265e31d` |
| `macos_product_x64` | baseline_passed | machine_qualified_preview_pending | exact_candidate_qualified_semantic_preview_pending | unpublished | unsupported_experimental_preview | `a7a518dbfe2a6d54da7b9c84fbd318300265e31d` |
| `linux_product_x64` | baseline_passed | machine_qualified_preview_pending | exact_candidate_qualified_semantic_preview_pending | unpublished | unsupported_experimental_preview | `a7a518dbfe2a6d54da7b9c84fbd318300265e31d` |
| `linux_portable_cli_x64` | passed | passed | passed | unpublished | candidate | `d00456069eb509eabf6a63f831aadbd19813413f` |
| `macos_portable_cli_x64` | passed | passed | passed | unpublished | candidate | `d00456069eb509eabf6a63f831aadbd19813413f` |
| `windows_portable_cli_x64` | passed | passed | passed | unpublished | candidate | `d00456069eb509eabf6a63f831aadbd19813413f` |
| `windows_portable_tui_x64` | passed | passed | passed | unpublished | candidate | `d00456069eb509eabf6a63f831aadbd19813413f` |
| `linux_portable_tui_x64` | passed | passed | passed | unpublished | candidate | `d00456069eb509eabf6a63f831aadbd19813413f` |
| `macos_portable_tui_x64` | passed | passed | passed | unpublished | candidate | `d00456069eb509eabf6a63f831aadbd19813413f` |
| `windows_legacy_winforms_x64` | passed | passed | contract_only | unpublished | experimental | `d00456069eb509eabf6a63f831aadbd19813413f` |
| `macos_legacy_appkit_x64` | passed | not_proven | contract_only | unpublished | experimental | `a40301ccfa57dfbf5ca057784022cd127ddbc539` |
| `linux_x11_gtk_x64` | passed | not_proven | contract_only | unpublished | unavailable | `a40301ccfa57dfbf5ca057784022cd127ddbc539` |
| `portable_cli_x64` | passed | contract_tested | contract_only | unpublished | experimental | `d00456069eb509eabf6a63f831aadbd19813413f` |
| `portable_tui_x64` | opt_in_only | not_proven | not_built | unpublished | experimental | `-` |

Status alias: `machine_qualified_preview_pending` means `exact_candidate_machine_qualified_semantic_preview_pending`.
<!-- FACMAN-SUPPORT-STATUS:END -->

## Design Targets, Not Current Support Claims

The table below records product direction only. It does not override the
evidence-backed status table above.

| Platform | Support level | Artifact |
| --- | ---: | --- |
| Windows 10/11 x64 WinForms | 0.1 beta reference candidate | portable ZIP + setup EXE |
| Windows modern WinUI | Post-beta admission | installer + portable ZIP |
| macOS Intel AppKit | 0.1 beta experimental preview | x86_64 ZIP + pkg |
| macOS modern SwiftUI | Post-beta admission | signed/notarized universal `.app` |
| macOS 10.10-10.12 Intel | Experimental legacy | CLI/basic GUI only if tested |
| macOS 10.9 | Not primary | source/experimental only |
| Ubuntu 24.04 x64 GTK3/X11 | 0.1 beta experimental preview | tar.zst + `.run` |
| Linux Wayland Qt | Post-beta admission | GUI tarball/AppImage profile |
| Linux old desktop/server | Best-effort | portable CLI/TUI tarball |
| Linux 2010-era GUI | Experimental | source build or special legacy AppImage |

## Windows

Microsoft documents .NET Framework 4.8 as separately installable on Windows 7
SP1, but also marks Windows 7 as out of support. Therefore Windows 7 SP1 is a
best-effort launcher target, not a modern security-support target.

Reference:
https://learn.microsoft.com/en-us/dotnet/framework/get-started/system-requirements

## macOS

Apple's Xcode support matrix currently shows modern Xcode 26.x deployment
targets down to macOS 11, while Xcode 15.4 and 16.x-era rows include deployment
target support down to macOS 10.13. Therefore macOS 10.13 support needs a
pinned legacy Xcode/toolchain lane.

Reference:
https://developer.apple.com/support/xcode/

## Linux

AppImage is a good one-file Linux UX, but it is not a magic compatibility
guarantee. AppImage guidance says the payload must avoid compiled-in absolute
paths, bundle dependencies missing on target systems, be built on a base system
no newer than the oldest target, and be tested on those base systems.

Reference:
https://docs.appimage.org/reference/best-practices.html

## Factorio Runtime

Wube's current FAQ lists Factorio support for Windows 10/11, OS X 10.10
Yosemite or newer, Linux tarball installation, and a 64-bit OS requirement.
Launcher support for older systems does not imply current Factorio support on
those systems.

Reference:
https://factorio.com/support/faq
