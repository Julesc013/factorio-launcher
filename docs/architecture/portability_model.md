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
