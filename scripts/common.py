import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WYNIKI = ROOT / "wyniki"
SCHEMA = ROOT / "schema" / "wynik.schema.json"
ALIASES = ROOT / "schema" / "aliasy.json"
ADGR3_EMAIL = "".join(["1316","14110","+ad","gr3","@users.noreply.github.com"])
_USED_NAMES = set()


def load_aliases():
    if not ALIASES.exists():
        return {}
    data = json.loads(ALIASES.read_text(encoding="utf-8"))
    return data.get("aliases", {})


ALIASES_MAP = load_aliases()


def normalize_benchmark(name):
    if not isinstance(name, str):
        return name
    return ALIASES_MAP.get(name, name)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def family_for_model(model):
    m = (model or "").lower()
    if "token" in m or "fertility" in m:
        # tokenizer rows handled separately by benchmark, but keep fallback
        pass
    if m.startswith("slayer"):
        return "Slayer"
    if m.startswith("bielik"):
        return "Bielik"
    if m.startswith("lfm"):
        return "LFM"
    if m.startswith("qwen"):
        return "Qwen"
    if m.startswith("pythia"):
        return "Pythia"
    if m.startswith("eurollm"):
        return "EuroLLM"
    if m.startswith("speakleash") or m.startswith("pllum"):
        return "PLLuM"
    return "other"


def git_authors(repo, rel_path):
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "log", "--diff-filter=A", "--format=%H|%ae|%an", "--", str(rel_path)],
            capture_output=True, text=True, check=False,
        )
        out = [l for l in r.stdout.splitlines() if l.strip()]
        if not out:
            r = subprocess.run(
                ["git", "-C", str(repo), "log", "--format=%H|%ae|%an", "--max-count=5", "--", str(rel_path)],
                capture_output=True, text=True, check=False,
            )
            out = [l for l in r.stdout.splitlines() if l.strip()]
        return out
    except Exception:
        return []


def measured_by_for(repo_name, repo_path, rel_path):
    if repo_name.startswith("local:"):
        return "adgr3"
    authors = git_authors(repo_path, rel_path)
    if any(ADGR3_EMAIL.lower() in a.lower() for a in authors):
        return "adgr3"
    return "bench-team"


def source_url(repo_name, commit, rel_path, existing=None):
    if existing:
        return existing
    rel = str(rel_path).replace("\\", "/")
    if repo_name == "slayerlabs/benchmarks-fabryka-ai" and commit:
        return f"https://github.com/slayerlabs/benchmarks-fabryka-ai/blob/{commit}/{rel}"
    if repo_name == "adgr3/tokenizatorex" and commit:
        return f"https://github.com/adgr3/tokenizatorex/blob/{commit}/{rel}"
    if repo_name.startswith("local:"):
        return f"local://{repo_name[len('local:'): ]}/{rel}"
    return None


def comparable_reason(measured_by, comparable, fallback=None):
    if not comparable:
        return fallback or "not comparable"
    if measured_by == "adgr3":
        return "measured by this project (adgr3)"
    if measured_by == "bench-team":
        return "measured by Bench Team contributors in slayerlabs/benchmarks-fabryka-ai; reproduced here with link"
    if measured_by == "model-card":
        return "value from model card/reference; not measured by this project"
    return fallback or "unknown"


def sanitize(value):
    out = []
    for ch in str(value):
        if ch.isalnum() or ch in "._-":
            out.append(ch)
        else:
            out.append("_")
    s = "".join(out).strip("_")
    while "__" in s:
        s = s.replace("__", "_")
    return s[:60] or "x"


def record_key(record):
    return (
        record.get("model"),
        normalize_benchmark(record.get("benchmark")),
        record.get("metric"),
        record.get("subset"),
        json.dumps(record.get("settings", {}), sort_keys=True, ensure_ascii=False),
        record.get("source", {}).get("repo"),
        record.get("source", {}).get("path"),
    )


_SEEN_KEYS = set()
_SEEN_LOOSE = set()


def loose_key(record):
    return (
        record.get("model"),
        normalize_benchmark(record.get("benchmark")),
        record.get("metric"),
        str(record.get("score")),
        str(record.get("n")),
        record.get("source", {}).get("repo"),
        record.get("source", {}).get("path"),
    )


def write_record(record):
    WYNIKI.mkdir(parents=True, exist_ok=True)
    record["benchmark"] = normalize_benchmark(record.get("benchmark"))
    key = record_key(record)
    lk = loose_key(record)
    if key in _SEEN_KEYS or lk in _SEEN_LOOSE:
        return None
    _SEEN_KEYS.add(key)
    _SEEN_LOOSE.add(lk)
    base = "__".join([
        sanitize(record["model"]),
        sanitize(record["benchmark"]),
        sanitize(record.get("metric", "metric")),
        sanitize(record.get("settings", {}).get("variant") or record.get("subset") or "default"),
    ])
    name = base + ".json"
    if name in _USED_NAMES:
        i = 2
        while "{}_{}.json".format(base, i) in _USED_NAMES:
            i += 1
        name = "{}_{}.json".format(base, i)
    _USED_NAMES.add(name)
    path = WYNIKI / name
    text = json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    return path
