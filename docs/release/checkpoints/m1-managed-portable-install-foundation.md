# M1 Managed Portable Install Foundation

Status: **fixture-proven and integrated on `dev`**.

M1 turns Universal Setup from a verification bootstrap into a bounded,
product-neutral local portable-install authority, consumes its state seam in
Universal Launcher, and supplies the first Factorio recipe and generated
workflow through FacMan. This is independent of real Factorio execution and
does not change the R3.7 H1 candidate.

## Exact repository identities

| Repository / slice | Accepted identity | Hosted evidence |
| --- | --- | --- |
| Universal Setup WU1-WU7 | `2bc4bf93b1a77c5c906fdc6d3f12b286dadc8ca7` on `main` | CI `29293560341` |
| Universal Launcher WU8 | `c43d390efe0db17480f9d0262827659b4ae242dd` on `main` | CI `29290652251` |
| FacMan WU9 recipe/gateway | `842ee9fa36e7d46900eab7d55bc0cc3f917913a5` on `dev` | CI `29294372585`; CodeQL `29294372612`; schema `29294372523`; policy `29294372522` |
| FacMan WU10 generated workflows | merge `96a559ffba4b24e11e6ad71e4d4809dc50726d9f` | exact-head CI `29296336736`, `29296347817`; CodeQL `29296336781`, `29296347798` |
| FacMan WU11 system proof | task head `f4fdafead6a0be4810d8c9722d8d8f521870d73d`; merge `13319e4f9e51bd8687829262edcfa120e488990d` | exact-head CI `29297920929`, `29297933372`; CodeQL `29297920909`, `29297933359`; schema `29297920946`, `29297933368`; policy `29297920914`, `29297933385` |
| FacMan WU12 package proof | task head `2f13923a9cbdd60d47cab114ba1e280282259bb5`; merge `10b1caa915ed4ad5e934f625f3e1384ecc700eaa` | CI `29299245206`; CodeQL `29299245093`; security `29299245082`; release policy `29299286894` |

The WU12 schema inputs are unchanged. Schema run `29297933368` is therefore
the carried-forward exact WU11 schema identity; WU12's schema and strict checks
also passed in the clean local reproduction.

## Implemented foundation

Universal Setup now owns descriptor-driven command dispatch, versioned setup
contracts, stable local-source/archive inspection, deterministic plan binding,
owned staging, durable transaction journals, installed-state and ownership
repositories, audit chains, and the fixture-backed portable install lifecycle:

```text
install -> verify -> move -> repair -> uninstall -> recovery
```

The archive and transaction layers reject traversal, ambiguous or colliding
paths, links and unsupported file types, source/target substitution, changed
plan inputs, unowned targets, foreign-content deletion, and unbounded resource
use. Repair and uninstall act only on recorded owned state. Unknown files are
retained and reported.

Universal Launcher consumes immutable setup plan/result/state references and
refreshes managed install references only after verified state changes. It
remains product-neutral.

FacMan supplies the declarative Windows ZIP-style Factorio recipe, product
classification, managed install-reference projection, generated CLI/TUI/
WinForms/AppKit plan-review workflows, progress/cancellation/recovery models,
and a direct three-repository proof. It does not absorb setup mutation into the
launcher or frontends.

## Three-repository journey proof

CTest `m1_three_repository_system_proof` links the actual FacMan product
binding, Universal Setup lifecycle, and Universal Launcher state seam. It runs
only in an exclusively created temporary root and proves:

```text
synthetic Factorio archive
-> inspect and digest-bound plan
-> install and installed-state record
-> install-reference and instance creation
-> launch preview only
-> verify
-> move and reference refresh
-> deliberate owned-file drift and repair
-> foreign-content uninstall retention/refusal
-> clean uninstall
-> recovery-required inspection and completion
```

The journey uses no proprietary Factorio binary and does not start a process.
`run.execute` remains refused with `isolation_not_proven`.

## WU12 clean and package evidence

Clean command:

```text
py -3 tools/repro_workspace_smoke.py --build --require-clean \
  --build-root build/m1-wu12-final-repro
```

Result: PASS in 392.8 seconds. It independently configured, built, and ran
CTest plus strict validation for Universal Launcher and Universal Setup, then
configured and built FacMan and ran CTest, AIDE Lite, strict validation, and
the full Python corpus. No checkout-local build artifact was accepted as a
substitute for the fresh output roots.

At the exact WU12 implementation state:

- native CTest inventory: 35/35 PASS;
- Python: 337 cases, 336 PASS and one deliberate opt-in bounded-scale skip;
- required Windows package proof: 14/14 PASS, zero skips;
- installed SDK/provider consumers, target linkage, workspace-lock identities,
  relocation, Unicode/pathless/arbitrary-working-directory runtime, read-only
  package files, tamper/unhashed-file refusal, SBOM, and provenance: PASS.

Two independent selected-package staging roots produced identical complete
package trees, archives, SBOMs, and adjacent provenance:

| Evidence | Identity |
| --- | --- |
| archive | 1,902,407 bytes; SHA-256 `ff5fe8c4ee51771f4efd177ce9f5af16fa2c330d27b8b76adaec46d0943df4c8` |
| package tree | 379 files; SHA-256 `7bdffb88092bbc66663a43f5218614a2911fe7c00a4144f8b7768d689207cef6` |
| SPDX 2.3 SBOM | 6,252 bytes; SHA-256 `c7789bbece2f730d5c4f4ea7d929e1b0b6463ab6cd957bdd2174569069820a32` |
| adjacent provenance | 2,088 bytes; SHA-256 `c134fed6dffa67ab61686119a3de0247382a617d3b37d38b151298cf552e3d1f` |

The proof runner refuses dirty source state and is now required by the Windows
target-native CI job. CI `29299245206` passed Linux native, sanitizer, bounded
fuzzer, coverage, Linux package, Windows Debug/Release native, WinForms,
Windows package/reproducibility, macOS native/package, macOS archive, and AppKit
compile jobs. CodeQL `29299245093` passed C/C++, C#, and Python.

## Authority and residual boundaries

M1 proves mutation only in exclusively created fixture, disposable test, and
setup-owned package-proof roots. Ordinary FacMan setup apply commands remain
unavailable until a separate live-target operator acceptance is authorized.

This checkpoint does not authorize or claim:

- `run.execute`, server execution, or an R3.8 execution candidate;
- an H1 Pass, standalone/manual isolation, or Safe beta;
- network/download, credentials, Steam mutation, registry, package-manager,
  elevation, installer execution, or system-wide installation;
- adoption of imported, foreign-owned, GUI-installer, Steam, or unknown legacy
  installations;
- signing, publication, or publisher authenticity.

The Steam-backed H1 operator verdict remains **Fail**. Standalone/manual
isolation remains `unproven`. Artifacts remain unsigned and unpublished, and
the Universal repository license decision remains an operator blocker.
