# Server planning without execution

Server creation now stores `factorio.server_profile.v2` records with instance and
save selection, launch profile, server/map settings, visibility and autosave
policy, description, tags, allowlist and banlist references, and credential
references. Plaintext password, token, secret, or credential fields are refused.

`servers inspect`, `validate`, `plan`, and `diff` are read-only. Planning requires
a registered instance, a structurally recognized local save, a verified modset,
and bounded valid settings. It emits reviewed `server-settings.json`,
`map-gen-settings.json`, `map-settings.json`, a headless launch plan, required
inputs, expected output roots, port declaration, effects, risks, and preflight.
Every report states that no process started, no network socket opened, and no
firewall rule changed.

`servers export` produces a reproducible portable ZIP with generated configs,
hash manifest, and no secrets, Factorio binary, or execution scripts. Saves are
excluded unless `--include-save` is explicitly supplied. `servers start`, `stop`,
and `rcon` remain unavailable with their existing structured refusal.
