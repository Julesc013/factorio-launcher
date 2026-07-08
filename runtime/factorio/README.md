# Factorio Runtime

Owns Factorio-specific product behavior behind the Factorio binding ABI.

May contain:

- install discovery and install validation
- instance and launch-template interpretation
- launch-plan construction helpers
- mods, modsets, saves, servers, and Mod Portal behavior
- account redaction and Factorio diagnostics
- compatibility shims when they are tied to a specific Factorio/runtime surface

Must not contain:

- universal setup mutation logic
- universal launcher command graph ownership
- GUI presentation code
- language-version folders such as `c11/` or `cpp11/`

Place implementation by product domain: `discovery/`, `launch/`, `modsets/`,
`mod_portal/`, and so on.
