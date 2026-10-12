# retire.js follow-up: the record does not reach the default output format

**Measured 2026-08-26 against retire 5.7.0** with
`contrib/two-runs-one-output/measure_format_coverage.py`.
**Status: DRAFT, not sent.**

---

## What we found

The `72438a0` / v5.6.0 remediation works, and `verify_retirejs_remediation.py`
confirms it across five formats. Asking the wider question — *how many formats
are there* — gives a different answer:

| format | `--insecure` vs control | |
|---|---|---|
| `json` | differs | records it |
| `cyclonedx` (XML) | differs | records it |
| `cyclonedxJSON` | differs | records it |
| `cyclonedxJSON1_6` | differs | records it |
| `cyclonedxJSON1_7` | differs | records it |
| **`text`** | **IDENTICAL** | **the DEFAULT format** |
| `jsonsimple` | IDENTICAL | |
| `depcheck` | IDENTICAL | |

**`text` is the strongest of the three and the only one worth pressing.** It is
what a user gets with no `--outputformat` at all, it is the one a human reads,
and it already prints a line naming the advisory repository **at the moment of
the fetch**:

```
Downloading https://raw.githubusercontent.com/RetireJS/retire.js/master/repository/jsrepository-v5.json ...
```

That line is byte-identical whether or not certificate verification was disabled
for that exact request. Verified on a **cache miss**, so the download genuinely
happened in both runs — a cached run would not have tested it.

`jsonsimple` and `depcheck` are weaker asks and should be presented as such: both
plausibly have schemas that deliberately carry no extra metadata, and `depcheck`
targets an external tool's format that is not the maintainer's to extend.

---

## ⚠ The wrong test was run first, and it is worth knowing why

The first probe searched each report for the literal string
`ignoreRepositoryCertificateErrors`. A human-readable format would never contain
that string, so `text` failed a test it was never eligible to pass, and the
result would have been a false positive presented to a maintainer who has
already been generous twice.

The correct instrument is the one the finding is named after: run both ways,
normalise only what legitimately varies between any two invocations, and compare.
`measure_format_coverage.py` does that.

---

## How to word it, based on what worked twice

The first report to this maintainer was rejected, correctly, as describing an
intentional feature. What got code shipped was **two runs, one output**. The same
framing applies here and should be used again, because it is also simply the
accurate description:

> Following up on #615, and this may well be deliberate. The JSON and CycloneDX
> reporters now carry the flag, which is exactly what was asked for. The default
> `text` output does not: running with and without `--insecure` produces
> byte-identical output, including on a cache miss where the download actually
> happens. The `Downloading <url> ...` line is the same either way.
>
> Since `text` is what you get with no `--outputformat`, and there is already a
> line about the repository at the point of the fetch, it may be the cheapest
> place of all to say it. `jsonsimple` and `depcheck` are also identical, but I
> assume those schemas are meant to stay minimal, so I would not ask for those.
>
> Script that measures it, if useful: <link>

**What NOT to do:** do not call this a security issue, do not imply the previous
fix was inadequate, and do not ask for all three. He fixed it twice already; the
tone that earned that should not change now that we are asking a third time.

---

## What it changes for us

**The paper's retire.js result becomes more precise, not weaker.** Currently it
reads as fully remediated. It should read: remediated in the five structured
report formats, with the default human-readable format still identical across
the two runs, reported as a follow-up. That is a better finding — it shows the
obligation being met *partially*, which is a more realistic picture of how this
defect class actually gets closed than a binary fixed/unfixed.

**It also earns the harness its keep.** This was invisible until the verifier was
run somewhere new, on a different retire version. The coverage question was not
asked by design; it was forced by an unrelated crash on 5.6.0.

⚠ **Do not publish the LessWrong post's retire.js paragraph as "fixed, full
stop"** if this goes out first, or the post will be describing a state that the
follow-up has already complicated. Either send this first and describe both
rounds, or post first and add the follow-up afterwards. Sending first is
better: a third accepted round is a stronger story than a clean one.
