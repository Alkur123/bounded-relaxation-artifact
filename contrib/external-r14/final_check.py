"""One command that answers "is paper 14 shippable", and says why not if it isn't.

Every other checker in this directory answers one question. This runs all of
them plus the structural checks nothing else covers, and prints a checklist a
person can read in ten seconds. It exits non-zero if any line is a FAIL.

    python final_check.py            # the checklist
    python final_check.py --quiet    # only failures

What it does NOT do is judge the writing, the argument or the honesty of a
claim. Those need a reader. It checks that the paper agrees with its artifacts,
with itself, and with the two copies of it we ship.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
TEX = pathlib.Path(os.environ["R14_PAPER_TEX"]) if os.environ.get("R14_PAPER_TEX") else REPO / "backend" / "paper" / "bounded_relaxation.tex"
BUNDLE = REPO / "backend" / "paper" / "bounded_relaxation_extracted" / "bounded_relaxation.tex"

results: list[tuple[str, bool, str]] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    results.append((label, ok, detail))


def run(label: str, argv: list[str], must_contain: str | None = None,
        cwd: pathlib.Path | None = None) -> None:
    try:
        p = subprocess.run(argv, cwd=str(cwd or HERE), capture_output=True,
                           text=True,
                           timeout=900, encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as exc:
        check(label, False, str(exc)[:90])
        return
    ok = p.returncode == 0
    out = (p.stdout or "") + (p.stderr or "")
    if ok and must_contain and must_contain not in out:
        ok = False
    last = [ln for ln in out.strip().splitlines() if ln.strip()]
    check(label, ok, (last[0] if ok else (last[-1] if last else ""))[:96])



def _strip_tex(text: str) -> str:
    """Drop comments and escaped delimiters so the balance checks mean something."""
    out = []
    for line in text.split("\n"):
        cut, esc = len(line), False
        for i, ch in enumerate(line):
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
            elif ch == "%":
                cut = i
                break
        out.append(line[:cut])
    body = "\n".join(out)
    for token in ("\\{", "\\}", "\\$", "\\%", "\\&", "\\_", "\\#"):
        body = body.replace(token, "")
    return body


def latex_structure(text: str) -> list:
    """The compile-breakers findable without a compiler."""
    body = _strip_tex(text)
    problems = []

    stack = []
    for kind, name in re.findall(r"\\(begin|end)\{([^}]+)\}", body):
        if kind == "begin":
            stack.append(name)
        elif not stack:
            problems.append(f"\\end{{{name}}} with nothing open")
        elif stack[-1] != name:
            problems.append(f"\\end{{{name}}} closes \\begin{{{stack[-1]}}}")
            stack.pop()
        else:
            stack.pop()
    if stack:
        problems.append(f"never closed: {', '.join(stack[:4])}")

    depth = body.count("{") - body.count("}")
    if depth:
        problems.append(f"brace balance off by {depth:+d}")

    if body.count("$") % 2:
        problems.append(f"odd number of $ ({body.count('$')})")
    return problems


def main() -> int:
    tex = TEX.read_text(encoding="utf-8")

    # ── the released checkers ───────────────────────────────────────────────
    run("scan and verdicts agree (summarize)", [sys.executable, "summarize.py"])
    run("per-subject table matches the artifact",
        [sys.executable, "verify_paper_table.py"])
    run("every scalar claim matches its artifact",
        [sys.executable, "verify_paper_numbers.py"])
    run("the paper agrees with itself",
        [sys.executable, "verify_paper_consistency.py"])
    run("every consistency rule can still fail",
        [sys.executable, "verify_paper_consistency.py", "--selftest"])
    run("TypeScript verdicts re-derive from the scan",
        [sys.executable, "adjudicate_ts.py"])
    run("TypeScript scan and verdicts agree",
        [sys.executable, "summarize_ts.py"])
    run("bounds measurement reproduces",
        [sys.executable, "measure_bounds.py"])
    run("executed proof, Python", [sys.executable, "prove_reachable.py"])
    run("executed proof, TypeScript", ["node", "prove_reachable_ts.mjs"])
    run("derived claims are current",
        [sys.executable, "emit_paper_claims.py", "--check"])

    # The upstream remediations, executed against the RELEASED artifacts. These
    # need the network, and they FAIL rather than skip when they cannot reach
    # it. A check that quietly reports OK because it could not run is the exact
    # fail-open shape R3 exists to catch, and it would be indefensible to ship
    # it inside the gate for the paper that says so.
    run("executed proof, Langfuse remediation",
        ["node", "prove_langfuse_remediation.mjs"])

    # THE CHECK THIS GATE WAS MISSING, AND IT MATTERED.
    # Everything above lives in this directory. The repository-wide paper
    # checker lives in backend/paper and was never called here, so when paper
    # 14's external percentages stopped tracing on 2026-08-18 the paper failed
    # `verify_paper.py` for two full sessions while this file printed 19 of 19.
    # A green light from a different gate standing in for the one that could
    # not see the claim is the exact failure this paper is about.
    run("repo-wide paper checker (verify_paper.py)",
        [sys.executable, "verify_paper.py", "bounded_relaxation.tex"],
        must_contain="PASS", cwd=REPO / "backend" / "paper")

    # ── structure nothing else checks ───────────────────────────────────────
    labels = set(re.findall(r"\\label\{([^}]+)\}", tex))
    refs = set(re.findall(r"\\ref\{([^}]+)\}", tex))
    check("no undefined cross-reference", not (refs - labels),
          ", ".join(sorted(refs - labels))[:90] or "all resolve")

    # Keys come from a .bib file OR from an inline `thebibliography`, and this
    # paper uses the latter. The first version of this check looked only at
    # .bib files and reported a missing entry for a citation that resolves
    # perfectly well -- a checker crying wolf on correct work, which is the
    # failure mode this project keeps finding in other people's tools and has
    # no business shipping in its own. Recorded rather than quietly corrected.
    bib_keys = set(re.findall(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}", tex))
    for bib in (REPO / "backend" / "paper").glob("*.bib"):
        bib_keys |= set(re.findall(r"@\w+\{([^,]+),", bib.read_text(
            encoding="utf-8", errors="replace")))
    cited = set()
    for group in re.findall(r"\\cite[tp]?\{([^}]+)\}", tex):
        cited |= {k.strip() for k in group.split(",")}
    check("every citation has a bib entry", not (cited - bib_keys),
          ", ".join(sorted(cited - bib_keys))[:90] or f"{len(cited)} cited")

    tables = re.findall(r"\\begin\{table\}", tex)
    tab_labels = [x for x in labels if x.startswith("tab:")]
    check("every table is labelled", len(tables) == len(tab_labels),
          f"{len(tables)} tables, {len(tab_labels)} labels")

    check("the shipped bundle is identical to the source",
          BUNDLE.read_text(encoding="utf-8").replace("\r\n", "\n")
          == tex.replace("\r\n", "\n"),
          "byte-identical modulo line endings")

    # ── retired values that must not come back ──────────────────────────────
    # Each was a real number in a previous corpus and is now wrong everywhere.
    retired = {
        "24.1\\%": "site precision from the 22-subject corpus",
        "10.3\\%": "violation precision from the 22-subject corpus",
        "4{,}248": "file count from the 22-subject corpus",
        "$292$": "proposal count from the 22-subject corpus",
        "whether anyone asked": "the generalisation the pre-registered test withdrew",
    }
    back = [f"{v} ({k})" for k, v in retired.items() if k in tex]
    check("no retired value has come back", not back, "; ".join(back)[:90] or "none")

    # ── the artifacts the paper points at ───────────────────────────────────
    needed = ["prove_langfuse_remediation.mjs",
              "verify_langfuse_remediation.py",
              "external_r14_results.json", "adjudication.json",
              "external_r14_ts_results.json", "adjudication_ts.json",
              "r3_handoff.json", "audit_rate.json", "reachability.json",
              "bounds.json", "ADJUDICATION.md",
              "PREREGISTRATION_audit_rate.md",
              "PREREGISTRATION_cross_language.md",
              "PREREGISTRATION_cross_language_ext.md"]
    missing = [n for n in needed if not (HERE / n).exists()]
    check("every released artifact is present", not missing,
          ", ".join(missing)[:90] or f"{len(needed)} files")

    # ── the archive a reader actually receives ──────────────────────────────
    # The zip is a BUILD OUTPUT and `.gitignore` excludes `**/*.zip`, so it is
    # absent on a fresh clone and on CI. Its absence therefore cannot fail the
    # build. What gates everywhere is the tracked `_extracted/` mirror compared
    # above; this check adds the pre-upload gate on the machine that actually
    # produces the archive, which is where the drift happened -- the bundle was
    # two generations behind its source and nothing noticed.
    zip_path = REPO / "backend" / "paper" / "bounded_relaxation_overleaf.zip"
    if not zip_path.exists():
        check("the Overleaf bundle carries the current source", True,
              "NOT BUILT HERE (gitignored build output) -- run "
              "`python make_bundle.py bounded_relaxation` before uploading")
    else:
        with zipfile.ZipFile(zip_path) as zf:
            names = set(zf.namelist())
            same = (zf.read("bounded_relaxation.tex")
                    == TEX.read_bytes()) if "bounded_relaxation.tex" in names else False
            needed = {"bounded_relaxation.tex", "aegis_preprint.sty",
                      "README_COMPILE.txt"}
            complete = needed <= names
        check("the Overleaf bundle carries the current source", same and complete,
              f"{len(names)} entries, tex "
              f"{'identical' if same else 'DIFFERS'} to the repository copy")

    # ── compilability, as far as it can be judged without a compiler ────────
    structural = latex_structure(TEX.read_text(encoding="utf-8"))
    check("no structural error that would stop a LaTeX build", not structural,
          "; ".join(structural)[:88] or
          "environments, braces and math delimiters balance "
          "(NOT a compile: no TeX toolchain here)")

    # ── the disclosure state, which is a fact about the work, not a check ───
    findings = json.loads((HERE / "adjudication.json").read_text(encoding="utf-8"))
    ts_findings = json.loads((HERE / "adjudication_ts.json").read_text(encoding="utf-8"))
    upheld = [e for a in (findings, ts_findings) for e in a["entries"]
              if e["verdict"] == "UPHELD"]
    class_a = [e for e in upheld if e["class"] == "A"]

    # Derived from the tracking table, never hardcoded. This line asserted
    # "NOTHING HAS BEEN DISCLOSED" as a literal, so on 2026-08-20 it went on
    # saying so after all four had been sent. A gate that states a fact it does
    # not read is the stale-record failure this whole directory exists to catch.
    lines = (HERE / "DISCLOSURE_DRAFTS.md").read_text(encoding="utf-8").splitlines()
    head = next((i for i, ln in enumerate(lines)
                 if ln.replace(" ", "").startswith("|subject|sent|")), None)
    disclosed = answered = 0
    if head is not None:
        for ln in lines[head + 2:]:
            if not ln.startswith("|"):
                break
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if len(cells) < 3 or set(cells[0]) <= set("-: "):
                continue
            if cells[1] and cells[1] != "—":
                disclosed += 1
                if cells[2] not in ("", "—", "awaiting"):
                    answered += 1
    if head is None:
        state = "TRACKING TABLE NOT FOUND, disclosure state unknown"
    elif disclosed == 0:
        state = "NOTHING HAS BEEN DISCLOSED, founder decision"
    elif answered == 0:
        state = f"{disclosed} disclosed, none answered yet"
    else:
        state = f"{disclosed} disclosed, {answered} answered"
    check("class A findings, which the rubric says to disclose first",
          True, f"{len(class_a)} of {len(upheld)} upheld are class A -- {state}")

    quiet = "--quiet" in sys.argv
    width = max(len(label) for label, _ok, _d in results)
    failed = 0
    print()
    for label, ok, detail in results:
        if not ok:
            failed += 1
        if quiet and ok:
            continue
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {label:{width}s}  {detail}")
    print()
    if failed:
        print(f"{failed} of {len(results)} checks FAILED")
        return 1
    print(f"all {len(results)} checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
