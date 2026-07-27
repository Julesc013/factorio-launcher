# Remaining risks

- The staged-candidate handoff repair is not yet hosted-accepted or merged.
- Qualification-03 must restart again from new empty remote-only clone, build,
  qualification, and revalidation roots after the source-changing repair.
  No prior closure, qualification, or partial stage root may be reused.
- The final immutable qualification and staged-candidate digests do not yet
  exist for the repaired source.
- Revalidation-02 has not completed staging.
- Coordinator `prepare` remains intentionally uninvoked.
- No real Factorio process, observer capture, baseline, permit issuance, human
  verdict, route promotion, signing, publication, or product Play route
  exists.
