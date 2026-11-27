import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from common import (
    ROOT,
    WYNIKI, family_for_model, sha256_file, write_record,
    measured_by_for, source_url, comparable_reason, normalize_benchmark,
)

BENCH = ROOT / "_zrodla" / "benchmarks-fabryka-ai"
HLE = ROOT.parent / "bench" / "hle"
if not HLE.exists():
    HLE = ROOT / "_zrodla" / "benchmarks-fabryka-ai"

def git_head(repo):
    try:
        return subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None

BENCH_COMMIT = git_head(BENCH)
HLE_COMMIT = git_head(HLE)

GENERIC_DEVIATIONS = {"see README.md, Deviations", "see README.md Deviations", "see source README Deviations", "see README, Deviations"}


def clean_reason_text(value):
    if not isinstance(value, str):
        return value
    s = value.strip()
    if s.startswith("none (") and s.endswith(")"):
        s = s[len("none ("):].strip()
        if s.endswith(")"):
            s = s[:-1].strip()
    return s


def concrete_deviation(d, value):
    if not isinstance(value, str):
        return value
    s = value.strip()
    if s in GENERIC_DEVIATIONS:
        for key in ("reason", "score_null_reason", "null_reason"):
            cand = d.get(key)
            if isinstance(cand, str) and cand.strip():
                return cand.strip()
    return clean_reason_text(s)

def make_source(repo_name, repo, rel_path, commit, pr_status=None, url=None):
    full = repo / rel_path
    mb = measured_by_for(repo_name, repo, rel_path)
    return {
        "repo": repo_name,
        "path": str(rel_path).replace("\\", "/"),
        "commit": commit,
        "sha256": sha256_file(full),
        "url": source_url(repo_name, commit, rel_path, existing=url),
        "pr_status": pr_status,
    }, mb

# --- results.jsonl (log-likelihood benchmarks) ---
jsonl = BENCH / "benchmarks" / "results" / "results.jsonl"
for line in jsonl.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    src_rel = row["source"]
    source, mb = make_source("slayerlabs/benchmarks-fabryka-ai", BENCH, src_rel, BENCH_COMMIT, pr_status="merged (main)")
    # read source JSON for provenance / ci95
    src_json = json.loads((BENCH / src_rel).read_text(encoding="utf-8"))
    obs = src_json.get("observations", [{}])[0]
    ci95 = obs.get("ci95")
    data_revision = src_json.get("provenance", {}).get("inventory_commit") or row.get("protocol")
    task = None
    for t in src_json.get("tasks", []):
        if t.get("task_id") == obs.get("task_id"):
            task = t
            break
    subset = task.get("split") if task else None
    if subset:
        subset = "{} split".format(subset)
    else:
        subset = "full test set"
    record = {
        "model": row["model"],
        "model_revision": row.get("revision"),
        "family": family_for_model(row["model"]),
        "benchmark": normalize_benchmark(row["benchmark"]),
        "benchmark_version": row.get("legacy_id"),
        "data_revision": data_revision,
        "subset": subset,
        "metric": row["metric"],
        "score": row["value"],
        "stderr": row.get("se"),
        "ci95": ci95,
        "n": row.get("n"),
        "n_empty": None,
        "n_overflow": None,
        "settings": {
            "variant": row.get("variant"),
            "protocol": row.get("protocol"),
            "unit": row.get("unit"),
            "language": row.get("language"),
            "category": row.get("category"),
            "repo": row.get("repo"),
            "harness": row.get("harness"),
            "review_flag": row.get("review_flag"),
            "review_notes": row.get("review_notes", []),
        },
        "harness": {"name": row.get("harness"), "commit": None},
        "judge": None,
        "deviations": row.get("review_notes", []) if row.get("review_flag") not in (None, "ok") else [],
        "comparable_to_reference": {"comparable": True, "reason": comparable_reason(mb, True)},
        "source": source,
        "measured_by": mb,
        "date": datetime.fromtimestamp((BENCH / src_rel).stat().st_mtime, tz=timezone.utc).date().isoformat(),
        "status": "measured",
        "null_reason": None,
    }
    # deviations from review notes only if flagged; keep review_notes separate in settings
    if row.get("review_flag") in (None, "ok"):
        record["deviations"] = []
    write_record(record)

# --- API benchmark result files ---
import glob as _glob
api_files = sorted(_glob.glob(str(BENCH / "research" / "api-benchmarks" / "*" / "results" / "*.json")))
for full in api_files:
    p = Path(full)
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    if not (isinstance(d, dict) and "model" in d and ("score" in d or "value" in d) and "benchmark" in d and "metric" in d):
        continue
    rel = p.relative_to(BENCH)
    source, mb = make_source("slayerlabs/benchmarks-fabryka-ai", BENCH, rel, BENCH_COMMIT, pr_status="merged (main)")
    score = d.get("score", d.get("value"))
    settings = d.get("settings", {})
    if not isinstance(settings, dict):
        settings = {"value": settings}
    deviations = d.get("deviations")
    if isinstance(deviations, str):
        deviations = [deviations]
    elif not isinstance(deviations, list):
        deviations = [] if deviations is None else [str(deviations)]
    deviations = [concrete_deviation(d, x) for x in deviations]
    null_reason = d.get("score_null_reason") or d.get("null_reason")
    if score is None and null_reason is None:
        if isinstance(deviations, list) and deviations:
            null_reason = deviations[0]
        else:
            null_reason = "not run or null result in source"
    if isinstance(null_reason, str):
        null_reason = clean_reason_text(null_reason)
    status = "null" if (score is None or null_reason) else "measured"
    if status == "measured":
        null_reason = None
    judge = settings.get("judge", d.get("judge"))
    record = {
        "model": d["model"],
        "model_revision": d.get("model_revision", d.get("revision")),
        "family": family_for_model(d["model"]),
        "benchmark": normalize_benchmark(d["benchmark"]),
        "benchmark_version": d.get("data"),
        "data_revision": d.get("data"),
        "subset": settings.get("subset") or d.get("subset"),
        "metric": d["metric"],
        "score": score,
        "stderr": d.get("stderr"),
        "ci95": d.get("ci95"),
        "n": d.get("n", d.get("n_judged")),
        "n_empty": d.get("n_empty"),
        "n_overflow": d.get("n_overflow", d.get("answers_cut_at_length")),
        "settings": settings,
        "harness": d.get("harness"),
        "judge": judge,
        "deviations": deviations,
        "comparable_to_reference": {"comparable": True, "reason": comparable_reason(mb, True)},
        "source": source,
        "measured_by": mb,
        "date": d.get("date"),
        "status": status,
        "null_reason": null_reason,
    }
    if record["date"] is None:
        record["date"] = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).date().isoformat()
    write_record(record)

# --- HLE (open PR #358) ---
hle_result = HLE / "research" / "api-benchmarks" / "hle" / "results" / "bielik-11b-v3.1.json"
if hle_result.exists():
    d = json.loads(hle_result.read_text(encoding="utf-8"))
    settings = d.get("settings", {})
    source, mb = make_source("slayerlabs/benchmarks-fabryka-ai", HLE, hle_result.relative_to(HLE), HLE_COMMIT, pr_status="open (#358)", url="https://github.com/slayerlabs/benchmarks-fabryka-ai/pull/358")
    record = {
        "model": d["model"],
        "model_revision": None,
        "family": family_for_model(d["model"]),
        "benchmark": normalize_benchmark(d["benchmark"]),
        "benchmark_version": d.get("data"),
        "data_revision": d.get("data"),
        "subset": settings.get("subset"),
        "metric": d["metric"],
        "score": d["score"],
        "stderr": d.get("stderr"),
        "ci95": None,
        "n": d.get("n"),
        "n_empty": None,
        "n_overflow": d.get("truncated") if isinstance(d.get("truncated"), int) else None,
        "settings": {**settings, "samples_per_item": d.get("samples_per_item")},
        "harness": d.get("harness"),
        "judge": settings.get("judge_main"),
        "deviations": [
            f"{d.get('samples_per_item')} sample per item (methodology: 10)",
            f"{d.get('n_unresolved_counted_incorrect')} unjudged answers counted incorrect",
            "see source README Deviations",
        ],
        "comparable_to_reference": {"comparable": True, "reason": comparable_reason(mb, True) + "; judge agreement 100%"},
        "source": source,
        "measured_by": mb,
        "date": d.get("date"),
        "status": "measured",
        "null_reason": None,
    }
    write_record(record)
    # null record for Slayer not run
    null_source = dict(source)
    null_source["sha256"] = source["sha256"]
    record_null = {
        "model": "slayer1b-1.09-k70000",
        "model_revision": "adfaf3fd5402bc7f3adbfe077798f20262979433",
        "family": "Slayer",
        "benchmark": d["benchmark"],
        "benchmark_version": d.get("data"),
        "data_revision": d.get("data"),
        "subset": settings.get("subset"),
        "metric": d["metric"],
        "score": None,
        "stderr": None,
        "ci95": None,
        "n": None,
        "n_empty": None,
        "n_overflow": None,
        "settings": {"note": "Slayer not run — maintainer decision / no GPU"},
        "harness": d.get("harness"),
        "judge": None,
        "deviations": [],
        "comparable_to_reference": {"comparable": False, "reason": "not run"},
        "source": null_source,
        "measured_by": mb,
        "date": d.get("date"),
        "status": "null",
        "null_reason": "not run — maintainer decision (Slayer not run in PR #358)",
    }
    write_record(record_null)

print("importuj_bench: done")
