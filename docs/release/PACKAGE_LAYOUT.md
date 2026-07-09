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
```

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

Package-manager shims can expose `facman`, `facman-tui`, `facmand`, and the GUI
entrypoint under `/usr/bin` or `/usr/local/bin`.
