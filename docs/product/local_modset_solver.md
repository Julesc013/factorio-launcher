# Local modset solver

`modsets plan`, `diff`, and `explain` resolve requested enabled and disabled
packages against bounded local inventory. Required dependencies are added;
optional and hidden-optional dependencies constrain ordering only when already
selected. Incompatibilities, version constraints, derived built-in virtual
packages, and the instance Factorio version are evaluated without portal or
network access.

Selection is deterministic: a compatible current lock wins, then an explicit
`--prefer name=version`, then the highest compatible local version, then stable
normalized filename order. Plans contain the complete explanation, state
fingerprint, budget usage, and a content-derived plan identifier. Package,
version, edge, state, backtrack, elapsed-time, and explanation-node budgets all
fail closed with `solver_budget_exceeded`.

Content's **Plan instance modset** and **Apply instance modset** offer both
name-only choices and explicit local versions such as `simple@2.0.0`. A name-only
choice retains the existing solver behavior, including current-lock preference.
An explicit version performs maintenance of the existing enabled set: the other
enabled locked packages stay requested, and the selected version must resolve
with their dependencies. It binds the selected instance's physical archive,
filename, source and SHA-256 from the reviewed snapshot. Missing, changed or
incompatible material refuses instead of falling back to another version.
Identical archives in other instances do not replace that selected-instance
binding. Invalid archives and installation-derived virtual packages are excluded
from explicit physical-version choices. The direct CLI's soft `--prefer`
ordering is unchanged; the public `presentation action` route accepts the same
explicit identity through `--mod name@version`.

In the ordinary terminal, activate Plan to review its form, set the local version,
then activate again to see the version diff. Apply requires a separate explicit
confirmation; editing its form clears an earlier confirmation. Review the
returned activation transaction in **Roll back instance modset** to restore the
exact prior activation and both locks. Rollback preserves the displaced state in
history and never reselects a newer available archive. Binary startup settings,
configuration overrides, selected saves and unrelated files remain outside these
activation writes.

`modsets apply` always resolves and verifies a plan before mutation. It preserves
the current `mod-list.json`, instance lock, and shared lock in managed activation
history, stages new Factorio-compatible state, revalidates archive identities and
external drift, and commits through the workspace transaction journal. The plan
identifier remains deterministic. Applied results also report `transaction_id`,
the identity to pass to `modsets rollback`. The first attempt retains the plan ID
as its transaction ID for existing consumers; retries use a separate ID and
preserve all previous history and journals. A retry verifies the restored file
presence, contents, backups, activation identity and journal-owned marker-only
staging. Active attempts, unknown staged content and inconsistent history refuse.
Apply and rollback share the existing instance configuration lock.
Immediately before publication, apply checks selected local archive identities,
the instance binding, and the exact presence and bytes of all three managed
files again. A detected external edit refuses without restoring over that edit.
Staging and history must retain their owned markers, safe paths, exact expected
files, staged output and original backup bytes. Changed or unknown staged data
remains intact for recovery. Failed applies retain the original failure detail
in both the refusal and journal after verified restoration.
`modsets rollback` verifies
both applied state and backup hashes before restoring the exact earlier state;
the displaced applied state remains in history.

`modsets verify` checks only the packages pinned by the lock. It reinspects local
archives and derives built-in packages from the instance's registered install;
lock metadata cannot grant built-in provenance. Unselected local versions do not
invalidate a solver selection. Human inventory and solver commands show the
owner's package identities, selection, changes, explanation and rollback ID.

Readiness additionally asks the content owner to verify activation: the bounded,
unlinked `mods/mod-list.json` must enable exactly the verified lock's selected
packages and `base`. Missing, malformed, duplicate, unsafe or mismatched entries
block joined preparation. Disabled unselected entries and unrelated metadata are
preserved; entry order and JSON formatting do not affect activation semantics.
The exact file identity and bytes still participate in readiness revisions.
The local and shared locks must agree when both are used for readiness.
Review and explicitly confirm **Apply instance modset** on Content to repair
activation, then refresh and confirm joined preparation for configuration and
the selected save. Joined preparation does not yet reconcile pending content in
that same request. Package-only `modsets verify` retains its existing meaning.

`modsets export` packages the exact verified `modset-lock.v1.json`, a typed
`modpack-manifest.v1.json`, and only the selected physical archives under `mods/`.
The manifest projects the canonical content lock, binds the SHA-256 and size of
the exact raw source lock and each selected archive, and carries a canonical
manifest identity. Trusted built-in packages remain virtual metadata; export
does not invent archives for them. Unselected versions, installation binaries,
credentials, and other instance content stay outside this selected closure.

The fixed settings paths `mods/mod-list.json` and `mods/mod-settings.dat` retain
their exact bytes when present. The manifest binds each path's presence, size,
and SHA-256. An absent file is explicitly bound as absent, with zero size and an
empty digest; no empty file is invented. A present empty file has the SHA-256 of
empty bytes and remains distinct from absence. Startup settings report
`sha256_bound` when present and `absent` when missing, including for virtual-only
packs. Older internal projections without admitted settings retain `unbound`.
Settings and source lock files are limited to 16 MiB each.

The staged archive must retain every bound entry's exact size and bytes. Source
checks after staging and immediately before publication also revalidate file
presence, object identities, bytes, and the instance/mods directories; linked
or redirected sources refuse. Export preserves reproducible ZIP output and
refuses existing targets without replacement. Genuine offline import and
reconstruction still require their own implementation and acceptance evidence.

Export cleanup binds created staging file identities and bytes, including the
transaction's exact ownership marker. It removes only those recorded children
relative to held parent directories and removes directories nonrecursively.
Observed unknown, replaced, or changed staging content remains for recovery;
writer failures retain staging for this policy, and generic recovery requires
review for the portable export strategy. Windows verifies and deletes each file
through one exclusive handle. POSIX verifies each recorded leaf before bounded
unlink; concurrent replacement of that same leaf between the final check and
unlink remains an open platform acceptance limit. This change does not establish
complete adversarial or cross-platform acceptance.

These commands never fetch missing mods, remove local archives, execute Factorio,
or grant setup, publication, or human-acceptance authority.
