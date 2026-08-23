# FacMan canonical v2 final-source qualification 01

Date: 24 August 2026

State: `pass_exact_source_three_root_non_authorizing`

## Outcome

Three independent no-hardlink Windows roots reconstructed the canonical v2
WinForms Technical Preview candidate from exact replacement source `0df94467`.
Complete file, inventory, and byte comparison found zero root-to-root
mismatches. Product inspection, native intact verification, deliberate
payload-drift refusal, deterministic archive construction, SPDX SBOM,
provenance, six-file licence closure, and independent assurance verification
passed in every root.

This is an internal package receipt. It is not a tag, release route, human
verdict, signature, publication, support promotion, Setup mutation, or
Factorio execution claim.

## Semantic invalidation from the superseded head

The replacement source is the direct child of `ff7f8454` and adds one
test-fixture path canonicalization line. A fresh exact-root comparison still
found 20 changed paths in the canonical candidate domain: `facman.exe`, its
staged copy, all 12 resolution records, the two staged runtime identity
records, the stage manifest, archive, SBOM, and provenance. The WinForms
executable and all ordinary staged product content were unchanged.

Because the CLI embeds the exact source revision, the canonical candidate
identity changed even though runtime product behavior did not. The earlier
`ff7f8454` reconstruction therefore could not be relabeled; this receipt binds
a complete new three-root qualification to `0df94467`.

## Exact identities

| Identity | Exact value |
| --- | --- |
| FacMan commit/tree | `0df94467637836a364f684a43b887d8133ed4388` / `6c8cf9751f8be7f6ed2d2808dddc649b50d7c642` |
| Universal Launcher commit/tree | `5479939ca5cbc9ee0f901608a92012778b4752ae` / `7728e4d415539a0f24e6f17aa7d22be00cc99d80` |
| Universal Setup commit/tree | `d2a2aae7e61c47035c92334b0522143b4fea3880` / `291d63214cdd0cd3d15c809de5744ee3514fb2b2` |
| Target/artifact | `windows_winforms_technical_preview_x64` / `windows_winforms_technical_preview_zip` |
| Toolchain | `windows_msvc_v143_x86_64` |
| Source observation | `88bfea3fa3ee907957cc2b34b82b5f138caa48eabf186d08c8608ee2de8998ae` |
| Coherence/wrong-provider proof | `f36212a7bbf34a0b19b059fc6687bd08e270fe2428f34671963450f7318a107f` |
| Resolution root/resolution | `cd79c8a9be51ee1ecaf03cb5493814bd2226d19ad4016778896204cb4721b376` / `996f1b3d80f27d140d229261c14df35308ee2b75d0d83b44f64ea8f8eaad004f` |
| Canonical stage | `e805ed87df1264ba75cbfb45f374d0d519961dc5fd4ef29646f036cd28eb94bd` |
| Archive inventory | `fdf3fc8be198d4d76db24965f87b28a06096b265f4ade0d8fa03797b92d597b0` |

Every checkout observation was clean, detached at the requested object,
canonical-remote bound, provider-pin exact, release eligible, non-shallow, and
free of object alternates, partial-clone configuration, and promisor packs.
Path-bearing checkout observations differ by root as expected; their path-free
source and coherence identities are identical. Both injected wrong-provider
controls produced the exact required refusal in every root.

## Stable build topology

Each physical root was sequentially mapped to temporary logical drive `Q:` by
`tools/windows_stable_build_root.py`. The driver verified and removed every
mapping and preserved a JSON receipt. Process-scoped `safe.directory` entries
were limited to the six exact physical and logical source roots because the
elevated build identity differed from the sandbox clone owner; no global Git
configuration changed. Each root ran:

```text
cmake -S Q:\facman -B Q:\build -G "Visual Studio 18 2026" -A x64
  -DFACMAN_BUILD_CLI=ON -DFACMAN_BUILD_TUI=ON
  -DFACMAN_PROVIDER_MODE=source
  -DFACMAN_PROVIDER_SOURCE_LINKAGE=static
  -DFACMAN_WARNINGS_AS_ERRORS=ON
  -DFLAUNCH_UNIVERSAL_LAUNCHER_ROOT=Q:\universal-launcher
  -DFLAUNCH_UNIVERSAL_SETUP_ROOT=Q:\universal-setup
cmake --build Q:\build --config Release --parallel --target facman_cli
MSBuild.exe Q:\facman\apps\gui\windows\winforms\FacMan.WinForms.csproj
  /p:Configuration=Release /p:Platform=x64 /m
```

The compiler sequence resolved the exact source observation, staged the built
executables, verified the stage, ran `product inspect --json` and
`package verify --json`, constructed and inspected the deterministic archive,
verified it against the external resolution, generated candidate assurance,
and independently recomputed the assurance closure.

## Verification and negative controls

All product inspections reported exact source/provider identity,
`source_dirty = false`, build/package and contract/build identity matches, 406
verified files, and the canonical stage digest. All intact native package
checks passed.

Each root used a separate stage copy for drift control. The copies changed one
hash-covered text payload only; the canonical stages stayed untouched. Every
native verifier exited 1 with `integrity: failed`, a precise file-size
mismatch, and `refused_before_effects`.

All archive verifications reported 407 entries, inventory digest
`fdf3fc8be198d4d76db24965f87b28a06096b265f4ade0d8fa03797b92d597b0`,
and exact stage/resolution identity. Every assurance verification reported
`verified = true` and `native_admission_ready = true`.

## Complete comparison

The comparison enumerated both native executables and every file under each
root's resolution, canonical stage, and distribution trees. Each root produced
424 files totalling 16,887,218 bytes. The canonical path/length/SHA-256 table
digest is `98301316becddafdc57cbfa804b9489225416499839e60f52a82df326dda6957`;
the mismatch count is zero.

| Output | Bytes | SHA-256 |
| --- | ---: | --- |
| `facman.exe` | 4,502,016 | `33915f0e9446566c39ecff5a30b0f6859cdf796e4aa5ed70da80c173e05840ae` |
| `FacMan.WinForms.exe` | 522,240 | `a1aa6d5f6a26c332c7dd48f2fe9293f49af513084287a66db743098c278d4c77` |
| `manifest/stage.v1.json` | 162,570 | `0aba3cefc2d28be421727403ddb1b21a1cced52e393b419dbd45d513a4aefe6d` |
| canonical ZIP | 4,206,890 | `4d878d3dc2c1420360301b4af95669fc2fbf90cb569fe60febc8edc88a5fc870` |
| SPDX 2.3 SBOM | 4,097 | `368e891dae1c8b3a84ad5bcbe3f0547393695667cacca009ba46ee7c76ebd2d8` |
| provenance | 5,056 | `0d50028d0635af5741d8ad4cf00d77241c67528af73863b0fa2b74d10897fa8a` |

Ignored evidence remains under `tmp/qualification/candidate-0df94467/`,
including the semantic invalidation audit, complete byte table, comparison
receipt, checkout/coherence and stable-root receipts, resolutions, stages,
archives, SBOMs, and provenance.

## Remaining authority gates

- No Factorio process was started and no real Play route is accepted.
- Accessibility and usability still require exact human receipts.
- The archive and sidecars remain unsigned, unpublished, unsupported, and
  untagged.
- No support, signing, approved-unsigned, tagging, publication, Setup mutation,
  or Factorio execution authority was granted.
- Any later source change invalidates this exact package receipt.

Work-Item: `FACMAN-WINDOWS-TECHNICAL-PREVIEW-CANDIDATE-01`
