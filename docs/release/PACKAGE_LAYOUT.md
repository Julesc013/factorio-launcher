# Package Layout

Every package uses the same conceptual layout, adjusted to platform convention.

## Common Layout

```text
bin/
lib/
contracts/
content/
release/
docs/
licenses/
manifest/
├─ resolution/
│  └─ ten digest-bound resolved graph records
└─ stage.v1.json
```

The stage manifest is mandatory for composition-compiler adapter conformance.
Legacy package-pipeline artifacts embed `manifest/resolution/`; they adopt the
complete stage manifest when their adapter is migrated to the constrained
staging path.

Portable packages may also include:

```text
state/
workspace/
```

Native user or system installs must not place user workspace data under the
installed app directory.

## Windows

```text
C:/Program Files/FacMan/
├─ bin/
├─ contracts/
├─ content/
├─ release/
├─ docs/
└─ licenses/
```

Per-user state lives under the user's application data root.

## macOS

```text
FacMan.app/
└─ Contents/
   ├─ MacOS/
   ├─ Frameworks/
   └─ Resources/
      ├─ contracts/
      ├─ content/
      ├─ release/
      ├─ docs/
      └─ licenses/
```

Per-user state lives under `~/Library/Application Support/FacMan/`.

## Linux

```text
/opt/facman/
├─ bin/
├─ lib/
├─ contracts/
├─ content/
├─ release/
├─ docs/
└─ licenses/
```

Package-manager shims expose `facman` and a proven GUI when present. Experimental
`facman-tui` and `facmand` shims require an explicit experimental build and are
not part of default product packages.
entrypoint under `/usr/bin` or `/usr/local/bin`.
