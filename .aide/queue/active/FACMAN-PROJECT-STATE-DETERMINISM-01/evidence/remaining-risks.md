# Remaining risks

- The human-verdict producer still accepts a requested disposition and must be
  repaired before any `prepare`.
- Machine observations and irreducible operator attestations are not yet
  separated.
- Python and native approval paths remain incompatible; the Python approval
  path must be removed or unified.
- Authority-bearing evidence reads and archive extraction still require the
  stable native I/O boundary.
- The historical qualification cannot be reused after those repairs.

No item above permits Factorio execution or route promotion.
