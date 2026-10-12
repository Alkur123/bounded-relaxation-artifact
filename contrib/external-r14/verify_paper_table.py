"""Check that paper 14's per-subject table matches the artifact, row by row.

The house rule for this paper is that a value not in the released artifact does
not appear in the prose. A twenty-two row table transcribed by hand is exactly
where that rule gets broken quietly, so it is checked instead of trusted. Every
numeric column is compared for every subject, not just the totals, because a
totals-only check passes while individual rows are wrong.

    python verify_paper_table.py        # exits non-zero on any mismatch

A mutation probe belongs with this: change one digit in the paper and it must
fail by name.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
TEX = pathlib.Path(os.environ["R14_PAPER_TEX"]) if os.environ.get("R14_PAPER_TEX") else HERE.parents[1] / "backend" / "paper" / "bounded_relaxation.tex"

res = json.loads((HERE / "external_r14_results.json").read_text(encoding="utf-8"))
adj = json.loads((HERE / "adjudication.json").read_text(encoding="utf-8"))
SURFACE = re.compile(adj["_surface_regex"], re.I)

verdict_of = {(e["subject"], e["module"], e["line"]): e["verdict"]
              for e in adj["entries"]}

# Display name in the paper -> subject key in the artifact.
ROW_TO_KEY = {
    "ControlArena": "control-arena", "Inspect AI": "inspect_ai",
    "AgentDojo": "agentdojo", "NeMo Guardrails": "nemo-guardrails",
    "LLM Guard": "llm-guard", "Guardrails AI": "guardrails",
    "Presidio": "presidio", "garak": "garak",
    "LlamaFirewall": "llama-firewall", "OpenAI Agents": "openai-agents",
    "Petri": "petri", "Giskard": "giskard", "Rebuff": "rebuff",
    "ModelScan": "modelscan", "TruLens": "trulens",
    "Semantic Kernel": "semantic-kernel", "AutoGen": "autogen",
    "CrewAI": "crewai", "LangGraph": "langgraph", "Vigil": "vigil",
    "bandit": "bandit", "detect-secrets": "detect-secrets",
    "Pylint": "pylint", "mypy": "mypy", "Semgrep": "semgrep",
    "Checkov": "checkov", "Vulture": "vulture", "pip-audit": "pip-audit",
}


def tally(keys):
    """(files, proposed, r14, r3, structural, surface, upheld, passes)."""
    t: Counter = Counter()
    for s in res["subjects"]:
        if s.get("candidates") is None or s["key"] not in keys:
            continue
        dom = Counter(c.get("domain", "R14") for c in s["candidates"])
        stratum = s.get("stratum", "A")
        surf = [c for c in s["candidates"]
                if c.get("domain") == "R14"
                and (stratum == "B" or SURFACE.search(c["module"]))]
        t["files"] += s["scan"]["parsed"]
        t["prop"] += len(s["candidates"])
        t["r14"] += dom.get("R14", 0)
        t["r3"] += dom.get("R3", 0)
        t["struct"] += dom.get("STRUCTURAL", 0)
        t["surf"] += len(surf)
        for c in surf:
            v = verdict_of.get((s["key"], c["module"], c["line"]))
            if v == "UPHELD":
                t["upheld"] += 1
            elif v == "PASS":
                t["passes"] += 1
    return (t["files"], t["prop"], t["r14"], t["r3"], t["struct"], t["surf"],
            t["upheld"], t["passes"])


# The paper's table is the ADJUDICATED corpus. Later subjects were fetched only
# for the pre-registered audit-rate test and are scanned but not adjudicated, so
# summing every scanned subject here would compare the table against a wider
# population than it reports. The boundary is read from the verdict file rather
# than hardcoded, so adjudicating a new subject updates both at once.
scanned = {s["key"] for s in res["subjects"] if s.get("candidates") is not None}
adjudicated = set(adj.get("_adjudicated_subjects") or
                  {e["subject"] for e in adj["entries"]}) & scanned
expected = {name: tally({key}) for name, key in ROW_TO_KEY.items()
            if key in adjudicated}
expected[f"total ({len(adjudicated)} scanned)"] = tally(adjudicated)

tex = TEX.read_text(encoding="utf-8")
block = tex.split(r"\label{tab:external}")[1].split(r"\end{tabular}")[0]


def _num(cell: str) -> int:
    """Numeric cells carry LaTeX bolding and the digit separator, both of which
    use braces, so brace matching is the wrong tool. The cell is a number."""
    digits = "".join(ch for ch in cell if ch.isdigit())
    if not digits:
        raise ValueError("no digits in cell %r" % cell)
    return int(digits)


def _label(cell: str) -> str:
    for tok in ("\\textbf{", "\\emph{", "\\textit{", "{", "}"):
        cell = cell.replace(tok, "")
    return cell.strip()


bad, seen = [], set()
# Rows end at the LaTeX row separator, not at a newline: a wide row wraps.
for raw in block.split(r"\\"):
    line = " ".join(raw.split())
    # \hline and \heavyrule come from the house boxed-table form and would
    # otherwise prefix the next row's first cell, hiding the row label.
    for tok in (r"\midrule", r"\toprule", r"\bottomrule", r"\addlinespace",
                r"\heavyrule", r"\hline"):
        line = line.replace(tok, " ")
    line = " ".join(line.split())
    if "&" not in line or "multicolumn" in line or "begin{tabular}" in line:
        continue
    cells = [c.strip() for c in line.split("&")]
    label = _label(cells[0])
    if label in ("", "Subject"):
        continue
    if label not in expected:
        bad.append(f"unrecognised row label {label!r}")
        continue
    seen.add(label)
    try:
        # cells[1] is the origin column, which is prose; numbers start at 2
        got = tuple(_num(c) for c in cells[2:10])
    except (ValueError, IndexError) as exc:
        bad.append(f"{label}: could not parse the row ({exc})")
        continue
    if got != expected[label]:
        bad.append(f"{label}: paper says {got}, artifact says {expected[label]}")

for label in expected:
    if label not in seen:
        bad.append(f"{label}: expected in the paper table and not found")

if bad:
    print("MISMATCH between paper 14 and the artifact:")
    for b in bad:
        print("  ", b)
    sys.exit(1)
print(f"paper 14 table matches the artifact on all {len(seen)} rows")
print("  columns checked: files, proposed, R14, R3, structural, surface, "
      "upheld, pass")
