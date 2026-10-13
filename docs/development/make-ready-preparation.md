# Make Ready preparation

The ordinary `readiness.prepare` action and the Instances **Make Ready**
control prepare one currently admitted component. The request binds the
current presentation revision, instance, profile and menu or selected-save
intent, with explicit confirmation and the existing idempotency identity.

A needed routing configuration repair runs first. Once configuration is
already current, an available selected-save context owner can record the
exact declared context. Each effect retains its own existing domain journal.
The returned `factorio.make_ready_preparation_result.v1` payload reports
partial preparation, the actual completed owner command, transaction and
plan digest, and the need for a fresh revision. It does not grant execution
or a permit or report whole-instance readiness.

After interrupted execution, the original semantic request retains its
unknown outcome; replay cannot redispatch it. Use the ordinary domain
recovery path, observe a fresh presentation revision and submit the next
applicable action with a new identity. Existing configuration and selected
save preparation controls remain available.

This component preserves stored launch overrides, custom routing INI bytes
and identity where admitted, selected content/settings and save archives.
Installation/content/profile reconstruction and complete Make Ready
orchestration remain open. The compiled gallery harness establishes button
wiring and interpretation of separately supplied actual receipts; live
click-to-backend dispatch, real game and human experience remain separate
acceptance. Windows source fixtures do not establish other-host or Beta
qualification.

Linux missing-INI and new selected-save-reference publication retain the inode
bound before the first write. Publication links the opened staging descriptor
into the held destination directory without replacing an existing leaf. The
owner alone can read the exact journal-bound two-link staging/destination pair;
ordinary pinned readers still require one link. Before removing staging, it
checks both names, device/inode, link count and intended bytes. Recovery can
finish that pair or verify the same singly-linked destination after interrupted
cleanup. Foreign same-byte objects, unknown staging, symlinks, additional links
and substituted parents remain refused. Link and cleanup metadata flush failures
retain the journal for recovery; successful recovery flushes the parent again.

Linux uses the existing local-filesystem/operation-lock policy and requires the
held-descriptor publication facility to be available. Its locks are advisory:
uncooperative writes and rename are detected at bounded observations, not
prevented. Staging removal retains the POSIX final compare/unlink window; this
does not claim safety against a namespace writer racing that last interval or
power-loss recovery. Source fixtures on tmpfs do not qualify ext4, physical
hosts, produced packages, real Factorio or human experience.

macOS missing-INI and selected-save-reference owners explicitly use an observed
staging-name hard link inside the held sibling directory. The separate helper
checks the retained and named staging inode, intended bytes and parent before
publication, then verifies the destination against that same prebound inode.
The default descriptor-source publication API still clones on macOS and remains
unchanged. A different destination inode is never adopted by matching bytes.
These owners use the same journal-bound one/two-link recovery and owned staging
cleanup as Linux; a created but unverified destination requires recovery and is
preserved. Unbound staging, foreign same-byte objects, changed bytes and unsafe
parents remain refused and preserved.

The macOS helper additionally retains a source compare/link interval: Darwin
`linkat` accepts a source name, not an expected-inode argument. A namespace writer
racing that interval can cause a foreign inode to acquire the destination name.
The owner refuses that object and preserves both names; it never replaces a
destination or removes the foreign staging object. This is an explicit opt-in
to the existing cooperative-writer/advisory-lock policy, not a descriptor-atomic
publication or malicious-writer exclusion claim. Staging cleanup also retains
the POSIX compare/unlink interval. Actual macOS native and public owner tests are
required for qualification; source checks do not establish physical APFS hosts,
power-loss recovery, produced packages, real game, human experience or Beta.
The helper uses `linkat` with flags zero so a raced final symlink is not followed.
Darwin kernels accept that flag value; filesystems that do not support this link
operation refuse it and preserve the bound staging file. API source inspection
and a newer hosted macOS result do not qualify the declared minimum macOS host.

Existing-INI reconciliation is admitted on Windows fixed-local-NTFS and supported
local Linux/macOS filesystems through the retained-original-inode owner. Its
source acceptance is distinct from named physical-host and power-loss evidence;
missing-file publication grants no broader configuration or Play authority.

`tests/test_macos_delivered_tui.py` defines two mandatory Darwin consumer tests
for `macos_portable_tui_x64`: ordinary linear Make Ready and actual PTY full-screen
Make Ready with terminal restoration. They require explicit matching native
candidate/build paths and stage one package through the existing package factory,
which checks clean source and exact provider/build metadata. They relocate the
package, remove its write permissions and run from a consumer directory outside
the checkout with backend/source overrides removed and an empty executable PATH.
Fixture setup and fresh CLI queries use that same produced executable.

Both reuse the Linux ordinary selected-save scenario: changed observation cancels
confirmation without effects, missing routing preparation changes the revision,
and a fresh confirmation publishes selected-save context. Its independent
receipt, owner-journal, digest, inode and input-preservation assertions remain;
neither step grants Play. Full-screen input uses real typed keys, requires complete
terminal frames and checks original terminal flags, cursor and screen restoration
on exit. Darwin missing artifacts or incoherent metadata fail rather than skip.

Darwin's raw-to-canonical `TCSANOW` restoration sets the kernel's `PENDIN`
retyping state even when the application restores the saved attributes correctly.
The fixture records immediate post-exit attributes, queries `FIONREAD` on the
held slave, requires zero queued scenario input, and then compares every saved
attribute exactly. This queue query completes pending retyping; it neither
rewrites attributes nor flushes input. The candidate PTY receives no `tcsetattr`
after exit. A separate control PTY first proves the same transition with an empty
queue and with known pending input, verifies exact settings after the query,
and reads back the pending bytes without loss. These observed attributes, queue
counts and control input/output bytes are retained in each mode's hashed
`terminal-state.json`; full-screen requires all three candidate sessions, while
linear requires zero. This follows the same mechanism in Apple's
[pinned current XNU](https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/kern/tty.c#L1358)
and [macOS 13-era XNU](https://github.com/apple-oss-distributions/xnu/blob/xnu-8792.41.9/bsd/kern/tty.c#L1247).
It adds no runtime workaround and does not establish a minimum-host result.

The tests print compact package/source/build/provider identities and hashes with
their actual result into the job log. The existing validated CLI integration
source observation corroborates the same source/providers/build; it does not
establish a TUI composition or release-custody claim. Full terminal output and validated effects
are retained beneath the build root's owned `delivered-tui-evidence` directory,
with their hashes in each result. Before runner cleanup, each mode also emits one
`delivered-tui-custody` record: zlib-compressed, base64-encoded canonical JSON
containing the exact terminal/effect file bytes, lengths, hashes and result.
The record binds the canonical JSON and compressed payload hashes; the separate
compact result binds those custody hashes. Raw files are capped at 4 MiB combined,
canonical JSON at 6 MiB, and encoded payload at 512 KiB. Overflow fails without
truncation. The root observer must decode, verify and persist these files from the
actual job log before integration. Non-Darwin skips and static source checks are
not delivered macOS acceptance. Actual candidate-bound Darwin results remain
required; minimum macOS, named physical hosts, real Factorio, human experience,
complete Make Ready and Beta qualification remain separate.
