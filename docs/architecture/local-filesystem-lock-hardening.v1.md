# Local Filesystem Lock Hardening v1

FacMan run and recovery locks use one shared stable-handle primitive. The lock
object owns an open platform handle from successful creation until verified
release. Pathname metadata alone is never deletion authority.

## Platform ownership

On Windows, FacMan creates or opens the lock with `CreateFileW`, rejects
reparse points, requires a single-link disk file, and records the volume serial
and 64-bit file index returned by `GetFileInformationByHandle`. The held handle
denies write and delete sharing. Release revalidates both the handle and the
current path identity, then marks that same open file for deletion with
`SetFileInformationByHandle`.

On POSIX, FacMan uses `O_NOFOLLOW`, an exclusive nonblocking `flock`, `fstat`,
and a single-link regular-file requirement. It records device and inode. Before
unlink, `lstat` must prove that the path still names that exact device/inode;
after unlink the containing directory is flushed where supported.

The lock metadata records the stable identity. Run-lock release also rereads
the held content and verifies the operation token and identity before removal.

## Filesystem boundary

Windows remote or unclassified drive types refuse. macOS requires the
`MNT_LOCAL` flag. Linux accepts only reviewed local filesystem magic values
covering ext, XFS, Btrfs, tmpfs/ramfs, overlay, ZFS, F2FS, and bcachefs.
Unknown types fail closed.

This is a conservative local-filesystem policy, not an SMB, NFS, cloud-sync,
cluster, container-host, or multi-host guarantee. Adding another filesystem
requires a reviewed identity and lock-semantics record plus target proof.

## Substitution behavior

- A linked or reparse lock refuses.
- An active stable handle makes a second owner contend.
- A stale run lock is opened and exclusively owned before its metadata is
  evaluated; deletion applies only if the held identity still matches its path.
- If an attacker unlinks/replaces a POSIX lock or renames its parent, release
  refuses and leaves the replacement untouched.
- Where Windows sharing prevents the hostile rename/removal, the original lock
  remains held and releases normally.
- Recovery cleanup uses the same stable release and converts identity drift
  into a structured refusal.

The proof covers local single-host behavior only. It does not enable
`run.execute` or promote real Factorio isolation.
