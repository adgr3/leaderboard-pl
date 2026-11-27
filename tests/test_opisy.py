import glob
import json
from pathlib import Path

from scripts.opisy import load_opisy, validate_opisy

ROOT = Path(__file__).resolve().parents[1]


def test_opisy_cover_all_benchmarks():
    opisy = load_opisy()
    names = {json.loads(Path(p).read_text(encoding="utf-8"))["benchmark"] for p in glob.glob(str(ROOT / "wyniki" / "*.json"))}
    errors = validate_opisy(opisy, names)
    assert errors == []
