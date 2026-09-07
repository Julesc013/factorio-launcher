# Local source-static provider canary

The source canary selects one reviewed local USK checkpoint with an exact clean HEAD, Git tree
and local task ref. The external custody JSON and its explicitly supplied digest bind the
selected checkpoint to a non-authorizing ROOT review receipt. This permits disposable
source-static SDK-candidate builds only. A review receipt never establishes stable-main
identity, installed SDK acceptance, provider adoption or release authority.

`tools/provider_local_source_canary.py` consumes the actual FacMan source and existing stable
ULK source. It writes a separate external candidate lock, validates USK before and after
execution, and binds consumer source bytes, compiler commands, build identity, executable hashes
and raw logs. The five tracked release-input files are hashed before and after. Candidate build
identity must state that it differs from the tracked provider and is not release-coherent.

The CMake local source path requires both `FACMAN_PROVIDER_LOCAL_SOURCE_CUSTODY_FILE` and its
SHA256, `source`, `static`, and the existing explicit SDK-candidate class. Other modes refuse
these inputs. Ordinary source custody still requires the selected origin ref and reachability;
installed SDK and stable import rules are unchanged. No remote ref is invented and no
publication is needed for local evidence.
Assume-unchanged, skip-worktree and sparse tracked entries refuse before source admission,
because a clean Git status can conceal modified or missing tracked bytes. These source
observations do not establish an atomic build lease.

Physical tracked files are also compared to each reviewed HEAD blob with bounded raw reads.
Only regular files are admitted; gitlinks, symlinks, reparse indirection and control-bearing
paths refuse. Custom filter and working-tree-encoding attributes refuse before status checks;
no Git clean filter executes. A fixed UTF-8 source-text extension/name list permits CRLF to LF
normalization, with NUL-bearing/nontext mismatches refused. Every raw SHA256 and byte count is
retained alongside its Git blob and normalization rule. The source-static runner compares
these observations before configure, before build, after build and after tests. Limits are
10,000 files, 8 MiB per file and 256 MiB total. This is sequential source observation.

Windows qualification builds actual CLI, setup gateway, standalone transaction/archive tests and
FacManSetup, with parallelism capped at four. The gateway fixtures test stored ZIP, a raw
Deflate block, incomplete product layout, missing input, floating version and inconsistent
CRC/truncation refusals. The self-setup fixture uses stored and zlib-compressed Deflate
payloads, tests consistent-but-wrong payload CRC and truncation, then exercises install,
verification, owned-file damage, repair, foreign-content uninstall refusal and bounded clean
uninstall. No synthetic Factorio file is executed. Explicit retained fixture paths preserve raw
responses and failed effects; CRC apply refusal may retain provider staging and state, and must
never publish the target or alter the foreign sentinel/input bytes.

This is one source-consumer slice of PROVIDER-CANARY-01. Installed static/shared and relocation
proof, consumer interruption/replay, protected successful commit authority,
generation/stale-owner recovery, retained cleanup and provider adoption remain open. Existing
legacy commit preparation is observational and does not close its post-observation publication
race. No automatic recovery, genuine human/game experience or Beta qualification is claimed.
