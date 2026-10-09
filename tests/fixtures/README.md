# Scanner fixtures

- `hp-m283fdw-capabilities.xml`: read-only capture from the user's HP Color LaserJet
  MFP M283fdw, 2026-10-08. Serial, UUID and embedded URLs redacted. Confirms parser
  behavior only; prior physical test evidence is recorded in plans.
- `profiles-disjoint.xml`, `profiles-reference-range.xml`: synthetic regressions,
  not captures or claims that any particular vendor was tested.
- Inline fixtures cover asymmetric-only DPI, missing metadata and malformed refs.

Never commit documents, credentials, addresses, serials or identifying URLs.
