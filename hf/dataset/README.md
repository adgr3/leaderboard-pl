---
license: cc-by-4.0
language:
  - pl
  - en
pretty_name: leaderboard-pl-results
task_categories:
  - text-generation
  - question-answering
tags:
  - leaderboard
  - benchmarks
  - polish
  - evaluation
configs:
  - config_name: default
    data_files:
      - split: train
        path: data/results.parquet
---

# leaderboard-pl-results

Public dataset of benchmark result records used by `adgr3/leaderboard-pl`.

## Contents

- `data/results.parquet` and `data/results.jsonl` — flattened records from `wyniki/*.json`
- `data/benchmarks.jsonl` — benchmark descriptions from `opisy/benchmarki.yaml`
- Each row keeps provenance: source repo/path/commit/SHA256/URL, deviations, comparability, status.

## Schema (results)

- `model`, `family`, `benchmark`, `benchmark_display_pl`, `benchmark_family`
- `metric`, `direction`, `score`, `score_display`, `stderr`, `n`
- `status`, `null_reason`, `measured_by`, `date`
- `deviations`, `comparable`, `comparable_reason`
- `source_repo`, `source_path`, `source_commit`, `source_sha256`, `source_url`, `file`

## Sources

- `adgr3/tokenizatorex`
- `local:bielik-if-pl`
- `slayerlabs/benchmarks-fabryka-ai`

## Notes

- Compare only rows with the same benchmark, metric, and comparable settings.
- `null` / `not run` rows are explicit missing results, not measured scores.
- This dataset is a compilation; underlying benchmark/data terms may differ by source.

## License

Compilation: CC-BY-4.0. Source terms may differ; see repository README.
