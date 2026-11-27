import json
from datetime import datetime, timezone
from pathlib import Path

from common import ROOT, family_for_model, sha256_file, write_record, measured_by_for, source_url, comparable_reason

BIELIK = ROOT.parent / "bielik-if-pl"

def load(name):
    return json.loads((BIELIK / "wyniki" / name).read_text(encoding="utf-8"))

for fname, benchname in [("ifeval.json", "IFEval (Bielik IF-PL local)"), ("ifbench.json", "IFBench (Bielik IF-PL local)")]:
    d = load(fname)
    p = BIELIK / "wyniki" / fname
    sha = sha256_file(p)
    metrics = d["metrics"]
    ci = d.get("ci", {})
    n = d.get("counts", {}).get("prompts", d.get("n"))
    for metric_key, score in metrics.items():
        ci_entry = ci.get(metric_key)
        ci95 = None
        if ci_entry:
            ci95 = {"lower": ci_entry["lo"], "upper": ci_entry["hi"], "level": 0.95, "method": ci_entry.get("method")}
        record = {
            "model": "bielik-11b-v3.1",
            "model_revision": None,
            "family": "Bielik",
            "benchmark": benchname,
            "benchmark_version": d.get("dataset"),
            "data_revision": d.get("source_file"),
            "subset": "full test set",
            "metric": metric_key,
            "score": score,
            "stderr": 0.0 if ci95 is None else None,
            "ci95": ci95,
            "n": n,
            "n_empty": None,
            "n_overflow": d.get("truncation", {}).get("count") if isinstance(d.get("truncation"), dict) else None,
            "settings": d.get("evaluation", {}),
            "harness": "Bielik IF-PL evaluation",
            "judge": None,
            "deviations": ["local Bielik IF-PL protocol; not part of Bench Team harness"],
            "comparable_to_reference": {"comparable": False, "reason": "different harness from Bench IFEval"},
            "source": {
                "repo": "local:bielik-if-pl",
                "path": "wyniki/" + fname,
                "commit": None,
                "sha256": sha,
                "url": source_url("local:bielik-if-pl", None, "wyniki/" + fname),
                "pr_status": None,
            },
            "measured_by": "adgr3",
            "date": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).date().isoformat(),
            "status": "measured",
            "null_reason": None,
        }
        write_record(record)

print("importuj_bielik_ifpl: done")