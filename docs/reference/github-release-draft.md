# GitHub Release Draft

Q48 defines how AIDE turns the Q47 local AIDE Lite release bundle into a
reviewable GitHub Release draft without publishing anything.

Q48 does not create Git tags, push tags, call GitHub APIs, create releases,
upload assets, publish packages, mutate branches, install CI, install into
target repositories, or apply install, repair, upgrade, rollback, or uninstall
plans.

## Lifecycle

The release-draft lifecycle is:

1. validate the Q47 local release bundle
2. collect local bundle assets
3. collect changelog and release-note previews
4. generate Markdown and JSON release drafts
5. generate an asset list with checksums
6. generate a no-upload plan
7. generate a publication checklist
8. generate a publication boundary report
9. validate the draft
10. review
11. future manual or explicit publication

Q48 implements local draft generation and validation only.

## Commands

```text
py -3 .aide/scripts/aide_lite.py release draft
py -3 .aide/scripts/aide_lite.py release draft-validate
py -3 .aide/scripts/aide_lite.py release draft-status
py -3 .aide/scripts/aide_lite.py release upload-plan
py -3 .aide/scripts/aide_lite.py release checklist
py -3 .aide/scripts/aide_lite.py release publication-boundary
```

The `upload-plan` command writes and prints a preview only. It does not upload.

## Generated Files

Q48 writes:

- `.aide/release/github-release-draft.md`
- `.aide/release/github-release-draft.json`
- `.aide/release/github-release-assets.json`
- `.aide/release/github-release-upload-plan.md`
- `.aide/release/github-release-upload-plan.json`
- `.aide/release/github-release-checklist.md`
- `.aide/release/github-release-checklist.json`
- `.aide/release/github-release-publication-boundary.md`
- `.aide/release/github-release-draft-validation.json`
- `.aide/release/github-release-draft-validation.md`
- `.aide/release/latest-github-release-draft.md`
- `.aide/release/latest-github-release-draft.json`

These files are source-repo evidence and review material. They are not a
published release and are not target-repository truth.

## Asset Inputs

The draft reads required Q47 assets from `.aide/release/dist/`:

- `aide-lite-pack-v0.zip`
- `aide-lite-pack-v0.tar.gz`
- `aide-lite-pack-v0.checksums.json`
- `SHA256SUMS.txt`
- `manifest.yaml`
- `install.md`
- `CHANGELOG.preview.md`
- `RELEASE_NOTES.preview.md`

It may also reference validation, provenance, and asset-index JSON/Markdown
files. Every present asset gets a size and SHA-256 value.

## Suggested Tag

If no stable SemVer contract exists, Q48 suggests a draft-only tag:

```text
aide-lite-pack-v0-draft-<short-sha>
```

The tag is only text in the draft. Q48 never creates or pushes it.

## Publication Checklist

The checklist records source state, validation gates, artifact gates, security
gates, target install caveats, publication blockers, and manual review items.
Dirty source state is recorded for review. Missing required assets, failed
checksums, or failed validation become blockers.

## Publication Boundary

Q48 reports:

- tag_created: no
- github_release_created: no
- upload_performed: no
- network_api_call: no
- branch_mutation: no
- active_ci_installed: no

If a future phase publishes a release, it must have explicit operator approval,
reviewed tag naming, reviewed assets, passing validation, passing secret scan,
and a reviewed checklist.

## Export Boundary

The portable export pack includes Q48 policies, schemas, commands, tests,
golden tasks, and this reference doc. It excludes generated release draft
outputs such as `.aide/release/github-release-draft.*`,
`.aide/release/github-release-assets.json`,
`.aide/release/github-release-upload-plan.*`,
`.aide/release/github-release-checklist.*`, and
`.aide/release/latest-github-release-draft.*` as target truth.

## Next Phase

Q49 Dominium Fresh Install Preflight is next because the local bundle and
release draft are ready for review, but downstream install readiness still must
be proven in the target repository before any public readiness claim.
