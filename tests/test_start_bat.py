"""start.bat runs with delayed expansion, where cmd treats every "!" as the
start of a !variable! and drops it: a bare "!" in a command (the Python
version check once read `!= (3, 11)`, BUG-0235) silently changes the command."""

import re
from pathlib import Path

START_BAT = Path(__file__).resolve().parents[1] / "start.bat"


def test_no_bare_exclamation_mark_in_a_delayed_expansion_script() -> None:
    text = START_BAT.read_text(encoding="utf-8", errors="replace")
    assert re.search(r"enabledelayedexpansion", text, re.I)
    bad = []
    for no, line in enumerate(text.splitlines(), 1):
        if re.match(r"\s*(rem\b|::)", line, re.I):
            continue
        if "!" in re.sub(r"![A-Za-z_][A-Za-z0-9_]*!", "", line):
            bad.append(f"{no}: {line.strip()}")
    assert bad == []
