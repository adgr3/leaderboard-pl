import json
from datetime import datetime, timezone
from pathlib import Path

from common import ROOT, family_for_model, sha256_file, write_record, measured_by_for, source_url, comparable_reason

TX = ROOT / "_zrodla" / "tokenizatorex"

def git_head(repo):
    import subprocess
    try:
        return subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None

COMMIT = git_head(TX)

# fertility benchmark
bench = json.loads((TX / "results" / "benchmark.json").read_text(encoding="utf-8"))
src_rel = Path("results") / "benchmark.json"
src_full = TX / src_rel
sha = sha256_file(src_full)
pl_words = sum(v for k, v in bench["meta"]["words"].items() if k != "angielski")
for row in bench["rows"]:
    record = {
        "model": row["name"],
        "model_revision": None,
        "family": "Tokenizer" if row["group"] != "nasz" else "TOKENIZATOREX",
        "benchmark": "Token fertility (tokens per word, 7 Polish domains)",
        "benchmark_version": "TKX-A",
        "data_revision": "corpus word counts in results/benchmark.json meta",
        "subset": "Polish domains (excluding English)",
        "metric": "fertility (tokens/word)",
        "score": row["fertility_pl"],
        "stderr": 0.0,
        "ci95": None,
        "n": pl_words,
        "n_empty": None,
        "n_overflow": None,
        "settings": {
            "vocab": row["vocab"],
            "group": row["group"],
            "note": row.get("note"),
            "roundtrip_all": all(row.get("roundtrip", {}).values()) if isinstance(row.get("roundtrip"), dict) else None,
            "tokens_pl": row.get("tokens_pl"),
            "vs_tokenizatorex_pl": row.get("vs_tokenizatorex_pl"),
        },
        "harness": "TOKENIZATOREX benchmark script",
        "judge": None,
        "deviations": [],
        "comparable_to_reference": {"comparable": True, "reason": comparable_reason(measured_by_for("adgr3/tokenizatorex", TX, src_rel), True) + " on same corpus"},
        "source": {
            "repo": "adgr3/tokenizatorex",
            "path": str(src_rel).replace("\\", "/"),
            "commit": COMMIT,
            "sha256": sha,
            "url": source_url("adgr3/tokenizatorex", COMMIT, src_rel),
            "pr_status": None,
        },
        "measured_by": measured_by_for("adgr3/tokenizatorex", TX, src_rel),
        "date": datetime.fromtimestamp(src_full.stat().st_mtime, tz=timezone.utc).date().isoformat(),
        "status": "measured",
        "null_reason": None,
    }
    write_record(record)

# BPB / bytes per token
metrics = json.loads((TX / "results" / "metrics.json").read_text(encoding="utf-8"))
src_rel2 = Path("results") / "metrics.json"
src_full2 = TX / src_rel2
sha2 = sha256_file(src_full2)
for row in metrics["rows"]:
    record = {
        "model": row["name"],
        "model_revision": None,
        "family": "Tokenizer" if not row["name"].startswith(("superbpe", "tokenizatorex")) else "TOKENIZATOREX",
        "benchmark": "Held-out corpus (bytes per token)",
        "benchmark_version": "TKX held-out",
        "data_revision": "heldout corpus in results/metrics.json",
        "subset": "full held-out corpus",
        "metric": "bytes per token",
        "score": row["bytes_per_token"],
        "stderr": 0.0,
        "ci95": None,
        "n": metrics.get("heldout_bytes"),
        "n_empty": None,
        "n_overflow": None,
        "settings": {
            "vocab": row["vocab"],
            "tokens": row["tokens"],
            "fertility": row["fertility"],
            "chars_per_token": row["chars_per_token"],
            "roundtrip": row["roundtrip"],
            "vocab_used": row.get("vocab_used"),
            "superword_share": row.get("superword_share"),
            "transition": row.get("transition"),
            "vs_cl100k": row.get("vs_cl100k"),
            "heldout_words": metrics.get("heldout_words"),
            "heldout_chars": metrics.get("heldout_chars"),
        },
        "harness": "TOKENIZATOREX metrics script",
        "judge": None,
        "deviations": [],
        "comparable_to_reference": {"comparable": True, "reason": comparable_reason(measured_by_for("adgr3/tokenizatorex", TX, src_rel2), True) + " on same held-out corpus"},
        "source": {
            "repo": "adgr3/tokenizatorex",
            "path": str(src_rel2).replace("\\", "/"),
            "commit": COMMIT,
            "sha256": sha2,
            "url": source_url("adgr3/tokenizatorex", COMMIT, src_rel2),
            "pr_status": None,
        },
        "measured_by": measured_by_for("adgr3/tokenizatorex", TX, src_rel2),
        "date": datetime.fromtimestamp(src_full2.stat().st_mtime, tz=timezone.utc).date().isoformat(),
        "status": "measured",
        "null_reason": None,
    }
    write_record(record)

print("importuj_tokenizatorex: done")
