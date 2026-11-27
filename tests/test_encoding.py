import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERN = re.compile(r"[A-Za-z]\?[a-z]")


def tracked_files():
    out = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
    files = []
    for line in out.splitlines():
        p = ROOT / line
        if p.suffix.lower() in {".py", ".md", ".json"} and p.is_file():
            files.append(p)
    return files


def test_no_lost_polish_chars():
    for p in tracked_files():
        text = p.read_text(encoding="utf-8")
        assert not PATTERN.search(text), f"lost char pattern in {p}"


def test_leaderboard_has_markers():
    text = (ROOT / "leaderboard.md").read_text(encoding="utf-8")
    assert "★" in text
    assert "Ranking główny" in text
