# Platform I/O Durability v1

`runtime/platform/fl_file_io` is the narrow boundary for security-sensitive
file lifetime and durable output operations.

Stable inputs use wide `CreateFileW` handles with reparse-point inspection on
Windows and `open(..., O_NOFOLLOW)` plus `fstat` on POSIX. The handle records
device/object identity, regular-file type, size, and link count and can
revalidate that identity without reopening the path.

Durable outputs use exclusive create, sequential bounded writes, file flush,
and containing-directory flush where POSIX exposes it. No-replace commit uses
write-through move on Windows and link/unlink plus directory flush on POSIX.
Exact-object removal opens without following links and compares identity before
unlinking.

`runtime/platform/fl_system_services` supplies real UTC time and OS-random IDs.
The core interfaces also provide fixed clocks and sequence IDs for deterministic
tests. UTF-8 conversion enters and leaves native paths only through
`path_from_utf8` and `path_to_utf8`.

The archive layer is the first migrated consumer. Remaining critical writers
are tracked by `critical_io_check` and its monotonically shrinking exception
set.
