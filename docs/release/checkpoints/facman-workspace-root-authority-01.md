# FACMAN-WORKSPACE-ROOT-AUTHORITY-01

Date: 2026-08-04

FacMan now classifies an exact workspace root as `missing`, `empty_unowned`,
`facman_owned`, `legacy_facman`, `foreign_nonempty`, `link_or_reparse`, or
`inspection_failed` before broad workspace initialization.

A missing or empty root receives an exclusive `.facman-root.v1.json` ownership
marker before managed directories or the workspace manifest are written. The
marker binds the FacMan owner, canonical root path, workspace identity, and
claim mode. A live no-follow directory object and stable marker file are
revalidated before and after initialization.

Legacy roots require the separate `adopt_legacy_workspace_root` call. Adoption
adds only the exclusive ownership marker and can be rolled back by exact marker
identity without modifying the legacy manifest or its content. Foreign,
linked/reparse, changed, and inconclusive roots refuse mutation and return a
specific recovery action.

This WorkUnit grants only FacMan workspace-root ownership. It opens no
installed-software mutation, Universal Setup operation, product execution,
successor route, permit, signing, or publication authority.
