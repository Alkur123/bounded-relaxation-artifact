# Maintainer disclosure — drafts, NOT SENT

**Status: ALL FOUR SENT 2026-08-20.** See the tracking table at the foot for
per-subject dates and responses. The paragraph this replaced said nothing had
been sent, which was true from the day the drafts were written until that
morning.

**The compelled one is discharged.** `ADJUDICATION.md` requires a Class A
relaxation reaching an enforcement decision to be reported to its maintainers
before it appears in any paper; the NeMo Guardrails omit-mode finding is the one
that qualifies, and it went to NVIDIA PSIRT. Paper 14 is no longer gated on
disclosure. **What is now owed is the other half of the same rule: report what
came back, including a maintainer saying we are wrong, at the same prominence as
the finding.**

**First response in, 2026-08-21: retire.js — and as of 2026-08-24 it is fully
remediated in released code.** Acknowledged and code shipped the same day; that
first fix was **partial** (which advisory repository was used, not whether the
fetch was verified), we said so on the issue, and after one further exchange the
maintainer shipped the remaining field in `72438a0`, released as **5.6.0**.
Verified by running the published package, not by reading the diff. Full record
under "What came back" at the foot. **Three subjects remain "awaiting"**, and one
remediation out of four contacted is not a base rate.

> ⚠ **AMENDMENT 2026-08-26 — the two counts in the paragraph above were true on
> 24 August and are wrong now.** Langfuse answered on **2026-08-25** and shipped
> the fix in v4.18.0 the same day, so it is **two** subjects awaiting, not three,
> and **two** remediations out of four contacted, not one. The paragraph is left
> as written because it is dated and this file records what was believed when,
> rather than being rewritten to look as though it was always right. The
> **table below is authoritative** and was correct throughout: `final_check.py`
> derives the disclosure state from the table, never from this prose, which is
> why the gate did not catch the drift and why it is not a gate defect. The
> claim in the paper (`sec:limits`) is likewise correct at "two read
> `awaiting`" and "Two remediations are not a base rate".

## AMENDMENT 2026-08-20 — the channel was wrong for two of the four

Recorded as a dated amendment rather than folded in silently, per this
directory's convention.

Every message below is formatted as a GitHub issue, each with a **Title:** line.
Checked against each maintainer's own published policy on 2026-08-20, that is
against the stated wishes of two subjects, and one of the two is the finding our
own rubric compels.

| subject | published policy | correct route |
|---|---|---|
| **NeMo Guardrails** | `SECURITY.md`: "Please do not report security vulnerabilities through GitHub." | **`psirt@nvidia.com`**, or the NVIDIA vulnerability submission form |
| **LLM Guard** | security policy: "Do NOT open an issue on the GitHub repository, as doing so makes it public knowledge." | **`security@protectai.com`** |
| Langfuse | `security@langfuse.com` published; issues not prohibited | either; email is the safer default |
| retire.js | no `SECURITY.md` (404) | GitHub issue, as drafted |

**Why it matters beyond politeness.** The NeMo finding is a detector reporting
`allow` after its rules matched and the match was logged, inside a product whose
job is to block. Whether or not we claim exploitability — and House rule 1
correctly claims none — that is security-relevant on its face, and the vendor has
said in writing where such things go. Filing it publicly, on the one finding
compelled before publication, would be the first thing a reviewer of paper 14
noticed.

**The bodies below need no change.** Only the channel, and the **Title:** framing
becomes a subject line. Send-ready versions with the corrected `To` lines are at
`docs/OUTREACH_2026-08-20_SEND_READY.md`.

## Why this is owed, and by when

`ADJUDICATION.md` fixes the rule in advance:

> A finding is reported to its maintainers before it appears in any paper if it
> is a Class A relaxation that reaches an enforcement decision, and the paper
> says whether that was done and what came back.

Against the five upheld findings:

| finding | subject | class | reaches enforcement | compelled before publication? |
|---|---|---|---|---|
| omit-mode verdict from repair | NeMo Guardrails | **A** | **yes** | **YES — this one is compelled** |
| short-input exemption unaudited | NeMo Guardrails | A | no | no, but same maintainer, send together |
| ignore-list waiver unlogged | LLM Guard | B | no | no |
| agent auto-approval unrecorded | Langfuse | B | no | no |
| `--insecure` unrecorded | retire.js | B | no | no |

So exactly one is compelled by our own rule. The other four are courtesies that
cost us nothing and are, in two cases, security tools where the courtesy is
obviously right.

## House rules for all four messages

1. **No exploitability claim.** Every proof constructs its input. We have not
   shown that ordinary traffic reaches any of these paths in any deployment,
   and saying otherwise would be false.
2. **Name the commit.** These are moving trees; a finding without a SHA is not
   checkable.
3. **Lead with what we ran, not with what we conclude.**
4. **Offer the artifact.** Every claim has a released script behind it.
5. **Accept correction publicly.** If a maintainer shows a site is fine, that
   goes in the paper as a withdrawal, in the same place as the finding.
6. **No branding, no paper link in the first message.** A maintainer being told
   about their code should not have to read our marketing to get to the line
   number.

---

## 1. NVIDIA / NeMo-Guardrails — the compelled one

**Repo:** https://github.com/NVIDIA/NeMo-Guardrails
**Commit:** `6e53c3060a159ac88f4fa0137f4d3359d6e6815f`

> **Title:** Injection detection in `omit` mode can return `allow` after rules
> matched, when a decoding error is skipped
>
> Hello — we were running a static check over open-source guardrail code and it
> flagged something in `nemoguardrails/library/injection_detection/actions.py`
> that we think is worth a look. We may be wrong about the intent, in which case
> please say so and we will record the correction.
>
> At `actions.py:240`, in `omit` mode, the flow is: the YARA rules have already
> matched and the match has been logged. Each matched instance is then decoded
> inside a `try`; a decoding error is caught, logged, and the loop `continue`s
> **without removing that instance**. The verdict is then taken from whether the
> text changed:
>
> ```python
> if modified_text != original_text:
>     is_injection = True
> else:
>     is_injection = False
> ```
>
> So if every matched instance fails to decode, nothing is removed, the text is
> unchanged, and the function reports no injection — even though the detection
> succeeded and was logged. The verdict is being taken from whether the
> *repair* worked rather than from the strength of the *detection*.
>
> The docstring states the conflation directly: "False if the text is safe (i.e.
> not modified)".
>
> **What we did not do:** we have not shown that a real input reaches this
> branch. Our check is static, and the proof we ran constructs the inputs. This
> is a report about a code path, not an exploit.
>
> Happy to send the reproduction script; it needs no API key and executes only
> your function against stubs.

**Second item for the same repo**, in the same issue or a separate one:
`library/jailbreak_detection/heuristics/checks.py:89` skips the perplexity check
for prompts under a length threshold. The threshold itself looks sound — the
attack class is not meaningful below that length — but nothing records that the
check was skipped, so a caller cannot distinguish an exempted prompt from a
tested one. A single log line or a field on the result would close it.

---

## 2. Protect AI / LLM Guard

**Repo:** https://github.com/protectai/llm-guard
**Commit:** `168c1034ffdb33837e7ae6fd6a16b80567c1be03`

> **Title:** Entities dropped by the ignore list are the only ones not logged
>
> At `llm_guard/input_scanners/anonymize_helpers/transformers_recognizer.py:308`,
> three branches can drop a detected entity. Two of them log; the one driven by
> the operator-supplied ignore list does not. The result is that a redaction
> which *did not happen because of configuration* is indistinguishable
> downstream from one that was never needed.
>
> Not a correctness bug — the ignore list is doing what it is asked. It is an
> observability gap, and the fix is one line in the branch that already exists.

---

## 3. Langfuse

**Repo:** https://github.com/langfuse/langfuse
**Commit:** `e68e201a66ac67eaeb2a6dd8f1d36295c092913f`

> **Title:** In-app agent tool auto-approval leaves no trace
>
> `packages/shared/src/in-app-agent/server/mcpPolicy.ts` —
> `withInAppAgentToolApproval` marks every tool `requireApproval: true` except
> those `isInAppAgentAutoApprovedToolName` accepts, by name prefix, by a local
> allowlist, or by the role-derived `policy.autoApproved` set.
>
> The policy itself looks deliberate and role-aware. What we noticed is that the
> module contains no logging call of any kind, so nothing records that a
> particular tool call skipped approval. In a product whose purpose is making
> agent behaviour legible, a reader of a trace cannot currently distinguish a
> tool a human approved from one the policy waved through.
>
> Not a security report — an operator configured this. An observability one.

---

## 4. RetireJS / retire.js

**Repo:** https://github.com/RetireJS/retire.js
**Commit:** `680dfa2e2a436c9b66ab758693629a3cb92196ac`

> **Title:** `--insecure` disables certificate verification with no record in
> the output
>
> `node/src/repo.ts`, in `loadJson`: under `options.insecure` the request is
> built with `rejectUnauthorized = false`, which disables TLS certificate
> verification for the advisory downloads the scan reasons from. The only other
> occurrences of `insecure` in the package are the CLI flag's declaration and
> its type, and the log line in that function says `Downloading <url> ...` and
> nothing about verification.
>
> The flag is a legitimate operator choice — self-signed internal mirrors are
> real. The gap is that a clean report produced under `--insecure` looks exactly
> like a clean report produced with verification on, and a reader of the output
> cannot tell which they have. A line in the summary, or a field in the JSON
> output, would close it.
>
> We ran your function against stubs to confirm the behaviour rather than
> inferring it; happy to send that script.

---

## After sending, whatever comes back

The paper commits to reporting the outcome, including a maintainer saying we
are wrong. Add a row to this file per response, then update
`sec:limits` and the findings write-ups. **A withdrawal goes in the same place
as the finding, at the same prominence.**

| subject | sent | response | outcome in the paper |
|---|---|---|---|
| NeMo Guardrails | 2026-08-20, `psirt@nvidia.com` | **2026-08-21 acknowledged by NVIDIA PSIRT, case 6648406**, "I will send you an update once I have a response from the development team"; no further message as of 2026-10-12 (found in the inbox on 2026-10-12, it had never been entered here). Re-checked 2026-10-12: the omit-mode site and its caller are byte-identical on `main` at `9a051dc` (2026-10-10), as is the short-input exemption | acknowledged, no substantive response; reported as such |
| LLM Guard | 2026-08-20, `security@protectai.com` | no response as of 2026-10-12 (receipt window expired 2026-08-25). Re-checked 2026-10-12: `main` is still `168c103` (2026-07-09), the commit we scanned | silence, reported as an outcome |
| Langfuse | 2026-08-20, `security@langfuse.com` | **2026-08-25 answered, confirmed, and REMEDIATED: PR #16372 merged 09:22Z, released in v4.18.0 at 09:41Z the same day; verified at the tag with a control** | reported in full, including the correction to our wording; see "What came back" below |
| retire.js | 2026-08-20, public GitHub issue | **2026-08-21 acknowledged, `8c911d6` (v5.5.0) partial; 2026-08-22 `72438a0` (v5.6.0) closes the residual; confirmed by the maintainer 2026-08-24** | reported in full, including the partial stage; see "What came back" below |

**Chase dates.** Protect AI's policy commits to confirming receipt within three
business days, so an empty response column there after **2026-08-25** is a fact
worth recording rather than a reason to nudge. NVIDIA PSIRT normally returns a
case number; **put it in the response column when it arrives**, because
"reported to NVIDIA PSIRT, case NNNN, 2026-08-20" is materially stronger in the
paper than "reported to maintainers". No subject here gets a follow-up: these
were contributions, not requests.

**Silence is a reportable outcome.** If every column above still reads "awaiting"
at submission, the paper says exactly that. It does not say "disclosed" and stop.

**2026-08-25 — Protect AI's receipt window expired with no response.** Their
policy commits to confirming receipt within three business days of the
2026-08-20 report; the third expired today and nothing has arrived. Recorded as
a fact, **no follow-up sent**, per the rule above: these were contributions, not
requests. ⚠ **The response cell stays the literal `awaiting` on purpose** —
`final_check.py` reads any other text in that column as *answered*, so writing
the expiry into the cell would make the gate report a reply that does not exist.
The expiry belongs here, in prose, not in the table.

**What this obliges in the paper.** Five days after four disclosures, the record
is: one remediated in released code, three silent, and one of the three silent is
the class A finding the rubric compelled us to report before publishing. That is
the sentence paper 14 owes — not "all four were disclosed".

**2026-08-25 — Langfuse answered, and the count changes.** The record is now:
**two remediated in released code, two silent** — and one of the two silent is
still the class A finding the rubric compelled.

⚠ **This paragraph first said "one confirmed with a fix planned but not shipped",
and that was WRONG when written.** It was written on 2026-08-26 from the
maintainer's email alone. The email says "We're addressing that in #16372", which
was true when he sent it at 07:49Z; the PR merged 93 minutes later and shipped 20
minutes after that. A public artifact existed and was not checked, so a person's
description of the future was recorded as the state of the world. The rung this
directory is about is *a record that does not reflect what happened*. Keeping the
error visible here is cheaper than the alternative. See
[[feedback-run-the-artifact-not-the-source]].

---

## What came back

### Langfuse — 2026-08-25, second response of the four

**Confirmed, accepted as first worded, and remediated in a released version the
same day.** Two artifacts, answering two different questions.
`verify_langfuse_remediation.py` asks whether the code is in the released tree:
16 checks over the whole chain from predicate to span, control at the preceding
release. `prove_langfuse_remediation.mjs` asks what that code **does**: it
downloads the shipped module at **both** releases, prints each digest,
transpiles them, stubs only what the finding is not about, and calls the real
exported functions — **19 checks, all holding**.

**The caveat that stood here for one day is closed.** The first version said
Langfuse is a deployed server rather than a CLI, so there was no equivalent to
installing and running the package as `verify_retirejs_remediation.py` does.
That was true of a whole-product run and **false of the claim**: the finding is
about two exported functions, and functions can be called. What running proves
that reading could not:

| proof | result |
|---|---|
| the waiver now emits a record naming the stage | `langfuse_tool_approval`, `source: conversation_grant`, bound to `toolCallId` |
| **CONTROL** at v4.17.0 | the emitter does not exist, **and the same tool is waived identically** — two runs, one output, executed |
| the three paths are separately attributable | `auto`, `human`, `conversation_grant` each produced by the path that earns it |
| **CONTROL** on that | a call nobody approved yields **no** source and **no** sidecar — the field is not always-present, so it carries information |
| **the relaxation is unchanged** | 8 branches, both releases, **8/8 decide identically** |

That last row is the one that changed status. "Only the record changed" was a
reading of the diff; it is now a comparison of two running versions.

Replied by **Lysander Kiesel**, an engineer working on the in-app agent.
Verbatim from the mail, not from a summary:

| claim | what the maintainer said |
|---|---|
| the framing | "I agree this is an observability gap, not a security issue." |
| what already exists | "a human approve-once is stored as a HITL decision, and 'always approve for this conversation' is stored as a session allowlist of which tools may skip HITL for the rest of that conversation." |
| the gap, restated by him | "What is missing is an explicit per-call record for those auto-approved calls, so a trace reader cannot always tell whether a given execution ran because a human approved it, because of that session grant, or because policy auto-allowed it (as you reported)." |
| the remediation | "We're addressing that in #16372: each executed tool call will record its approval source (`human`, `session_grant` etc.) in the event stream and on the TOOL span." |

The parenthetical **"(as you reported)"** attributes the third path to this
report specifically. It is the rung's obligation named by a maintainer in his
own words: a stage weakened a verdict, and the record did not say which stage.

**The timeline, from the GitHub API rather than from the mail.** All times UTC;
the mail timestamps are IST as Gmail rendered them, converted here.

| when | what |
|---|---|
| 20 Aug 14:44 | our report emailed to `security@langfuse.com` |
| 20 Aug 17:50:12 | first commit `c18be7bf689b`, *record tool approval source in the event stream* |
| 20 Aug 17:51:04 | PR **#16372** opened by `LysanderKie` |
| 25 Aug 07:49 | his reply to us: "We're addressing that in #16372" |
| 25 Aug 08:12:02 | `477a50001e1b`, *collapse tool-approval sources to three values* |
| 25 Aug 09:03:27 | `5fd8ef582e65`, *do not stamp human approval source on rejected tools* |
| 25 Aug 09:22:04 | **merged** to `main` as `c34022568c59a4fc31f669f5092cce4bc12201b5` |
| 25 Aug 09:41:55 | **released in v4.18.0**, 19m51s after the merge |

5 commits, 13 files, +427/-13.

⚠ **What we may and may not claim about cause.** The first commit lands
**3h06m** after our email, and the maintainer attributes one of the three paths
to us in writing. That is strong. It is not a claim on the whole PR: the branch
is `lf-125-record-in-app-agent-tool-approval-source-in-the-conversation`, an
internal tracker id whose creation date we cannot see, and his own mail says the
human and session paths were **already** tracked implicitly. The defensible
sentence is that the *policy-auto-allowed* path is attributed to this report by
the maintainer, not that the PR would not exist without us.

**What shipped, traced from the predicate we named to the span a reader opens.**
`isInAppAgentAutoApprovedToolName` — the exact predicate in the finding — no
longer returns a bare boolean. It delegates to a new exported
`getInAppAgentToolApprovalSource`, which returns **which** stage waived the gate;
`buildInAppAgentToolApprovalSidecar` turns that into a first-class
`langfuse_tool_approval` event carrying `{toolCallId, toolName, source}`;
`withInAppAgentToolApprovalSidecars` emits one beside every `TOOL_CALL_START`;
and `instrumentation.ts` copies it onto the TOOL span as
`toolCallApprovalSource`. In R14's own vocabulary the site now has an
`audit_field`, so **`check_audited` moves from VIOLATION to OK in released
code**.

**The shipped vocabulary is `auto | human | conversation_grant`**, not the
`session_grant` in his email — commit `477a50001e1b` renamed it at 08:12Z, after
the mail went out at 07:49Z. Quote the shipped names.

**The relaxation is unchanged, and that is the result, not a caveat.** The
prefix waiver, the local allowlist and the role-derived `policy.autoApproved`
set all survive, and the refactor is behaviour-preserving: the new boolean is
`source !== undefined && source !== "human"`, which reproduces the old truth
table on every branch. The deviation stayed available and became visible — the
same shape as retire.js, now in a second language and a second subject.

⚠ **It also corrected us, and the correction stands.** Our mail said there is
"no way to tell whether a particular tool call was approved or was ignored by
the policy". Too sharp. A human approve-once **is** recorded, as a HITL
decision; a conversation grant **is** recorded, as a session allowlist. The true
structure has **three** paths, and the reader had to infer from the *absence* of
a record, absence covering two of them. The certifier's claim — the weakening
stage kept no record of its own — and the zero-logging fact about `mcpPolicy.ts`
both stand. The binary phrasing around them does not, and is withdrawn in the
paper beside the finding.

A fourth message the same day was an automated Pylon satisfaction survey with no
content; it is not a response and is not counted as one.

---

### retire.js — 2026-08-21, first response of the four

**Answered same day, code shipped the same day, and the fix is partial.** All
three facts belong in the paper, in that order.

**The thread, verbatim from the notification mail rather than from a summary.**
Four messages from `eoftedal`, a maintainer, on 2026-08-21:

| time | comment |
|---|---|
| 14:00 | "What are you trying to say with this report? This is an intentional feature." |
| 14:02 | "Can you explain with an example?" |
| 14:18 | "After thinking about it, I think I understand what you mean. The console output already says where the repository is downloaded from … However this is not reflected in the JSON output and probably not in the cycloneDX output either. It could be a good signal for consumers of the report (if that is not the same as the person running the scan)." |
| 17:10 | Closed #615 as completed via `8c911d6` |

The 14:18 parenthetical is the threat model of this rung restated by a
maintainer who had not read it: **the reader of the report is not the person who
ran the scan.**

**What `8c911d6` actually changes**, read from the patch and from the two source
files at that commit, not from the commit title:

* `reporters/json.ts` gains `vulnerabilityRepositories: vulnerabilityRepositories(config.jsRepo)`.
* `reporters/cyclonedx*.ts` gain a `metadata.properties[]` entry
  `retirejs:vulnerability-repository` per repository, and a `source.url` on each
  vulnerability when exactly one repository is configured.
* `cli.ts:71` resolves the default `'central'` to the built-in
  `raw.githubusercontent.com` URL, so the new field is populated even when
  `--jsrepo` is not passed.

**What it does not change.** `node/src/repo.ts` is **not among the twelve files
touched.** At `8c911d6` it still reads `options.log.info('Downloading ' + url + ' ...')`
(`repo.ts:152`) and `if (options.insecure) { reqOptions.rejectUnauthorized = false; }`
(`repo.ts:160-161`). The consequence is direct: `retire --outputformat json` and
`retire --insecure --outputformat json`, against the same repository, still emit
the same output. **The provenance half of the finding is closed; the relaxation
record we reported is not.**

**The accurate sentence, and the one that must not be written.** Accurate:
*acknowledged, partially remediated in `8c911d6` (repository provenance now in
the machine-readable output), the reported relaxation record still absent at that
commit.* Not accurate, and not to appear anywhere: "the finding was fixed."
Partial credit is still real — an operator pointing at a self-signed internal
mirror now surfaces a non-central URL to the report's reader, which is a weak
provenance signal that did not exist before.

**A methodological result, recorded because it is one.** The finding **as
originally worded did not land** — the first response was that this is an
intentional feature, and it was, because the wording argued about a flag. It
landed on the reframing: *a verified run and an unverified run produce the same
report.* The obligation this rung checks is legible to a maintainer as **two
runs, one output**, and illegible as "an unaudited relaxation". That is a finding
about how to state a relaxation-audit result, obtained the only way it could be —
by stating one to somebody who did not want it.

**Follow-up posted** on the closed issue naming the residual gap, offering a PR
for the minimal form (a sibling field in `json.ts` and one further
`metadata.properties` entry), and offering the harness. Per house rule 5, if the
maintainer answers that the flag's absence from the report is intended, that
answer goes in the paper at the same prominence as the finding.

### retire.js — 2026-08-22/24, the residual gap closed

**Recorded as a dated addition rather than folded into the section above**, per
this directory's convention. The paragraph before this one was accurate when it
was written and is now the account of an intermediate state, which is why it
stays.

**What happened.** The maintainer's reply to the follow-up was not an acceptance
and not a refusal — it was a question, and the right one:

> Of insecure to make sense to flag in output, it would mean someone has a rogue
> DNS and also sets the insecure flag. It's not really a strong signal. We could
> potentially add it only if you set it to true and leave it absent if set to
> false, but I'm not sure I see the value. If you know it's set to true, what
> does that tell you?

The answer given, verbatim in substance: it tells a reader that the advisory data
the report's conclusions rest on arrived over a channel whose authenticity was
not verified — not that the data is wrong, but that the reader cannot distinguish
"the repository said this" from "whatever answered said this" without going out
of band. Worth nothing to the person who set the flag; worth something to an
auditor, an SBOM pipeline, or a security team reading a vendor's scan as
evidence, for whom "no known vulnerabilities" from a verified fetch and from an
unverified one are two different strength claims that looked identical. And it is
worth more aggregated than per report: across an organisation you can ask which
scans run with verification off, which is answerable from the JSON and not from a
console line that scrolled past months ago. The reply also said, in as many
words, that if he weighed it and still did not think it earned its place that was
a reasonable call and would be recorded as working as intended.

**He implemented it.** `72438a0`, 2026-08-22, "Flag if insecure repository
downloads was enabled in output (ref #615)", released to npm as **5.6.0** roughly
a minute after the commit. `cli.ts` passes `insecure` into the logger options;
`reporters/json.ts` gains `ignoreRepositoryCertificateErrors`; the three
CycloneDX reporters gain a `retirejs:ignore-repository-certificate-errors`
entry under `metadata.properties`. **Emitted only when the flag is set** — his
suggestion, not ours, and the better shape: zero cost on the ordinary path. The
field names are his; the ones we proposed were `insecureRepositoryFetch` and
`retirejs:insecure-repository-fetch`. He posted "Added to the output" on the
issue on 2026-08-24, which is how we learned of it.

**Verified by running the released package, not by reading the patch.**
`verify_retirejs_remediation.py` in this directory installs nothing and asserts
nothing about the diff: it runs `retire` across all five report formats twice,
once with `--insecure` and once without. Against **5.7.0** from the registry, all
ten runs behave — the record is present with value `true` under the flag and
**absent** in every control. The control is half the result: a field that is
always present records nothing.

| format | control | `--insecure` |
|---|---|---|
| `json` | absent | `true` |
| `cyclonedxJSON` | absent | `true` |
| `cyclonedxJSON1_6` | absent | `true` |
| `cyclonedxJSON1_7` | absent | `true` |
| `cyclonedx` (XML) | absent | `true` |

`cyclonedxJSON1_7` did not exist when the fix landed; 5.7.0 refactored 1.6 and
1.7 onto a shared `cyclonedx-json-builder.ts` that carries the property, so the
record survived a refactor it was not written for. Worth noting because a fix
that is correct at its own commit and lost two releases later is a common
outcome, and this is not one.

**What is accurate to say now, and what still must not be said.** Accurate: *the
finding was reported, rejected as first worded, accepted on the reframing,
partially remediated in `8c911d6` (v5.5.0) and fully remediated in `72438a0`
(v5.6.0), verified against the released package.* Still not accurate: that the
relaxation was removed. `repo.ts` is unchanged and still sets
`rejectUnauthorized = false` under the flag — which was never the ask. R14 asks
that a relaxation be recorded, not that it be forbidden. **This is the rung's
whole claim demonstrated end to end on somebody else's code: the deviation stayed
available to the operator who wants it and became visible to the reader who
needs it.**

**One remediation is not a base rate**, and the paper says so. Four subjects were
contacted; one acted. Three still read "awaiting", and if they still do at
submission, that is the report.

> ⚠ **AMENDMENT 2026-08-26 — superseded by the Langfuse response, and the
> conclusion is unchanged.** As of **2026-08-25** it is **two** acted and **two**
> awaiting: Langfuse shipped PR #16372 in v4.18.0 on the day it replied. The
> sentence above is kept at its own date. **Two remediations are still not a base
> rate**, and the substantive point survives the correction rather than being
> rescued by it — four subjects is too few either way, and the two that acted
> both did so because a maintainer chose to, not because the finding compelled
> anything. See "What came back — Langfuse" below for the full record, including
> the correction that Langfuse made to *our* wording.

### retire.js -- 2026-08-26, close-out posted, and the ask withdrawn before sending

**Comment 6 on issue 615, posted 2026-08-26T17:50:31Z by `Alkur123`.** Confirms
`72438a0` against the released package (retire 5.7.0, ten runs, five structured
formats with a control each) and closes our side of the exchange.

**A fourth ask was drafted and then withdrawn without being sent.**
`measure_format_coverage.py` found that `text`, `jsonsimple` and `depcheck` are
byte-identical with and without `--insecure`, `text` being the default format.
That looked like a coverage gap. It is not one.

Reading `eoftedal`'s own comments rather than our summary of them: **he addressed
the console output in his first reply**, on 2026-08-21, saying it already names
the repository and that the gap was the JSON and CycloneDX outputs because those
*"could be a good signal for consumers of the report (if that is not the same as
the person running the scan)"*. `text` **is** the console, and its reader is the
operator who typed the flag. He was also sceptical of the whole idea twice in
writing -- *"not really a strong signal"*, *"I'm not sure I see the value"*,
*"If you know it's set to true, what does that tell you?"* -- and shipped it
anyway.

**So the scope was deliberate and correct, not an oversight**, and asking a
fourth time would have spent standing earned by two accepted reports. The
observation appears once in the close-out, explicitly not as a request, with his
own criterion credited back to him and only the CI-log case noted as the one he
may not have weighed.

**This is the more valuable finding.** Not "he missed three formats" but: *a
maintainer drew a principled line -- record the relaxation in the artifact that
leaves the operator's hands, not in the operator's own console -- and the line
holds under measurement.* It belongs in the mechanism taxonomy as its own entry,
and it answers the objection the taxonomy most needs to answer, which is "so must
everything be logged". No: log it where the reader is not the decider.

**Status: retire.js is closed on our side.** No further contact planned. If he
replies proposing to add it to `text`, that is his idea and stays his idea.

### retire.js -- 2026-09-25 re-check against the GitHub API: two facts this file lacked

**1. The maintainer replied to our close-out, 2026-08-26T22:03:36Z** (`eoftedal`,
`MEMBER`), verbatim:

> My first reaction was to say «no» as this has been reported as a vulnerability
> earlier when it is in fact an intentional feature. However, you did have a
> different point, which is more in the direction of provenance than of a
> vulnerability.

This explains the first-day rejection in his own words (a prior report had
framed the flag as a vulnerability) and names our reframe *provenance*.
`bounded_relaxation.tex` already quotes the second sentence verbatim and
paraphrases the first; this file had not recorded it at all.

**2. His first two comments are NO LONGER on the public thread.** The API
returns 7 comments; the earliest is the 08:48Z "After thinking about it…". The
two quoted in the table above ("What are you trying to say with this report?
This is an intentional feature." / "Can you explain with an example?") survive
**only in the notification email**. ⚠ **The table's times are IST** (14:00,
14:02, 14:18, 17:10 = 08:30, 08:32, 08:48, 11:40 UTC), not UTC. Consequence: do
not quote those two lines as if a reader could find them on GitHub; paraphrase
(as the paper already does) or cite "notification email, 2026-08-21".

Issue: `github.com/RetireJS/retire.js/issues/615`, opened 2026-08-20T15:25:35Z,
closed `completed` 2026-08-21T11:40:15Z via `8c911d6`; `72438a0` referenced
2026-08-22T07:12:22Z.
