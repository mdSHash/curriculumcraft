# mojibake-guard-skip — this guard's own source contains the example
# bigrams used as the scan pattern; skip it to avoid a self-match.
"""Mojibake CI guard — scan Python source files for double-encoded UTF-8.

When an Arabic string is mistakenly re-encoded as UTF-8 a second time
(e.g. file saved as Windows-1256 then read as UTF-8), the resulting bytes
look like nonsense Latin-1 letters instead of clean Arabic. This is hard
to spot visually and silently produces garbled DOCX output for Arabic
books — see book #2 in the early-2026 review where chapter titles came
out as 'PP uu rr ee' / 'replacement chars' instead of 'الرياضيات البحتة'.

Run on every Python file under backend/ and report any file containing
the canonical double-encoded UTF-8 bigrams (defined below as escape
sequences so this file does NOT itself trip the scan). Exit non-zero if
any are found so this can be wired into CI / pre-commit later.

Usage:
    python backend/scripts/check_mojibake.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Bigrams that appear when Arabic UTF-8 is interpreted as Windows-1252
# and then re-encoded as UTF-8. Hitting any of these in a Python source
# file is a strong signal the file is double-encoded. Defined as escape
# sequences so this guard's own source doesn't trip the scan.
MOJIBAKE_BIGRAMS = [
    "Ø§",  # alef
    "Ù„",  # lam
    "Ø±",  # ra
    "Ø¨",  # ba
    "Ù‡",  # ha
    "Ø¬",  # jim
    "Ø¯",  # dal
    "Ù†",  # nun
    "Ù…",  # mim
    "Ù‚",  # qaf
    "Ø¥",  # alef-with-hamza-below
    "Ø£",  # alef-with-hamza-above
    "Ø¢",  # alef-madda
    "Ù‰",  # alef-maksura
]


def scan(root: Path) -> int:
    """Scan all .py files under root for mojibake bigrams.

    Returns 0 if clean, 1 if any matches found.
    """
    pattern = re.compile("|".join(re.escape(b) for b in MOJIBAKE_BIGRAMS))
    bad: list[tuple[Path, int, str]] = []

    for py in root.rglob("*.py"):
        if any(part in {"venv", ".venv", "__pycache__", "node_modules"} for part in py.parts):
            continue
        try:
            text = py.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        # Skip files that opt out (this guard itself, plus tests that
        # need to embed mojibake examples as test fixtures).
        if "mojibake-guard-skip" in text:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if pattern.search(line):
                bad.append((py.relative_to(root), i, line.strip()[:120]))
                break  # one report per file is enough

    if not bad:
        print(f"OK: scanned files under {root}, no mojibake detected")
        return 0

    print(f"FAIL: mojibake detected in {len(bad)} file(s):")
    for path, line, snippet in bad:
        print(f"  {path}:{line}: {snippet}")
    print(
        "\nFix: re-save the offending file as UTF-8 (no BOM). In VS Code: "
        "Reopen with Encoding > Windows-1256 > Save with Encoding > UTF-8."
    )
    return 1


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    sys.exit(scan(repo_root))
