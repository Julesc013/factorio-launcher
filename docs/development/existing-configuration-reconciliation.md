# Existing routing configuration reconciliation

The ordinary Prepare routing configuration action restores a missing INI or
repairs the two exact routing values in an existing config/config.ini. Existing
comments, line endings, unrelated keys and user settings retain their bytes.
Missing routing keys are added conservatively. Duplicate or ambiguous path
sections/keys, inline comments on routing values, BOM/NUL/bare-CR input, empty
files, legacy config-path.cfg and unsupported targets remain unchanged.

The existing-file owner is qualified separately from missing-file publication.
It binds the original and intended bytes, exact original file and parent
identities, readable owner/group/DACL and creation/attribute inputs, and current
install/profile/content/settings/selected-save inputs to its durable journal.
Device and file identifiers use canonical unsigned decimal strings to retain all
64 bits. Numeric, noncanonical and overflowing journal identifiers are refused
before file access; bounded byte sizes remain exact JSON integers.
A checkpoint admits writing before the first stream effect. One retained
exclusive original file handle spans admission, prefix writes, flush/truncation,
verification, journal completion and exact owned lock removal. Read-only input
handles keep their original rights.

Recovery accepts only original/intended or journal-reachable prefix byte states
before verified completion. After its effect-verification checkpoint, recovery
can verify and finish journal closure but cannot write the stream again.
Unfamiliar bytes, a substituted file/parent, extra links, readonly files,
changed readable metadata or context, incompatible writers and changed journal
ownership remain preserved for review. Recovery never restores old permissions.

The operation changes only the unnamed stream on Windows fixed local NTFS.
It does not replace the file or set security descriptors or alternate streams.
Opaque SACL equality, frozen foreign ADS/security writers and power-loss
recovery are unqualified. Content writes may update write/access timestamps and
the archive/derived NORMAL attributes; those are not restoration promises.

This component does not establish full Make Ready, Play authority, game
compatibility, installed GUI experience, other-host or Beta acceptance. Prior
SDK q02 timeout and original CI63 attribution remain unresolved/unconfirmed.

The POSIX retained rewrite primitive is available for native qualification,
while existing-INI planner, reconcile and recovery mutation admission remains
Windows only. Linux missing-file publication has a separate qualification.
An already-current INI remains a read-only observation before the POSIX mutation
refusal; primitive availability must not enable its application owner.

The Linux/macOS primitive retains the original single-link inode opened relative
to a held parent with no-follow O_RDWR and a nonblocking exclusive advisory
flock. It classifies both held descriptors with the same local-filesystem policy
used by operation locks. Before each pwrite and ftruncate and after each flushed
prefix, it compares complete bounded bytes, namespace identity and readable
metadata. Uncooperative writers and renames still have intervals between those
observations and effects; flock does not provide Windows sharing denial.
No replacement, chmod/chown, ACL setter or xattr restoration is performed.

POSIX metadata identities are platform tagged and bounded to 64 KiB including
encoding. They include mode, uid/gid and sorted readable xattr names and values;
at most 256 readable attributes are admitted.
Linux access ACLs use their system.posix_acl_access xattr representation. Darwin
also includes birth time, flags and the external extended ACL representation.
Atime, mtime and ctime are explicitly excluded from the persistent identity;
mtime/ctime are still checked for drift during a single byte observation.
Unreadable/oversized metadata, set-ID bits, read-only mode, security xattrs and
Darwin content-sensitive compression or non-nodump flags are refused. Metadata
not exposed by readable enumeration is outside this scoped identity; equality
does not establish inaccessible metadata preservation. Native host/filesystem
qualification, including named Intel macOS APFS targets, remains outstanding.
Process-loss reachable prefixes are supported; power-loss recovery is unclaimed.
