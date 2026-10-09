# Scanner fixtures

- `hp-m283fdw-capabilities.xml`: read-only capture from the user's HP Color LaserJet
  MFP M283fdw, 2026-10-08. Serial, UUID and embedded URLs redacted. Confirms parser
  behavior only; prior physical test evidence is recorded in plans.
- `profiles-disjoint.xml`, `profiles-reference-range.xml`: synthetic regressions,
  not captures or claims that any particular vendor was tested.
- `epson-et4950-issue5-regions.xml`: report-derived fragment from
  [issue #5](https://github.com/wleonhardt/ha-escl-scan/issues/5), reviewed
  2026-10-09. The duplex fields and simplex maximums come from the ET-4950
  report; surrounding XML is synthetic scaffolding. This is not a full capture
  and contains no invented profiles, firmware or platen dimensions. Exercises
  parser-to-coordinator region selection, not physical Epson acceptance.
- Inline fixtures cover asymmetric-only DPI, missing metadata and malformed refs.

Never commit documents, credentials, addresses, serials or identifying URLs.
