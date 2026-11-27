import json
import subprocess
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schema" / "wynik.schema.json").read_text(encoding="utf-8"))
ALIASES = json.loads((ROOT / "schema" / "aliasy.json").read_text(encoding="utf-8")).get("aliases", {})
WYNIKI = ROOT / "wyniki"
BENCH_SRC = ROOT / "_zrodla" / "benchmarks-fabryka-ai"
TX_SRC = ROOT / "_zrodla" / "tokenizatorex"
BIELIK_SRC = ROOT.parent / "bielik-if-pl"


def load_all():
    files = sorted(WYNIKI.glob("*.json"))
    assert files, "no records"
    recs = []
    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        recs.append((f, data))
    return recs


def test_all_records_valid():
    for f, data in load_all():
        jsonschema.validate(data, SCHEMA)


def test_measured_by_enum_and_source():
    for f, data in load_all():
        assert data["measured_by"] in {"adgr3", "bench-team", "model-card"}
        url = data.get("source", {}).get("url")
        reason = data.get("source", {}).get("url_missing_reason")
        assert url or reason, f"missing source url/reason: {f.name}"


def test_no_duplicate_benchmark_names_after_aliases():
    for f, data in load_all():
        b = data.get("benchmark")
        assert b not in ALIASES, f"alias not normalized: {f.name} -> {b}"
        assert b != "ifeval"


def test_source_sha_matches():
    for f, data in load_all():
        src = data["source"]
        path = None
        repo = src["repo"]
        if repo == "slayerlabs/benchmarks-fabryka-ai":
            path = BENCH_SRC / src["path"]
        elif repo == "adgr3/tokenizatorex":
            path = TX_SRC / src["path"]
        elif repo.startswith("local:"):
            continue
        if path and path.exists():
            import hashlib
            h = hashlib.sha256(path.read_bytes()).hexdigest()
            assert h == src["sha256"], (f, h, src["sha256"])


def test_nasze_pomiary_count_matches():
    recs = [d for _, d in load_all()]
    adgr3 = [r for r in recs if r.get("measured_by") == "adgr3"]
    text = (ROOT / "leaderboard.md").read_text(encoding="utf-8")
    # report/section must state adgr3 count
    assert f"adgr3: {len(adgr3)}" in text
    assert "## Przegląd (nasze pomiary)" in text


@pytest.mark.skipif(not (BENCH_SRC.exists() and TX_SRC.exists() and BIELIK_SRC.exists()), reason="requires local _zrodla and bielik-if-pl sources")
def test_import_twice_identical():
    def snapshot():
        return {p.name: p.read_bytes() for p in WYNIKI.glob("*.json")}
    cmds = [
        ["python", "scripts/importuj_bench.py"],
        ["python", "scripts/importuj_tokenizatorex.py"],
        ["python", "scripts/importuj_bielik_ifpl.py"],
    ]
    for c in cmds:
        subprocess.run(c, cwd=ROOT, check=True)
    first = snapshot()
    for c in cmds:
        subprocess.run(c, cwd=ROOT, check=True)
    second = snapshot()
    assert first == second
