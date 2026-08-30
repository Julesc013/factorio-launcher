# FacMan canonical v2 three-root candidate qualification 01

Date: 23 August 2026

State: `pass_exact_source_three_root_non_authorizing`

## Outcome

Three independent no-hardlink Windows roots reconstructed the exact canonical
v2 WinForms Technical Preview candidate and produced byte-identical qualified
outputs. Native product inspection, intact package verification, deliberate
payload-drift refusal, deterministic archive construction, SBOM, provenance,
licence closure, and independent candidate-assurance verification passed in
every root.

This is an internal package qualification for the exact source below. It is
not a tag, public alpha, release-route receipt, human verdict, signature,
publication, support promotion, Setup mutation, or Factorio execution claim.

## Exact source and composition

| Identity | Exact value |
| --- | --- |
| FacMan commit | `6a032a456f8b03be420a5654f3b37d2a4f4a0cd8` |
| FacMan tree | `f8edc2b9f170a849583f96df11a2d8f2a2baac91` |
| Universal Launcher commit/tree | `5479939ca5cbc9ee0f901608a92012778b4752ae` / `7728e4d415539a0f24e6f17aa7d22be00cc99d80` |
| Universal Setup commit/tree | `d2a2aae7e61c47035c92334b0522143b4fea3880` / `291d63214cdd0cd3d15c809de5744ee3514fb2b2` |
| Target/profile | `windows_winforms_technical_preview_x64` |
| Artifact | `windows_winforms_technical_preview_zip` |
| Toolchain | `windows_msvc_v143_x86_64` |
| Source observation | `21df7b876b9a578db4727512abca6e19e22ea224e28e140e0e3f10dc4d91f48e` |
| Coherence proof domain | `44ad7b7ed34db810f9292d54ffdad220ca0bdc15bcc682682a17a890072472af` |
| Resolution root | `e2723cc78a0ad9d9cd321014191c3ae9f9d4a6e6ca4a7e5d16e4d0dc79911b79` |
| Resolution | `e47b11631ca9462f1450847cfcf84ecd6274ab775583c887081e285e8dd9cf60` |

Each source observation was release-eligible, clean, canonical-remote bound,
and provider-pin exact. Path-bearing checkout receipts differ by physical
root as expected; their path-free release-source projection is identical.
Wrong-provider coherence controls refused in every root.

## Stable-root build and exact commands

Each physical root was mapped in turn to the same temporary `Q:` logical drive
by `tools/windows_stable_build_root.py`. The driver removed the mapping after
each command and emitted `facman.windows_stable_build_root.v1` receipts.
The receipt command arrays were:

```text
cmake -S Q:\facman -B Q:\build -G "Visual Studio 18 2026" -A x64
  -DFACMAN_BUILD_CLI=ON -DFACMAN_BUILD_TUI=ON
  -DFACMAN_PROVIDER_MODE=source
  -DFACMAN_PROVIDER_SOURCE_LINKAGE=static
  -DFACMAN_WARNINGS_AS_ERRORS=ON
  -DFLAUNCH_UNIVERSAL_LAUNCHER_ROOT=Q:\universal-launcher
  -DFLAUNCH_UNIVERSAL_SETUP_ROOT=Q:\universal-setup

cmake --build Q:\build --config Release --parallel --target facman_cli

C:\Program Files\Microsoft Visual Studio\18\Enterprise\MSBuild\Current\Bin\MSBuild.exe
  Q:\facman\apps\gui\windows\winforms\FacMan.WinForms.csproj
  /t:Rebuild /p:Configuration=Release /p:Platform=x64 /warnaserror
```

Within each root, the production compiler sequence used:

```text
python facman/tools/facman_release.py --source-observation <source-observation> resolve
  --target windows_winforms_technical_preview_x64 --output resolution
python facman/tools/facman_release.py stage --resolution resolution
  --artifact windows_winforms_technical_preview_zip --source-root facman
  --source facman_cli=<facman.exe> --source facman_winforms=<FacMan.WinForms.exe>
  --output stage
stage/bin/facman.exe product inspect --json
stage/bin/facman.exe package verify --json
python facman/tools/facman_release.py archive --resolution resolution
  --artifact windows_winforms_technical_preview_zip --stage stage --output dist
python facman/tools/facman_release.py assure-candidate --resolution resolution
  --artifact windows_winforms_technical_preview_zip --stage stage
  --archive dist/<canonical-archive> --output dist/assurance
python facman/tools/facman_release.py verify-package --resolution resolution
  --artifact windows_winforms_technical_preview_zip
  --package dist/<canonical-archive>
python facman/tools/facman_release.py verify-candidate-assurance
  --resolution resolution --artifact windows_winforms_technical_preview_zip
  --stage stage --archive dist/<canonical-archive>
  --sbom dist/assurance/<sbom> --provenance dist/assurance/<provenance>
```

Angle-bracket values above are the root-local exact paths to the named and
digest-bound files. The stable-root JSON command arrays retain the physical
root used for each invocation; no machine path is part of the compared
release identity.

## Verification and negative controls

All three `product inspect --json` results reported `ok`, 405 verified files,
`sha256_consistent`, exact source/provider identity, build/package identity
match, contract/build identity match, and the canonical stage digest below.
All three intact `package verify --json` results passed.

For each root, a separate copy of the canonical stage had
`content/factorio/discovery/headless.toml` changed by one bounded qualification
marker. The canonical stage remained untouched. Each verifier exited 1 with:

```text
status: error
integrity: failed
detail: staged file size mismatch: content/factorio/discovery/headless.toml
operation: refused_before_effects
```

All three archive inspections reported 406 entries and inventory digest
`4bd4ad3c3012970a5ab0b6e3f7f7ca5737348557f9e81cd5d5810b7b25569309`.
All three assurance checks reported `verified = true` and
`native_admission_ready = true`.

## Complete compared-output table

The comparison enumerated both native executables and every file under the
exact resolution, canonical stage, and distribution trees. Each root produced
423 files totalling 16,716,887 bytes. The canonical path/length/SHA-256 table
digest is `e6cf4e1929067e0489ed35bbf6143232315cdc21ba990f855010ea4c8b5429c1`;
root-to-root mismatch count is zero.

| Output | Bytes | SHA-256 |
| --- | ---: | --- |
| `facman.exe` | 4,447,744 | `4e7840decefa4c49472ce25b98a3c6b87c9ebfd3e17b08e0de2f3ab019932f4f` |
| `FacMan.WinForms.exe` | 508,928 | `b5d530d050c89360c6f17cd475da060ce7dd883d5dca67681c7126cc563032b3` |
| `manifest/stage.v1.json` | 162,168 | `831de4baee67a9fe7d86cc02f2beecb85dc8e08f1617fa4118355c51d51c147f` |
| canonical ZIP | 4,175,982 | `f84792f2b5d48eface98ef3e462af91602e0b1f20c5ad70eac609f903eb2c27c` |
| SPDX 2.3 SBOM | 4,097 | `356fdd8ea0f3c54e66cfe8a4522e36192ee45834fe834484ce75985d330889df` |
| provenance | 5,056 | `fa13f552f68dba0cb7d0c0f5d8865f5f7756e8a6e951f143d3748405b6840207` |

The canonical stage closure digest is
`beb97029ef699ab4bb5348514b2bb6ed3ea5ca011d54f702fea519493a1f1325`.

## Classification and remaining gates

The first checkout attempts encountered Windows long-path checkout failures;
the three new, empty clone targets were safely recreated with
`core.longpaths=true`. Two observation attempts then correctly failed because
the disposable provider paths and canonical `origin/main` observations were
not yet represented. Exact local canonical tracking refs repaired only the
qualification topology. The final observations passed without changing source
or relaxing custody checks.

Remaining gates are scoped and unchanged:

- no Factorio process was started and no real Play route is accepted;
- no clean-host real-route or human accessibility/usability verdict exists;
- the archive and sidecars are unsigned and unpublished;
- no support, signing, approved-unsigned, tagging, or publication authority
  was granted; and
- the active 29-row product WorkUnit remains open for its independent product,
  route, and human gaps.

Work-Item: `FACMAN-WINDOWS-TECHNICAL-PREVIEW-CANDIDATE-01`
