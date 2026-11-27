import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_buduj_check():
    r = subprocess.run(["python", "scripts/buduj.py", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_leaderboard_exists():
    assert (ROOT / "leaderboard.md").exists()
