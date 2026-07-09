# Update Model

FacMan update checks are report-only. Update application is a Universal Setup
operation.

## Check

`facman update check` reads a release index and reports:

```text
current version
available version
channel
compatible package lanes
required migrations
download size
checksums
signature status
```

The check must not mutate install state, workspace state, release channels, or
downloaded payloads.

## Apply

`facman update apply` delegates to the bundled Universal Setup helper:

```text
FacMan frontend
  asks Universal Setup to apply update

Universal Setup
  downloads or reads payload
  verifies payload
  stages payload
  commits install mutation
  writes install state and audit
  can rollback
```

FacMan must not overwrite its own install directory directly.

## Channels

Supported release channels are:

```text
stable
beta
nightly
pinned
```

Build kinds are separate:

```text
dev
ci
beta
rc
release
hotfix
```

`pinned` means the user selected an exact artifact and no automatic channel
movement is allowed.
