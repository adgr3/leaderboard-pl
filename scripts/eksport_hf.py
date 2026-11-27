import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WYNIKI = ROOT / "wyniki"
OPISY = ROOT / "opisy" / "benchmarki.yaml"
OUT_DATA = ROOT / "hf" / "dataset" / "data"
SPACE = ROOT / "hf" / "space"


def load_opisy():
    try:
        import yaml
    except Exception:
        return {}
    if not OPISY.exists():
        return {}
    return yaml.safe_load(OPISY.read_text(encoding="utf-8")) or {}


def load_records():
    recs = []
    for p in sorted(WYNIKI.glob("*.json"), key=lambda p: p.name):
        d = json.loads(p.read_text(encoding="utf-8"))
        d["_file"] = p.name
        recs.append(d)
    recs.sort(key=lambda r: (r.get("benchmark",""), r.get("model",""), r.get("metric",""), r.get("measured_by",""), r.get("_file","")))
    return recs


def is_percent(r):
    m = (r.get("metric") or "").lower()
    b = (r.get("benchmark") or "").lower()
    if "byte_perplexity" in m or "perplexity" in m or "bytes per token" in m or "fertility" in m:
        return False
    if any(x in m for x in ("acc", "pass", "accuracy")) or m in {
        "prompt_level_strict_acc","overall_acc","exact_match (flexible-extract)","ewok","omniscience_index"
    }:
        s = r.get("score")
        if s is None:
            return any(h in b for h in ("ifeval","ifbench","ruler","hle","aa-lcr","automationbench","bfcl"))
        if 0 <= s <= 1.5:
            return True
        if 0 <= s <= 100 and any(h in b for h in ("ifeval","ifbench","ifstruct","multi-if","bfcl","automationbench","aa-omniscience","aa-lcr","ruler","hle","terminal-bench","humanity")):
            return True
    return False


def score_display(r):
    s = r.get("score")
    if s is None:
        return None
    if is_percent(r) and 0 <= s <= 1.5:
        return s * 100
    return float(s)


def flatten(records, opisy):
    rows = []
    for r in records:
        b = r.get("benchmark")
        o = opisy.get(b, {})
        src = r.get("source") or {}
        comp = r.get("comparable_to_reference") or {}
        rows.append({
            "model": r.get("model"),
            "family": r.get("family"),
            "benchmark": b,
            "benchmark_display_pl": o.get("display_pl"),
            "benchmark_family": o.get("family"),
            "metric": r.get("metric"),
            "direction": o.get("direction"),
            "score": r.get("score"),
            "score_display": score_display(r),
            "stderr": r.get("stderr"),
            "n": r.get("n"),
            "status": r.get("status"),
            "null_reason": r.get("null_reason"),
            "measured_by": r.get("measured_by"),
            "date": r.get("date"),
            "deviations": "; ".join(r.get("deviations", [])) if r.get("deviations") else "",
            "comparable": bool(comp.get("comparable")) if isinstance(comp, dict) else None,
            "comparable_reason": comp.get("reason") if isinstance(comp, dict) else None,
            "source_repo": src.get("repo"),
            "source_path": src.get("path"),
            "source_commit": src.get("commit"),
            "source_sha256": src.get("sha256"),
            "source_url": src.get("url"),
            "file": r.get("_file"),
        })
    return rows


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fieldnames})


def write_parquet(path, rows):
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except Exception as e:
        raise RuntimeError("pyarrow required for parquet export") from e
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path, compression="zstd")


def build_dataset_card(opisy, rows):
    benches = sorted(opisy.values(), key=lambda x: x.get("display_pl",""))
    srcs = sorted({r.get("source_repo") for r in rows if r.get("source_repo")})
    return f"""---
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

{chr(10).join(f'- `{s}`' for s in srcs)}

## Notes

- Compare only rows with the same benchmark, metric, and comparable settings.
- `null` / `not run` rows are explicit missing results, not measured scores.
- This dataset is a compilation; underlying benchmark/data terms may differ by source.

## License

Compilation: CC-BY-4.0. Source terms may differ; see repository README.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    opisy = load_opisy()
    records = load_records()
    rows = flatten(records, opisy)
    bench_rows = []
    for k in sorted(opisy.keys()):
        v = dict(opisy[k])
        v['benchmark'] = k
        bench_rows.append(v)

    OUT_DATA.mkdir(parents=True, exist_ok=True)
    SPACE.mkdir(parents=True, exist_ok=True)

    jsonl_path = OUT_DATA / 'results.jsonl'
    parquet_path = OUT_DATA / 'results.parquet'
    csv_path = OUT_DATA / 'results.csv'
    bench_path = OUT_DATA / 'benchmarks.jsonl'
    card_path = ROOT / 'hf' / 'dataset' / 'README.md'

    fieldnames = list(rows[0].keys()) if rows else []
    # deterministic content
    jsonl_content = ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in rows)
    bench_content = ''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in bench_rows)
    card_content = build_dataset_card(opisy, rows)

    # space copies
    space_results = SPACE / 'results.json'
    space_bench = SPACE / 'benchmarks.json'
    space_results_content = json.dumps(rows, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    space_bench_content = json.dumps(bench_rows, ensure_ascii=False, sort_keys=True, indent=2) + '\n'

    if args.check:
        for path, content in [(jsonl_path, jsonl_content), (bench_path, bench_content), (card_path, card_content), (space_results, space_results_content), (space_bench, space_bench_content)]:
            if not path.exists():
                print(f'{path.relative_to(ROOT)} missing'); raise SystemExit(1)
            if path.read_text(encoding='utf-8') != content:
                print(f'{path.relative_to(ROOT)} out of date'); raise SystemExit(1)
        if not parquet_path.exists():
            print('hf/dataset/data/results.parquet missing'); raise SystemExit(1)
        if not csv_path.exists():
            print('hf/dataset/data/results.csv missing'); raise SystemExit(1)
        # parquet/csv checked by regeneration to temp compare? cheap enough: regenerate and compare bytes
        import tempfile, filecmp, shutil
        with tempfile.TemporaryDirectory() as td:
            td=Path(td)
            tp=td/'r.parquet'; tc=td/'r.csv'
            write_parquet(tp, rows); write_csv(tc, rows, fieldnames)
            if tp.read_bytes()!=parquet_path.read_bytes():
                print('hf/dataset/data/results.parquet out of date'); raise SystemExit(1)
            if tc.read_text(encoding='utf-8')!=csv_path.read_text(encoding='utf-8'):
                print('hf/dataset/data/results.csv out of date'); raise SystemExit(1)
        print('OK: hf export matches data')
        return

    jsonl_path.write_text(jsonl_content, encoding='utf-8')
    bench_path.write_text(bench_content, encoding='utf-8')
    card_path.write_text(card_content, encoding='utf-8')
    write_parquet(parquet_path, rows)
    write_csv(csv_path, rows, fieldnames)
    space_results.write_text(space_results_content, encoding='utf-8')
    space_bench.write_text(space_bench_content, encoding='utf-8')
    print('written', jsonl_path, parquet_path, csv_path, bench_path, card_path, space_results, space_bench)


if __name__ == '__main__':
    main()
