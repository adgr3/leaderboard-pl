# Dataset Card: leaderboard-pl-results

## Summary

`adegier/leaderboard-pl-results` is the planned dataset name for public benchmark result records used by `adgr3/leaderboard-pl`. This repository contains the local preparation files under `hf/`; nothing is published by this task.

## Contents

- JSON records compatible with `schema/wynik.schema.json`
- One record per measured result or explicit `not run`/`null` entry
- Provenance fields: source repo/path/commit/SHA-256, settings, deviations, comparability

## Intended use

- Public leaderboard tables and filters
- Auditable benchmark result tracking
- Reproducible comparison when benchmark, metric, and settings match

## Limitations

- Results come from multiple sources and protocols; compare only compatible records.
- Some source repositories have unknown license files; check source terms before reuse.
- `null`/`not run` records indicate missing execution, not a measured score.

## License

Repository code is MIT. Source data licenses may differ; see `README.md` section "Licencje danych".
