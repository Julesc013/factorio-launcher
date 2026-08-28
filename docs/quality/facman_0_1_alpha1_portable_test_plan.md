# FacMan 0.1.0-alpha.1 final-dev portable test plan

This plan qualifies the exact post-closeout protected `dev` packages. It does
not authorize a tag, signing, publication, support, a real Factorio run, or a
human verdict. The supplied external plan and template hashes were unavailable
in this workspace; these repository-owned materials are therefore new bounded
records and must not be represented as byte-identical copies of them.

## Freeze the candidate

1. Dispatch the manual `alpha-release` workflow with `operation=qualify` and
   the exact protected `dev` revision.
2. Retain `facman-alpha-1-machine-assets` and
   `facman-alpha-1-qualification-evidence` from the same successful run.
3. Confirm `three-root-qualification.v1.json` is schema-valid, records three
   fresh roots with no mismatches, and binds the exact source SHA/tree,
   ULK/USK SHA/tree/package/ABI/contract identities, contract-set digest,
   `facman.workspace.v1`, package-tree/archive/manifest/SBOM/provenance/licence
   digests, file count, uncompressed bytes, and archive bytes for:

   - `facman-0.1.0-alpha.1-windows-cli-x64-portable.zip`
   - `facman-0.1.0-alpha.1-windows-tui-x64-portable.zip`
   - `FacMan-0.1.0-alpha.1-windows-x64-portable.zip`

4. Create the no-clobber pending human packet:

   ```powershell
   py -3 tools/alpha_portable_test_packet.py --bind `
     --qualification-root <qualification-root> `
     --machine-root <machine-asset-root> `
     --output <evidence-root>/facman-0.1.0-alpha.1-human-test-receipt.v1.json
   ```

5. Verify the bound packet again before and after copying the artifacts:

   ```powershell
   py -3 tools/alpha_portable_test_packet.py `
     --verify-bound <receipt> `
     --qualification-root <qualification-root> `
     --machine-root <machine-asset-root>
   ```

The qualification and machine-asset artifacts may be downloaded to new,
separate directories. Packet binding verifies each archive and sidecar against
the durable qualification record, including the embedded package and hash
manifests; it does not depend on runner-local paths captured during the build.

The Windows classification is `Windows 10/11 x64`, unsupported, unsigned,
unpublished, portable alpha. Accepted real Play routes remain zero.

## Windows product lane

Run CLI JSON journeys for version/help, Doctor/status, workspace
open/create/inspect, discovery, installation identity/ownership/read-only
registration, instance create/select/inspect, profile/configuration/content/save
inspection, readiness, presentation query/action, operation inspect/cancel,
Last Run, recovery, package verification, and support bundle. Every invocation
must emit one structured stdout result, diagnostics only on stderr, no prompt
or terminal control, stable IDs, exact provider/version identity, a specific
refusal class, and a specific post-uncertainty inspection route.

Assess human CLI discoverability, blocker wording, safe next actions, plan and
effect disclosure, recovery guidance, narrow consoles, and exit codes.

Exercise the same binary through `facman tui`, `tui --ordinary`, and
`tui --advanced` in linear/full-screen, `NO_COLOR`, redirected, and dumb
terminal modes. Cover restoration, Ctrl+C, backend failure, keyboard-only
navigation/focus, narrow and Unicode content, Launch Deck, Activity, Last Run,
`outcome_unknown`, recovery, and close-versus-cancel.

Exercise WinForms from arbitrary working directories with restricted `PATH`, a
standard user, and Unicode/long paths. Cover Instances, Installations,
Activity, Settings/About, Advanced, Launch Deck, stale refusal, progress, Last
Run, recovery, keyboard and screen reader operation, High Contrast,
100/125/150/175/200 percent scaling, clean close, and restart.

## API and SDK lanes

CLI JSON is the normative public `0.1` automation API. Treat `FrontendSession
v2` as experimental while testing request/revision/idempotency propagation,
operation and attempt IDs, capabilities, query/act/inspect/cancel,
`advanced_execute`, direct/process equivalence, malformed responses, transport
loss before/after dispatch, stale revision, duplicate/conflicting idempotency,
and the clear absence of daemon transport.

Test ULK and USK as source, installed static/shared/combined, relocated
static/shared, C and C++ consumers, old-ABI consumers, and wrong-provider
negative controls. Treat FacMan C/C++ clients, generated C++/C#/Python models,
schema bundle, and direct/process transports as experimental engineering
consumers—not an installed or supported public SDK.

## Linux exploratory lane

Use Ubuntu 24.04/glibc 2.39 for CLI and same-binary TUI package previews. Record
build, package, relocation, runtime, terminal, failure, and negative-control
evidence as exploratory only. The GTK artifact may be checked for startup,
rendering, keyboard, AT-SPI/Orca, theme, scaling, relocation, and truthful
missing-backend behavior. It remains a frontend-only prototype without the
backend, contracts, licences, live Play, clean-machine packaging, or stable
support needed for a Linux product claim.

## Decision law

Human `Pass`, `Fail`, and `Inconclusive` are assigned only by named humans to
the exact bound packet. Machine success does not create them. Any source,
package, provider, or qualification digest change invalidates the packet and
requires a new three-root rebuild. Findings are repaired through a reviewed
`dev` WorkUnit and the entire affected freeze and test lane is repeated.

Tag-only progression additionally requires current protected-dev checks, three
independent attestations, exact pins, no unknown required skips, and the
currently absent no-bypass alpha-tag ruleset. Public alpha remains NO-GO without
an accepted real Play route and publication authority. Beta remains NO-GO until
the exact packages have completed CLI/TUI/WinForms usability and accessibility
receipts. Plain `0.1.0` remains outside this packet.
