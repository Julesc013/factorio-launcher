# Remaining risks

- Evidence filesystem reads, hashing, JSON parsing, durable writes, and archive
  inspection still require the separate stable-I/O repair.
- Environment-derived protected-resource paths still need to be snapshotted once
  and bound through preflight/provider revalidation.
- A fresh source-closed candidate qualification is still required after the
  evidence-I/O repair.
- Revalidation 02 has not been created or prepared. Human Pass/Fail/Inconclusive
  evidence remains absent.
- No exact Play route has been promoted and product Play remains unavailable.
