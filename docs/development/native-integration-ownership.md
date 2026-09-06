# Native integration ownership

Work item: FACMAN-0.1-ALPHA6-NATIVE-INTEGRATION-OWNERSHIP-01.

FacManSetup checks the contents of the current-user Start Menu shortcut and
uninstall registration against the requested installation before removing them.
A matching filename or registry key name alone does not establish ownership.

The shortcut must target FacMan.exe directly within one generation beneath the
requested install root, use that generation as its working directory, and contain
no custom arguments. Registration must name FacMan, have the same absolute
InstallLocation, and have the exact maintenance uninstall command for that
location. Unknown values, nested registry keys, unreadable entries, relative
targets and foreign locations are preserved. Path comparisons use Windows ordinal
case-insensitive comparison after lexical normalization; missing generations
remain recognizable after the file lifecycle has removed their payload.

Removal first observes both entries. A foreign or unreadable entry blocks all
deletion and records the refusal. Otherwise a pending receipt is written before
the first effect. Each effect is followed by a progress receipt. Partial failures
and lost completion responses remain incomplete; a retry observes actual objects
again and skips entries already absent.

The Windows adapter rechecks a shortcut through the same file handle used for
deletion. The handle denies concurrent write/delete sharing; the shell link is
decoded from the bytes read through that handle, without path resolution or
target execution. Reparse points are refused. FileDispositionInfo removes that
opened object rather than reopening a pathname.

Registration observation and deletion share a registry transaction. The adapter
refuses nested keys and never falls back to recursive deletion. Concurrent
non-transacted writes cause transaction rollback; transaction failures remain
recoverable errors. These APIs are supported from Windows Vista, and this change
was compiled with Windows SDK 10.0.26100.0 targeting Windows 10.0.19045.
See Microsoft's [RegOpenKeyTransactedW contract](https://learn.microsoft.com/en-us/windows/win32/api/winreg/nf-winreg-regopenkeytransactedw)
and [RegDeleteKeyTransactedW contract](https://learn.microsoft.com/en-us/windows/win32/api/winreg/nf-winreg-regdeletekeytransactedw).

The removal receipt is stored at
integration-receipts/uninstall.v1.json below the requested setup state root.
Its schema is facman.windows_integration_removal.v1; phase is pending, blocked,
incomplete or complete. Shortcut and registration observations/progress are
recorded independently. Writes keep one exclusive temporary-file handle open through flushing and
FileRenameInfo publication. A failed replacement preserves the previous receipt
and retains the temporary object without pathname-based cleanup. Install
receipts use the same object-bound publisher.

Install and repair now refuse observed foreign entries, write a pending
integration receipt before native writes, and preserve partial effects on failure.
They no longer delete fixed shortcut/registry locations as an unconditional
rollback. Their existing v1 receipt gains a phase field. **The install replacement
path still uses separate observation and mutation calls**: atomic replacement,
recovery of an interrupted shortcut write or partially populated registration,
and coordination across the payload/native phases remain part of the separately
queued native setup recovery work. This ownership change does not qualify those
operations as race-free or fully recoverable.

Validation uses injected effects for ownership refusal, identity substitution at
the deletion boundary, native-effect failures, completion response loss, receipt
failures and retry idempotence. Windows adapter identity cases are enabled only when the adapter target is built;
the injected coordinator remains tested when self-setup is disabled.
Predicate tests cover generation paths, custom
arguments, registry commands and unknown content. The real adapter compiles and
links into FacManSetup. The existing disposable setup lifecycle also passes with
--no-shell-integration. A disposable file fixture attempts temporary-file replacement/deletion at the
flush/publication boundary and checks published bytes plus failed-publication
retention. No real HKCU or Start Menu mutation is part of these tests;
candidate-bound disposable-host native qualification remains required.