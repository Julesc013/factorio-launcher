# Root Ownership

`source/` is retired. Private implementation belongs under ownership roots:
`runtime/` for reusable/product implementation and `apps/` for thin frontend
entrypoints.

## Root Rules

- `include/flb/` owns only the Factorio binding public C ABI.
- `runtime/factorio/` owns Factorio-specific discovery, validation, launch
  templates, instance templates, mods, modsets, saves, servers, Mod Portal
  behavior, account redaction, and diagnostics.
- `runtime/client/` owns frontend-neutral command clients and transports.
- `runtime/package/` owns package/runtime location and component verification.
- `runtime/platform/` owns low-level platform adapters.
- `apps/` owns frontend entrypoints and presentation shells.
- `apps/gui/` owns OS-first GUI shells:
  `windows/{winforms,winui}`, `macos/{appkit,swiftui}`, and `linux/{gtk,qt}`.
- `content/factorio/` owns product templates, discovery rules, launch
  templates, instance templates, redaction rules, and policy.
- `contracts/` owns ABI, command, schema, policy, diagnostic, result, and
  refusal contracts.
- `release/` owns package manifests and release profiles.
- `release/profiles/` owns named target lanes such as
  `windows_legacy_winforms`, `macos_legacy_appkit`, `linux_x11_gtk`,
  `linux_wayland_qt`, and `portable_cli`.

Runtime module names are product domains, not language standards. Do not create
`runtime/factorio/c11`, `runtime/factorio/cpp11`, or similar buckets. Put files
under the domain they implement, such as `discovery/`, `install_validation/`,
`launch/`, `mods/`, `modsets/`, or `mod_portal/`.

## Cross-Repo Boundary

Universal setup owns install mutation:

```text
install
verify
repair
uninstall
stage / commit / rollback
installed-state manifests
setup audit
```

Universal launcher owns cross-product orchestration:

```text
products
install references
instances
profiles
accounts
launch plans
command graph
dry-run / audit / diagnostics
daemon protocol
frontend-neutral command client contracts
```

Factorio launcher owns only Factorio product behavior and Factorio-facing app
frontends.

## Forbidden Shapes

Do not create:

```text
source/
src/
data/
schemas/
packaging/
launcher/
product/
universal/
apps/*/src/
apps/*/source/
runtime/*/source/
runtime/**/c11/
runtime/**/cpp11/
apps/appkit/
apps/gtk/
apps/qt/
apps/winforms/
apps/gui/win32/
apps/gui/appkit/
apps/gui/gtk/
apps/gui/qt/
```

Do not reintroduce `include/usk`, `include/ulk`, `runtime/usk`, or
`runtime/ulk` in this repository. Those belong to `universal-setup` and
`universal-launcher`.

## Enforcement

Run:

```powershell
python tools\structure_policy_check.py
python tools\strict_check.py
```

The structure checker enforces the closed root model, retired-root absence,
content/code separation, Factorio-only public ABI headers, required app roots,
and the Factorio binding/contract spine.
