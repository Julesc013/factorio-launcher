# FacMan classic preview runtime and package qualification

`C1-PREVIEW-RUNTIME-PACKAGES-01` turns the AppKit and GTK source prototypes
into native-host evidence. It does not change the Windows WinForms reference
lane and cannot authorize live Play or stable platform support.

## Evidence model

Both hosted jobs emit a strict
`facman.classic_preview_package_proof.v1` record, a deterministic frontend-only
prototype `tar.gz`, and an adjacent SHA-256 file. The proof rejects a dirty
worktree and records `source_dirty: false` beside the exact revision. It binds
runner, binary identity, architecture, frontend dependency closure, deployment
floor, native runtime probe, relocated runtime probe, prototype manifest, and
artifact checksum. Every current record is `provisional` and non-promoting.

These archives do not satisfy the referenced full release profiles. They omit
the FacMan CLI/backend, TUI/daemon, Universal libraries, product contracts and
content, and required license bundle. RPC uses an external test fixture that is
not shipped. Accordingly the record says `artifact_scope:
frontend_only_prototype`, `profile_contract_satisfied: false`, and
`clean_machine_backend_closure: false`. It is not clean-machine product-package
evidence.

The in-application probes exercise native controls instead of substituting a
Python UI model. They cover the five shell surfaces, menu accelerators,
keyboard focus restoration, resize behavior, System Native/OEM+ appearance
recovery, accessible names/roles, the deterministic positive/refused/running/
exited/relaunch/interrupted/recovery journey, exact `stale_readiness`, and a
real `rpc --stdio` child process. The child is a deterministic protocol fixture,
not Factorio and not live Play.

## AppKit lane

The macOS Intel job uses the AppKit-local CMake project to produce and execute
`FacMan.app`. Qualification rejects any architecture other than x86_64, a
deployment floor other than macOS 10.13, `LC_RPATH`, or a non-system dynamic
dependency. It runs the bundle from its build location and again after copying
it beneath a Unicode path with spaces. The probe verifies Command-0 through
Command-5 menus, resize, focus and frame restoration, AppKit accessibility,
appearance recovery, fixture states, and bounded RPC.

Signing and notarization are not implemented in pull-request-controlled proof
code and ordinary CI receives no credentials. Evidence records `not_requested`;
it cannot imply a signature, notarization, publication, stable support, or live
Play. A future credential operation requires a separately reviewed, protected
manual workflow consuming reviewed exact-head artifacts.

The `macos-15-intel` runner label does not pin an exact legacy Xcode/SDK/clang
closure. The proof records the observed Xcode identity but marks the mutable
toolchain as a completion blocker. AppKit cannot leave provisional status until
an exact supported legacy toolchain is reviewed and pinned.

## GTK lane

The Linux job builds GTK 3 with Meson, installs it at the profile entrypoint
`usr/bin/facman-gui-gtk`, and runs the installed binary beneath Xvfb and a DBus
session. Each run first removes any stale liveness marker. Orca must still be
alive after an independent AT-SPI client finds the running FacMan window,
Launch Deck name/role, and Play button name with `push button` role. Local ATK,
the accessibility bus, and HighContrast checks remain additional signals. The
installed frontend tree is copied beneath a Unicode path and rerun.

The proof rejects unresolved `ldd` entries and any ELF RPATH/RUNPATH. A second
RPC fixture deliberately spawns a descendant and hangs. The GTK client starts
the RPC child in a distinct process group; its bounded timeout must report
`outcome_unknown` and terminate the whole fixture process tree. The deterministic
tarball carries a complete per-file SHA-256 manifest and an external artifact
checksum. Checksum signing is deferred; the record says `signing:
not_requested` and `signature_file: null`. Ordinary CI stays green while the
artifact remains explicitly provisional and non-promoting.

## Claim gate

The WorkUnit remains `active`. Current evidence can support implementation
diagnostics only: provisional compile, frontend fixture runtime, frontend-only
prototype packaging, provisional accessibility, and unavailable support.
Completion additionally needs a protected trusted signing path, full required
profile closure, clean-machine backend execution, and an exact reviewed AppKit
toolchain pin.

It does not establish older OS/distribution coverage, screen-reader usability,
signed/notarized availability when credentials were absent, publication,
support SLA, stable support, route authority, or live Play.
No current record can update runtime, product-package, accessibility, or support
claims.
