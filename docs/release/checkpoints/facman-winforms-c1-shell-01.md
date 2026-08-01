# FacMan WinForms C1 shell closeout

Date: 1 August 2026

WorkUnit: `FACMAN-WINFORMS-C1-SHELL-01`

Branch: `task/facman-winforms-c1-shell-01`

Base: `94fd1b9565c300bbc0e274f8d40083d967c367db`

## Result

The supported Windows 10/11 x64 reference presentation now opens on a native
four-page shell instead of the generated command catalog. Instances,
Installations, Activity, and Settings/About consume all five deterministic
`facman.presentation.v0` records. The persistent Launch Deck exposes current
readiness, exact structured refusal, running/exited state, Last Run, relaunch,
and exact interruption/recovery identities. The existing generated explorer is
retained only under Advanced.

The shell uses access keys, `Ctrl+1` through `Ctrl+5` navigation, native focus
order, accessible names/descriptions, state announcements, System Native
controls/colors/font, DPI autoscaling, and a Per-Monitor V2 manifest. Its x64
.NET Framework 4.8 project compiles locally with no warnings.

`tools/build_winforms_c1_portable.py` constructs a deterministic, unsigned,
unpublished portable ZIP prototype. Embedded fixtures keep its product pages
relocatable. An optional colocated CLI supports the unchanged bounded process
RPC Advanced path; its absence produces the existing structured frontend
refusal.

## Authority boundary

The player-facing path is fixture-only. It starts no Factorio process, changes
no qualified runtime identity, and grants no live Play, route, permit,
observer, verdict, promotion, publication, daemon, direct-client, transport
rewrite, setup mutation, or Universal Launcher ABI authority. The product
reference lane and live acceptance evidence remain separate truths.

## Evidence

```text
apps/gui/windows/winforms/C1ShellForm.cs
apps/gui/windows/winforms/C1Presentation.cs
apps/gui/windows/winforms/app.manifest
docs/product/facman_winforms_c1_shell.md
tools/facman_winforms_c1_check.py
tools/winforms_c1_runtime_smoke.py
tools/build_winforms_c1_portable.py
tests/test_facman_winforms_c1_shell.py
```

## Validation

```text
x64 .NET Framework 4.8 rebuild           PASS
WinForms C1 semantic/source check         PASS (5 states)
WinForms executable renderer smoke        PASS (5 states)
portable ZIP determinism and boundary     PASS
focused WinForms C1 unit tests            PASS
existing GUI surface check                PASS
existing operational UX check             PASS
presentation and fixture-journey checks   PASS
canonical plan generation/check           PASS
```

The portable AIDE Lite task helpers report the expected missing queue surfaces
because target `.aide/queue/` WorkUnit state is intentionally absent. This does
not broaden evidence. Hosted CI, PR integration, interactive assistive-
technology checks, visual review at 100/150/200%, signing, and publication
remain separate repository or release decisions.

The broader local obligation runner exercised 578 tests but is not a green
release proof in this isolated worktree: the native `build/native-smoke`
artifacts and exact sibling Universal Launcher/Setup workspaces are absent. Its
failures are confined to those established package, cross-repository,
dependency-pin, architecture-budget, and strict-check prerequisites. The
focused WinForms, presentation, journey, plan, target-truth, source-format,
schema, security, and AIDE Lite validations above are green.
