# Portability Model

Portable workspaces should avoid absolute paths where possible. When a record
must include an absolute path, it must declare whether that path is portable,
machine-local, or foreign-owned.

Exports must exclude:

- raw passwords
- tokens unless explicitly encrypted
- Steam session data
- private account files
- unmarked machine-local paths

## Native user roots

`facman::platform::user_paths()` is the only shared-code entry point for native
user directories. It returns absolute, normalized roots for home, data,
configuration, cache, and state:

- Windows uses `SHGetKnownFolderPath` for Profile, RoamingAppData, and
  LocalAppData; it does not infer these locations from path strings.
- Linux honors absolute XDG roots and otherwise uses the freedesktop fallbacks
  below an absolute `HOME` (`.local/share`, `.config`, `.cache`, and
  `.local/state`). Relative XDG values are ignored.
- macOS uses an absolute `HOME`, `Library/Application Support`, and
  `Library/Caches`.

Failure to obtain an absolute home/root is explicit. The platform layer does
not silently fall back to the current working directory.

Native Windows smoke proof covers the selected implementation in the current
development environment. Linux and macOS support remains target-runner evidence
and must not be inferred from shared source review or Windows compilation.
