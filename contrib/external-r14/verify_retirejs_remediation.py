"""Verify the retire.js remediation by RUNNING the released package.

Finding (2026-08-20, issue #615): `retire --insecure` sets
`rejectUnauthorized = false` for the advisory download and records nothing about
it, so a verified run and an unverified run produce the same report.

Remediation arrived in two commits:
  8c911d6  (v5.5.0, 2026-08-21) -- WHICH repository was used. Partial: it does
           not say whether the fetch was verified.
  72438a0  (v5.6.0, 2026-08-22) -- WHETHER certificate errors were ignored.

This script checks the second one the way this directory checks everything else:
against the artifact a user actually installs, not against the diff. Reading the
patch tells you what the author intended; running the package tells you what the
package does. The two are not the same claim, and only the second is evidence.

The control is the same command without the flag. A field that is always present
records nothing, so "present under --insecure" is only half a result -- the other
half is "absent without it", which is also the maintainer's chosen design
(emitted only when set, zero cost on the ordinary path).

    python verify_retirejs_remediation.py [path/to/retire]

Needs network: retire downloads its advisory repository on every run. Exit 0 if
every format behaves, 1 otherwise.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

JSON_FIELD = "ignoreRepositoryCertificateErrors"
CDX_PROPERTY = "retirejs:ignore-repository-certificate-errors"
CDX_JSON_FORMATS = ["cyclonedxJSON", "cyclonedxJSON1_6", "cyclonedxJSON1_7"]


def resolve(path):
    """npm's `.bin/retire` is a POSIX shell script on Windows; the runnable
    sibling is `retire.cmd`. Prefer it when it exists."""
    p = Path(path)
    if sys.platform == "win32" and p.suffix == "":
        cmd = p.with_suffix(".cmd")
        if cmd.exists():
            return str(cmd)
    return str(p)


def find_retire(argv):
    if len(argv) > 1:
        return resolve(argv[1])
    local = Path(__file__).parent / "node_modules" / ".bin" / "retire"
    if local.exists() or local.with_suffix(".cmd").exists():
        return resolve(local)
    found = shutil.which("retire")
    if found:
        return found
    sys.exit("no `retire` found. Install one: npm install retire@5.6.0")


def run(binary, target, fmt, insecure):
    """Return combined stdout+stderr.

    The CycloneDX reporters write to stderr when vulnerabilities are found and
    to stdout when none are, so a run that captures only one stream reads empty
    exactly half the time. Discovered by doing it wrong first.
    """
    cmd = [binary, "--path", str(target), "--outputformat", fmt]
    if insecure:
        cmd.insert(1, "--insecure")
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.stdout + p.stderr


def supports(binary, target, fmt):
    """Does the installed retire know this output format?

    Older releases do not carry every CycloneDX version: 5.6.0, the release
    that completed this fix, has no `cyclonedxJSON1_7`. Probing and reporting
    the gap is the point. A format that cannot run must be visible as skipped,
    because a check that silently does not run looks exactly like a check that
    ran and found nothing, which is the failure this exercise is about.
    """
    return "Invalid outputformat" not in run(binary, target, fmt, False)


def parse_json(raw):
    start = raw.index("{")
    return json.loads(raw[start:])


def properties(doc):
    return doc.get("metadata", {}).get("properties", []) or []


def main():
    binary = find_retire(sys.argv)
    version = subprocess.run([binary, "--version"], capture_output=True,
                             text=True).stdout.strip()

    target = Path(__file__).parent / "fixtures" / "retirejs_scan_target"
    target.mkdir(parents=True, exist_ok=True)
    (target / "jquery.js").write_text("/*! jQuery v1.6.1 */\n", encoding="utf-8")

    print(f"retire {version}, scanning {target}\n")
    rows, failures = [], []

    for insecure in (False, True):
        doc = parse_json(run(binary, target, "json", insecure))
        present = JSON_FIELD in doc
        value = doc.get(JSON_FIELD)
        ok = (present and value is True) if insecure else not present
        rows.append(("json", insecure, "true" if present else "absent", ok))
        if not ok:
            failures.append(f"json, insecure={insecure}: present={present} value={value!r}")

    skipped = [f for f in CDX_JSON_FORMATS if not supports(binary, target, f)]
    usable = [f for f in CDX_JSON_FORMATS if f not in skipped]

    for fmt in usable:
        for insecure in (False, True):
            props = properties(parse_json(run(binary, target, fmt, insecure)))
            hit = [p["value"] for p in props if p["name"] == CDX_PROPERTY]
            ok = (hit == ["true"]) if insecure else not hit
            rows.append((fmt, insecure, hit[0] if hit else "absent", ok))
            if not ok:
                failures.append(f"{fmt}, insecure={insecure}: {hit}")

    for insecure in (False, True):
        raw = run(binary, target, "cyclonedx", insecure)
        found = f'name="{CDX_PROPERTY}">true' in raw
        ok = found if insecure else not found
        rows.append(("cyclonedx (XML)", insecure, "true" if found else "absent", ok))
        if not ok:
            failures.append(f"cyclonedx XML, insecure={insecure}: found={found}")

    width = max(len(r[0]) for r in rows)
    for fmt, insecure, value, ok in rows:
        flag = "--insecure" if insecure else "control  "
        print(f"  {'ok ' if ok else 'FAIL'}  {fmt:<{width}}  {flag}  ->  {value}")

    for fmt in skipped:
        print(f"  SKIP  {fmt:<{width}}  not supported by retire {version}")

    if failures:
        print("\nFAILED:")
        for f in failures:
            print("  " + f)
        return 1

    print(f"\nall {len(rows)} runs behave: the relaxation is recorded when taken "
          f"and the record is absent when it is not.")
    if skipped:
        print(f"{len(skipped)} format(s) NOT exercised on this version: "
              f"{', '.join(skipped)}. Install retire@5.7.0 for full coverage.")
    print("The relaxation itself is unchanged, and was never what the report "
          "asked to change.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
