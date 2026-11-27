import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# patterns checked for public-repo hygiene; built dynamically so this test file
# does not contain literal banned tokens.
BANNED = [
    "ku" + "rs",
    "zaj" + "ęcia",
    "zaj" + "ecia",
    "dis" + "cord",
    "D:" + "\\",
    "C:" + "\\Users",
    "@gm" + "ail",
    "gran" + "tos",
]
SELF = "tests/test_publicznosc.py"


def test_no_banned_strings_in_tracked_files():
    out = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
    bad = []
    for rel in out.splitlines():
        if rel == SELF:
            continue
        p = ROOT / rel
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            text = p.read_bytes().decode("latin1", errors="ignore")
        low = text.lower()
        for pat in BANNED:
            if pat.lower() in low:
                bad.append((rel, pat))
    assert not bad, f"banned strings found: {bad[:20]}"
