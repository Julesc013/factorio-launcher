# C3 Universal Consumer Profile 01

Status: audit complete; implementation movement prohibited

Task: `C3-UNIVERSAL-CONSUMER-PROFILE-01`

Audit date: 2026-08-04

## Evidence snapshot and concurrent-writer caveat

This was a read-only audit of `D:/Projects/C3/compact-cassette-catalogue`. The
immutable evidence snapshot is:

```text
ea984df9b7ab99cf47fcdbd8edcb571e6ce80d52
```

At capture, `master` and the locally available `origin/master` tracking ref both
resolved to that commit. The C3 worktree was already dirty: eleven tracked files
were modified and
`src/C3.Infrastructure/CatalogueFiles/Xml/V1_1/LegacyCatalogueMetadataWriter.vb`
was untracked. Every source finding in this audit came from `git show` or
`git grep` against the captured commit, never from those mutable worktree files.

While the audit was running, a concurrent writer advanced local `master` by two
commits. The final observed HEAD was:

```text
2d99b047058bcc017e7094231d39e5abe66afefd
```

It was two commits ahead of the unchanged local tracking ref and had a different
set of twelve modified tracked files. That later state is recorded only as a
concurrency caveat; it is not part of the audited evidence. No fetch, provider
call, C3 product execution, or C3 filesystem write was performed.

## Ratified consumer decisions

- `win-x86-net40` is legacy x86 package-authoring only. Runtime USK
  maintenance remains disabled until the exact C3 candidate passes native
  Windows XP SP3 x86/.NET Framework 4.0 testing and the exact USK runtime
  independently proves XP compatibility.
- `win-x64-net48` is modern x64 package-authoring, with optional external USK
  maintenance behind a future versioned provider and product-binding contract.
- ULK is absent from both lanes. C3 has no demonstrated activation, session,
  command-line handoff, or single-instance coordination requirement. Reaudit
  only if such a requirement becomes real.

In the matrix, **move** means contract-driven reimplementation or generalization
in the permanent owner. It never means copying C3 implementation files into a
universal repository.

## Retain/move/adapt/delete matrix

Each row records source and symbol, responsibility, permanent owner,
disposition, characterization, migration dependency, and rollback.

### C3-01 — retain

- Source/symbol: `build/lanes.json` / `win-x86-net40`.
- Responsibility: define the x86, .NET 4.0, XP-targeted portable lane.
- Permanent owner: C3.
- Characterization: validate the exact lane ID, project, x86 platform, v4.0
  target, output directory, runtime claim, and portable distribution.
- Dependency: none for package authoring; native XP proof before widening
  runtime claims.
- Rollback: continue publishing the existing verified portable ZIP.

### C3-02 — retain

- Source/symbol: `src/C3.WinForms/C3.WinForms.Net40.vbproj`,
  `Configuration/Net40/App.config`, and `Configuration/Net40/app.manifest`.
- Responsibility: build and configure the legacy x86/v4.0 application with
  `asInvoker` execution.
- Permanent owner: C3.
- Characterization: run project-parity and I386/PE32 checks, then the full
  native XP manual suite.
- Dependency: VS2019 with the .NET 4.0 targeting pack.
- Rollback: revert the candidate and republish the prior complete x86 ZIP.

### C3-03 — retain

- Source/symbol: `build/lanes.json` / `win-x64-net48`.
- Responsibility: define the x64, .NET 4.8, Windows 7-targeted portable lane.
- Permanent owner: C3.
- Characterization: validate the exact lane ID, x64/v4.8 mapping, output
  directory, runtime claim, and package name.
- Dependency: none for package authoring.
- Rollback: continue the standalone portable ZIP.

### C3-04 — retain

- Source/symbol: `src/C3.WinForms/C3.WinForms.Net48.vbproj`,
  `Configuration/Net48/App.config`, and `Configuration/Net48/app.manifest`.
- Responsibility: build and configure the modern x64 application and its
  DPI/runtime policy.
- Permanent owner: C3.
- Characterization: run project parity, AMD64/PE32+ verification, and the
  Windows 7 SP1 manual suite.
- Dependency: an optional USK runtime must independently support the minimum
  operating system.
- Rollback: disable USK integration and launch the portable executable directly.

### C3-05 — retain

- Source/symbol: `build/build.ps1` and `build/resolve-msbuild.ps1`.
- Responsibility: build both product lanes.
- Permanent owner: C3.
- Characterization: exercise the existing dual-lane rebuild gate.
- Dependency: the authoritative VS2019 toolchain.
- Rollback: build the previous C3 commit; USK must never rebuild C3.

### C3-06 — adapt

- Source/symbol: `build/package.ps1` / lane staging and ZIP creation loop.
- Responsibility: author deterministic product packages.
- Permanent owner: C3.
- Characterization: package twice without rebuilding, then compare ZIP hashes,
  names, timestamps, and exact contents.
- Dependency: a future machine-readable product-binding/profile projection.
- Rollback: remove the projection and retain the current ZIP workflow.

### C3-07 — retain

- Source/symbol: `build/verify-packages.ps1` and generated
  `SHA256SUMS.txt`.
- Responsibility: verify the seven-entry ZIP closure and archive SHA-256 values.
- Permanent owner: C3.
- Characterization: require two ZIPs, exact entries, well-formed checksum
  records, and matching hashes.
- Dependency: USK must consume the verified output and hashes instead of
  maintaining a second file list.
- Rollback: reject the integration and use the verified portable asset.

### C3-08 — retain

- Source/symbol: `build/Version.props`, `build/sync-version.ps1`,
  `Generated/BuildInfo.g.vb`, and `VERSION`.
- Responsibility: own product, assembly, catalogue-format, stage, and date
  identity.
- Permanent owner: C3.
- Characterization: run `build/verify-metadata.ps1` and compare every generated
  projection.
- Dependency: a future profile may project these values but cannot become
  authoritative.
- Rollback: regenerate projections from `Version.props`.

### C3-09 — retain

- Source/symbol: the `build/package.ps1` payload containing the executable,
  executable config, two product DLLs, `BUILD.txt`, `README.md`, and
  `RELEASE_NOTES.md`.
- Responsibility: define the immutable application payload closure.
- Permanent owner: C3.
- Characterization: check the exact archive entries and perform a clean
  extraction/assembly-load smoke test.
- Dependency: a USK product-binding contract for the modern lane.
- Rollback: restore the prior complete closure, never individual files.

### C3-10 — retain

- Source/symbol: `My Project/Application.myapp` and
  `Application.Designer.vb` / `OnCreateMainForm`.
- Responsibility: start the standalone application directly in `frmMain`; the
  application is not single-instance.
- Permanent owner: C3.
- Characterization: direct-lane launch and clean-close characterization.
- Dependency: none; there is no ULK dependency.
- Rollback: continue direct executable startup.
### C3-11 — retain

- Source/symbol: negative search for a command-line parser, activation handler,
  session handoff, or `StartupNextInstance` implementation.
- Responsibility: define the current launcher/session boundary.
- Permanent owner: no universal owner currently required.
- Characterization: static search plus direct startup test.
- Dependency: reaudit only after an evidence-backed activation/session
  requirement appears.
- Rollback: there is no launcher integration to remove.

### C3-12 — retain

- Source/symbol: `Configuration/MySettingsStore.vb`,
  `My Project/Settings.settings`, and generated `MySettings`.
- Responsibility: persist per-user messages, default directory, update intent,
  and last-check time.
- Permanent owner: C3 and the user.
- Characterization: save and reload settings in both lanes and on their minimum
  operating systems.
- Dependency: USK must classify settings as preserved user data.
- Rollback: disable maintenance; never restore settings by replacing payload
  files.

### C3-13 — retain

- Source/symbol: `CatalogueSession` and the brand, cassette-model, deck, and
  tape services.
- Responsibility: own catalogue lifecycle, identity, dirty state, and product
  rules.
- Permanent owner: C3.
- Characterization: run the existing session and domain characterization cases.
- Dependency: none.
- Rollback: reopen the last verified catalogue or its user backup.

### C3-14 — retain

- Source/symbol: `spec/catalogue/v1.1.0`, its fixtures, and
  `LegacyCatalogueSchema`.
- Responsibility: own the public catalogue XML contract and
  compatibility-sensitive keys.
- Permanent owner: C3 and the user.
- Characterization: validate the XSD plus valid, invalid, security, and culture
  fixtures.
- Dependency: USK must never inspect, migrate, or delete catalogue documents.
- Rollback: restore the user-owned XML or backup.

### C3-15 — retain

- Source/symbol: `LegacyXmlCatalogueStore.Load`.
- Responsibility: securely and boundedly load XML and calculate a revision.
- Permanent owner: C3.
- Characterization: exercise malformed XML, external-entity, missing-version,
  unsupported-version, size, and structure failures.
- Dependency: none.
- Rollback: leave the active catalogue untouched on failure.

### C3-16 — retain

- Source/symbol: `LegacyXmlCatalogueStore.Save`, including the temporary write,
  round-trip verification, `File.Replace`, and `.bak` path.
- Responsibility: transactionally persist catalogue data and provide data
  rollback.
- Permanent owner: C3.
- Characterization: run `StoreSavesTransactionally` and add an explicit
  old-content `.bak` assertion.
- Dependency: none.
- Rollback: use `<catalogue>.bak`; this is independent of package rollback.

### C3-17 — retain

- Source/symbol: `CrashReportWriter.TryWrite`.
- Responsibility: write
  `%LocalAppData%/C3/CrashReports/C3-error-*.log` diagnostics.
- Permanent owner: C3 and the user.
- Characterization: generate a synthetic exception and verify the report path
  and bounded content.
- Dependency: USK preserve-data policy.
- Rollback: never delete reports during repair, update, or uninstall.

### C3-18 — retain

- Source/symbol: `OutputConsoleToolStripMenuItem_Click`.
- Responsibility: export a diagnostic log to the user-selected/default
  directory.
- Permanent owner: C3 and the user.
- Characterization: verify bounded log output to the chosen directory.
- Dependency: USK preserve-data policy.
- Rollback: the user retains the exported file.

### C3-19 — adapt

- Source/symbol: `UpdateCheckPolicy`, `UpdateCheckSchedule`, and
  `MySettingsStore.UpdatePolicy`.
- Responsibility: own user intent and startup/weekly/monthly/never scheduling.
- Permanent owner: C3.
- Characterization: retain `UpdateScheduleOwnsPolicy` and add
  provider-disabled/default-never behavior.
- Dependency: a future provider trigger/result contract.
- Rollback: set the policy to `never` and retain the manual releases link.

### C3-20 — move

- Source/symbol: `frmMain.checkUpdates`, `enableBestEffortTls`,
  `isNewerVersion`, and `UPDATELINKCHECK`.
- Responsibility: discover versions directly through `WebClient.OpenRead` of
  the raw GitHub `VERSION` file.
- Permanent owner: USK when maintenance is enabled.
- Characterization: test unavailable, current, available, and malformed
  fake-provider results and assert no direct network.
- Dependency: completed audits followed by a versioned USK provider contract;
  initially modern x64 only.
- Rollback: disable the provider and use the manual releases page.
### C3-21 — retain

- Source/symbol: `openWebLink`, `UPDATELINKDOWNLOAD`, and update-menu handlers.
- Responsibility: provide a manual browser fallback and product/help links.
- Permanent owner: C3.
- Characterization: characterize network-blocked and browser-open failure paths.
- Dependency: none; it may remain beside optional USK maintenance.
- Rollback: the user manually downloads the verified ZIP.

### C3-22 — move

- Source/symbol: current-tree negative search for `DownloadFile`,
  `ExtractToDirectory`, registry, shortcut, or uninstall paths.
- Responsibility: download, install, repair, update, and uninstall product
  payloads.
- Permanent owner: USK for enabled profiles.
- Characterization: keep a static negative-boundary test and later run USK
  conformance tests.
- Dependency: USK product-binding, transaction, and preservation contracts.
- Rollback: disable optional maintenance; the portable package remains
  authoritative.

### C3-23 — delete

- Source/symbol: historical `509c9ec...:Compact Cassette Catalogue
  Installer/frmMain.vb`, `varGlobals.vb`, and manifest.
- Responsibility: download a ZIP, extract in place, write HKLM uninstall data,
  and create common shortcuts.
- Permanent owner: none; future behavior belongs to USK.
- Characterization: assert the project remains absent from the current tree.
- Dependency: none; this code must not be a migration source.
- Rollback: never restore it.

### C3-24 — delete

- Source/symbol: the historical installer project targeting .NET Framework 4.6
  and requesting `highestAvailable`.
- Responsibility: provide a purported legacy-lane installation runtime.
- Permanent owner: none.
- Characterization: historical inspection proves it cannot establish the XP
  lane.
- Dependency: a native XP-capable USK would require an independent
  implementation and proof.
- Rollback: never restore it; use the portable x86 ZIP only.

### C3-25 — delete

- Source/symbol: historical `Compact Cassette Catalogue
  Uninstaller/frmMain.vb`.
- Responsibility: purport to uninstall despite placeholder registry, file, and
  shortcut removal bodies.
- Permanent owner: none; future behavior belongs to USK.
- Characterization: assert the project remains absent and never treat its
  success form as evidence.
- Dependency: none.
- Rollback: never restore it; use portable/manual removal.

### C3-26 — move

- Source/symbol: negative search for a current self-replacement implementation.
- Responsibility: replace the installed executable in place and provide runtime
  rollback.
- Permanent owner: USK if modern maintenance is enabled.
- Characterization: assert C3 never writes or replaces its installed executable.
- Dependency: USK atomic switch, process-quiescence, integrity, and rollback
  contracts.
- Rollback: disable USK and restore the prior complete portable directory.

### C3-27 — retain

- Source/symbol: `release/validation/1.2.1-beta.1.md` candidate identity,
  package evidence, manual workflows, and minimum-OS evidence.
- Responsibility: record candidate, package, manual-workflow, and minimum-OS
  evidence.
- Permanent owner: C3.
- Characterization: keep the gate blocked while any required row is unrun.
- Dependency: exact candidate commit and artifact hashes.
- Rollback: narrow or remove an unsupported compatibility claim.

### C3-28 — retain

- Source/symbol: `release/validation/1.2.0-beta.1.md` historical validation and
  release boundary.
- Responsibility: preserve historical evidence without promoting it to current
  proof.
- Permanent owner: C3.
- Characterization: the record explicitly says the XP VM test was not run and
  the old installer was not the official XP path.
- Dependency: historical evidence cannot satisfy current-candidate evidence.
- Rollback: do not promote historical results.

## Installer and uninstaller history

The last inspectable installer snapshot is
`509c9ec29679e30dcdcb1f57d8874b850cee310c`. It targeted .NET Framework
4.6, requested `highestAvailable`, read the raw GitHub `VERSION`, downloaded
`v<version>.zip` without an expected checksum or authenticated manifest, wrote
the archive directly into the final Program Files directory, extracted in place,
deleted the ZIP, wrote HKLM uninstall metadata, and created common shortcuts.
Its exception path offered no staging transaction, previous-version retention,
integrity closure, repair model, cleanup guarantee, or rollback.

The historical uninstaller's registry, file, and shortcut removal sections were
literal placeholders, yet execution proceeded to its success form. It is not
uninstall evidence.

Both projects were explicitly marked as archived and not reusable by
`bf3260987458a97dd3a4ed3db154f7992d9d48cc`, then deleted by
`08bb8da0d8d8d042fc75982510e56e81a08e38e8`. They are characterization
evidence only. Neither may be restored, copied, or used as a rollback path.

## Application and data boundaries

- The replaceable application payload is the complete verified seven-file ZIP
  closure. C3 authors it; an optional modern USK integration may deploy it only
  as a complete closure and may not rebuild it.
- Per-user settings remain C3/user data and survive repair, update, and uninstall.
- Catalogue XML and `.bak` files are user documents governed only by the C3
  format contract. Universal setup and launcher code must not inspect, migrate,
  delete, or claim ownership of them.
- Crash reports under `%LocalAppData%/C3/CrashReports` and console exports in a
  user-selected directory remain preserved C3/user diagnostics.
- Catalogue `.bak` replacement is product-data rollback. It must never be
  conflated with USK package rollback.
- Current C3 has no product downloader, installer, uninstaller, repair path, or
  self-replacement path. The direct update check is discovery and notification
  only; it does not download an update.

## Windows XP judgment

The x86 application is technically plausible on XP: the production dependency
chain targets .NET Framework 4.0, the executable is x86/PE32, the application
manifest is `asInvoker`, normal catalogue work is offline, and failure of the
optional GitHub/TLS path does not block catalogue use.

That is not native runtime proof. Both current and historical release-validation
records say the Windows XP SP3 VM test was not run. Therefore:

1. `win-x86-net40` remains package-authoring-only.
2. The exact candidate ZIP and hash must pass the complete native XP workflow.
3. Passing C3 on XP would not prove USK on XP. The exact USK binary and its
   install, repair, update, preservation, and rollback behavior need independent
   native proof before maintenance can be enabled.
4. ULK remains absent regardless of XP proof unless C3 later demonstrates an
   activation or session requirement.

## No-code-move result

The audit moved no implementation. It changed no C3 file and authorizes no bulk
file transfer, provider implementation, setup integration, product execution,
repin, signing, publication, or route change. The only permissible follow-on is
to design provider and product-binding contracts after all consumer audits are
complete and reviewed.
