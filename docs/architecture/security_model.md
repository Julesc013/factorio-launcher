# Security Model

The normative pre-beta threat model is
[threat_model.md](threat_model.md). The short operational rules are:

- foreign-owned installs are read-only
- raw identifiers never become managed filesystem paths directly
- persistent creation is no-clobber by default
- recursive cleanup requires proof that FacMan owns the output root
- diagnostics fail closed when a sensitive format cannot be parsed safely
- execution refuses until the effective Factorio write boundary is proven
- setup mutation, network access, and credential access are unavailable until
  their dedicated capability gates are enabled

Tokens must live in an OS credential store when account support lands. A
manifest may contain an account reference, never the token itself.
