# AIDE Lite Release Bundle

Q47 defines how AIDE turns the validated portable AIDE Lite Pack into local
downloadable archives. It is deterministic, local, no-call, and publication-free.

Q47 does not create Git tags, create GitHub Releases, upload artifacts, publish
packages, mutate branches, install CI, install AIDE into target repositories, or
apply install, repair, upgrade, rollback, or uninstall actions.

## Lifecycle

The local release-bundle lifecycle is:

1. validate source repository
2. regenerate the export pack
3. validate `pack-status`
4. build local archives
5. compute checksums
6. write release manifest and install notes
7. extract archives into fixtures
8. validate archive contents and forbidden-path exclusions
9. write evidence
10. review
11. GitHub release draft review
12. future publish

Q47 implements local generation and validation only.

## Commands

```text
py -3 .aide/scripts/aide_lite.py release bundle
py -3 .aide/scripts/aide_lite.py release validate
py -3 .aide/scripts/aide_lite.py release status
py -3 .aide/scripts/aide_lite.py release assets
py -3 .aide/scripts/aide_lite.py release manifest
py -3 .aide/scripts/aide_lite.py release checksums
py -3 .aide/scripts/aide_lite.py release provenance
py -3 .aide/scripts/aide_lite.py release clean --dry-run
```

`release clean` is dry-run only in Q47. It lists generated release artifacts
that a future cleanup phase could remove, but deletes nothing.

Q48 consumes the generated bundle with:

```text
py -3 .aide/scripts/aide_lite.py release draft
py -3 .aide/scripts/aide_lite.py release draft-validate
py -3 .aide/scripts/aide_lite.py release draft-status
py -3 .aide/scripts/aide_lite.py release upload-plan
py -3 .aide/scripts/aide_lite.py release checklist
py -3 .aide/scripts/aide_lite.py release publication-boundary
```

Those commands generate review material only. They do not create tags, call
GitHub APIs, upload assets, or publish releases.

## Artifact Layout

Release artifacts are written under:

```text
.aide/release/dist/
```

The generated local bundle includes:

- `aide-lite-pack-v0.zip`
- `aide-lite-pack-v0.tar.gz`
- `aide-lite-pack-v0.checksums.json`
- `SHA256SUMS.txt`
- `manifest.yaml`
- `install.md`
- `CHANGELOG.preview.md`
- `RELEASE_NOTES.preview.md`
- `release-validation.json`
- `release-validation.md`
- `release-provenance.json`
- `release-assets.json`

Q47 also writes latest source-repo evidence:

- `.aide/release/latest-release-bundle.json`
- `.aide/release/latest-release-bundle.md`
- `.aide/release/latest-release-artifacts.json`
- `.aide/release/latest-release-validation.md`
- `.aide/release/latest-release-provenance.md`

These files are local evidence. They are not official release notes, not a
GitHub Release, and not target-repository truth.

Q48 additionally writes local GitHub Release draft evidence under
`.aide/release/github-release-*` and
`.aide/release/latest-github-release-draft.*`. Those files are also source-repo
review material, not target-repository truth.

## Archive Contents

Archives are built from `.aide/export/aide-lite-pack-v0/` with the stable root:

```text
aide-lite-pack-v0/
```

The archive includes pack files such as `manifest.yaml`, `checksums.json`,
`import-policy.yaml`, `install.md`, `export-report.md`, and `files/**`.
Release-level metadata such as install notes, checksum summaries, provenance,
validation, changelog preview, and release-note preview may also be included.

Archives must not include `.git/`, `.aide.local/`, `.env`, `secrets/**`, raw
prompt or response logs, source repo queue history outside the pack payload, or
source-generated target state as install truth.

## Checksum Validation

`release bundle` writes `aide-lite-pack-v0.checksums.json` and
`SHA256SUMS.txt`. `release checksums` recomputes the recorded artifact hashes
and fails if any recorded artifact is missing or mismatched.

`release validate` also extracts both archive formats into temporary fixture
directories and checks:

- expected archive root exists
- required pack files exist
- forbidden paths are absent
- portable AIDE Lite script exists under the pack payload
- import policy and install notes exist
- checksums validate

No target install apply is run.

## Install Notes Boundary

The generated `install.md` intentionally says that install, repair, upgrade,
rollback, and uninstall surfaces are observe/plan/dry-run by default. Target
repositories must run their own preflight and validation after extraction or
import. Target-specific memory, queue, evidence, golden tasks, tools, doctrine,
and manual guidance remain target-owned.

## Export Boundary

The portable export pack includes release-bundle policies, schemas, README,
commands, tests, golden tasks, and this reference doc. It excludes
source-generated `.aide/release/dist/**` artifacts and
`.aide/release/latest-release-*` reports as target truth.

## Publication Boundary

Q47 is not a public release. It creates local files only:

- no Git tag
- no GitHub Release
- no upload
- no package registry publication
- no branch mutation
- no active CI installation
- no target repo mutation

Q48 adds local GitHub Release draft generation on top of this bundle, with a
checksum-backed asset list, no-upload plan, and publication checklist. Q49
Dominium Fresh Install Preflight is next because downstream install readiness
still needs target-local evidence before any public readiness claim.
