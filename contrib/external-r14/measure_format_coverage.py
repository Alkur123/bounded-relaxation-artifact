"""How far does the retire.js `--insecure` record reach across report formats?

`verify_retirejs_remediation.py` asks whether the v5.6.0 remediation works. It
does: five formats carry the field under the flag and omit it without. This file
asks the different and later question of how many formats there are, and answers
it with the test the finding is actually named after rather than by looking for a
field name.

WHY A FIELD-NAME SEARCH IS THE WRONG TEST. The first version of this probe
grepped each report for `ignoreRepositoryCertificateErrors`. A human-readable
format would never contain that string, so `text` failed a test it was never
eligible to pass. The correct instrument is a byte comparison of two runs,
normalising only what legitimately changes between any two invocations
(timestamps, uuids, elapsed times). If the two are identical, a reader holding
one of them cannot tell which was produced, and that is the whole claim.

RESULT AT retire 5.7.0 (2026-08-26), reproduced by running this file:

    carries the record  json, cyclonedx, cyclonedxJSON,
                        cyclonedxJSON1_6, cyclonedxJSON1_7      5 formats
    IDENTICAL           text (the DEFAULT), jsonsimple,
                        depcheck                                 3 formats

`text` is the strongest of the three, for three reasons. It is what a user gets
with no `--outputformat` at all. It is the one a human reads. And it already
prints a line naming the advisory repository at the moment of the fetch --

    Downloading https://raw.githubusercontent.com/.../jsrepository-v5.json ...

-- which is byte-identical whether or not certificate verification was disabled
for that exact request. There is an obvious place to put it and the line is
already there.

`jsonsimple` and `depcheck` are weaker asks and are reported as such: both may
have schemas that deliberately cannot carry extra metadata, `depcheck` in
particular targeting an external tool's format.

    python measure_format_coverage.py [path/to/retire]

Needs network. Exits 0 always: this measures, it does not judge.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

FORMATS = [
    "text", "json", "jsonsimple", "depcheck",
    "cyclonedx", "cyclonedxJSON", "cyclonedxJSON1_6", "cyclonedxJSON1_7",
]

# Everything that legitimately differs between any two runs of anything.
VOLATILE = [
    (re.compile(r"urn:uuid:[0-9a-f-]+"), "UUID"),
    (re.compile(r"\d{4}-\d{2}-\d{2}T[\d:.]+Z?"), "TIMESTAMP"),
    (re.compile(r'"(start|end|time|timestamp)"\s*:\s*"[^"]*"'), "TIME"),
]


def resolve(path):
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
    sys.exit("no `retire` found. Install one: npm install")


def run(binary, target, fmt, insecure):
    cmd = [binary, "--path", str(target), "--outputformat", fmt]
    if insecure:
        cmd.insert(1, "--insecure")
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.stdout + p.stderr


def canon(s):
    for pat, rep in VOLATILE:
        s = pat.sub(rep, s)
    return s


def main():
    binary = find_retire(sys.argv)
    version = subprocess.run([binary, "--version"], capture_output=True,
                             text=True).stdout.strip()

    target = Path(__file__).parent / "fixtures" / "retirejs_scan_target"
    target.mkdir(parents=True, exist_ok=True)
    (target / "jquery.js").write_text("/*! jQuery v1.6.1 */\n", encoding="utf-8")

    print(f"retire {version}: does --insecure change the report?\n")
    width = max(len(f) for f in FORMATS)
    carries, identical, unsupported = [], [], []

    for fmt in FORMATS:
        flagged = run(binary, target, fmt, True)
        if "Invalid outputformat" in flagged:
            unsupported.append(fmt)
            print(f"  {fmt:<{width}}  not supported by this version")
            continue
        control = run(binary, target, fmt, False)
        if canon(flagged) == canon(control):
            identical.append(fmt)
            print(f"  {fmt:<{width}}  IDENTICAL   two runs, one output")
        else:
            carries.append(fmt)
            print(f"  {fmt:<{width}}  differs     the relaxation is recorded")

    print()
    print(f"  carries the record : {len(carries)}  ({', '.join(carries)})")
    print(f"  identical          : {len(identical)}  ({', '.join(identical)})")
    if unsupported:
        print(f"  not in this version: {len(unsupported)}  ({', '.join(unsupported)})")

    if "text" in identical:
        print()
        print("  NOTE: `text` is the DEFAULT format. A user who passes no")
        print("  --outputformat gets a report that is byte-identical whether or")
        print("  not certificate verification was disabled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
