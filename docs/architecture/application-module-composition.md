# Application module composition

FacMan's Factorio application boundary is a composition root, not a product
command dispatcher.

After the boundary decodes one typed request, it performs the shared checks in
this order:

1. find the owning static application module;
2. require a workspace when the selected command needs one;
3. refuse persistent writes requested as dry runs;
4. apply the global effect and capability admission policy;
5. delegate to exactly one module;
6. serialize the shared result envelope.

The registered modules are:

| Module | Factorio-owned responsibility |
| --- | --- |
| `WorkspaceApplicationModule` | Product inspection, workspace projections, preferences, onboarding and doctor projections |
| `SetupApplicationModule` | Typed passage to the Universal Setup gateway |
| `InstallationApplicationModule` | Discovery and Factorio installation-reference interpretation |
| `InstanceApplicationModule` | Instance records, lifecycle and import/export |
| `ProfileApplicationModule` | Templates and Factorio profile composition |
| `ContentApplicationModule` | Snapshots, mods, modsets, saves and servers |
| `RecoveryApplicationModule` | FacMan workspace journal recovery and schema migration |
| `DiagnosticsApplicationModule` | Diagnostic export/redaction and typed development refusals |
| `LaunchApplicationModule` | Factorio launch planning, preflight and guarded execution |

`ApplicationModule` is an internal static seam. It does not create a plug-in
ABI, move install-mutation authority out of Universal Setup, or make
Factorio-specific handlers part of Universal Launcher.

Denied admission normally stops at the composition root. The two deliberate
exceptions are:

- launch commands, so the launch module can return the established
  plan-bound execution refusal;
- Mod Portal commands, so the content module can return the established
  network-policy refusal.

The structural validator rejects direct `CommandId` cases in
`flb_factorio_application.cpp`, unregistered modules, and missing
command-family route anchors.
