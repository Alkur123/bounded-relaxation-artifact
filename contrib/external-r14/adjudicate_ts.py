"""Adjudicate the TypeScript corpus, under the rubric fixed for the Python one.

Two steps, in the order `ADJUDICATION.md` fixes them:

  step 0   module role. In an analysis engine the analysis PRODUCES the verdict,
           so a later stage cannot be weakening one. A lint rule deciding a
           construct is acceptable, a type utility concluding an assignment is
           safe, a scorer computing a metric, a data-access filter narrowing a
           query, a developer UI: none of these has a prior verdict to weaken.
           Applied per module, with the rule stated, and the script REFUSES to
           run if any site's module has no rule.

  step 1+  read the source. Everything that survives step 0 is read against the
           lines it names and recorded with a class and a reason.

Writes `adjudication_ts.json`. Run `summarize_ts.py` to join it to the scan.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
RESULTS = HERE / "external_r14_ts_results.json"
PY_ADJ = HERE / "adjudication.json"
OUT = HERE / "adjudication_ts.json"

# ── step 0: module role. Prefix -> (role, reason) ──────────────────────────
# Ordered; the first matching prefix wins. Every rule is the same one the
# Python run applied to mypy, pylint, checkov and semgrep, restated for the
# module layouts of these subjects.
STEP0 = [
    (("eslint", "rules/"), ("lint rule",
     "a lint rule IS the analysis: it produces the verdict about a construct, "
     "so a permissive value written inside it is the analysis concluding, not "
     "a later stage weakening an earlier conclusion")),
    (("eslint", "linter/code-path-analysis/"), ("code-path analysis",
     "control-flow analysis that rules consume; it computes facts and reaches "
     "no verdict of its own")),
    (("eslint", "linter/esquery"), ("selector engine",
     "AST selector matching, an analysis primitive with no verdict")),
    (("typescript-eslint", "eslint-plugin/src/rules/"), ("lint rule",
     "same as eslint/rules: the rule produces the verdict")),
    (("typescript-eslint", "eslint-plugin/src/util/"), ("rule helper",
     "helpers the rules call while producing their verdict")),
    (("typescript-eslint", "type-utils/"), ("type analysis",
     "type-level analysis: concluding two types are compatible is the analysis "
     "producing a result, not a stage weakening one")),
    (("typescript-eslint", "typescript-estree/"), ("parser",
     "parsing and AST conversion, upstream of any verdict")),
    (("typescript-eslint", "scope-manager/"), ("scope analysis",
     "scope and binding analysis, upstream of any verdict")),
    (("typescript-eslint", "rule-tester/"), ("test infrastructure",
     "the harness rules are tested with; it ships to nobody's request path")),
    (("stylelint", "rules/"), ("lint rule",
     "same as eslint/rules: the rule produces the verdict")),
    (("stylelint", "utils/"), ("analysis predicate",
     "CSS/AST predicates and parsing helpers -- `isValid`, "
     "`isBlocklessAtRuleAfterSameNameBlocklessAtRule`, `findAnimationName` -- "
     "each of which computes the answer it returns rather than weakening an "
     "earlier one. `findAnimationName` is the interesting exception and is "
     "named rather than buried: it sets `shouldBeIgnored = true` and empties "
     "`animationNames` when the value uses non-standard syntax, which is 'the "
     "analysis could not run, so produce the safe empty result'. That is the "
     "LIVENESS rung's question, not this one, and it is reported here for the "
     "same reason 72 sites were deferred in the Python corpus. The two "
     "suppression-layer modules in this directory are read individually and "
     "are matched before this rule")),
    (("mastra", "playground/"), ("developer UI",
     "the local playground's React hooks; a chart filtering its own series is "
     "not a governance decision")),
    (("mastra", "playground-ui/"), ("developer UI", "as playground/")),
    (("mastra", "core/src/storage/"), ("data access",
     "a paged list() applying caller-supplied authorId/organizationId/projectId "
     "filters is a query, not a detection being narrowed")),
    (("mastra", "evals/src/scorers/"), ("metric computation",
     "an eval scorer computing a similarity or noise metric produces the "
     "number; there is no prior verdict for the arithmetic to weaken")),
    (("mastra", "core/src/datasets/"), ("metric computation", "as evals/scorers")),
    (("mastra", "core/src/evals/"), ("metric computation", "as evals/scorers")),
    (("mastra", "core/src/agent/durable/"), ("workflow plumbing",
     "durable-execution step wiring around a scorer call")),
    (("mastra", "core/src/workflows/dynamic/validate/"), ("schema repair",
     "workflow-schema validation and repair actions; `blocksCheckpoint: false` "
     "describes a repair's effect on a checkpoint, not a safety verdict")),
    (("mastra", "cli/"), ("developer tooling", "CLI file helpers")),
    # ---- extension subjects, 2026-08-19 ---------------------------------
    (("portkey-gateway", "src/middlewares/"), ("request validation",
     "a request validator producing its verdict about a host or a header; "
     "there is no earlier verdict for it to weaken")),
    (("promptfoo", "src/util/"), ("metric computation",
     "aggregation of evaluation results into metrics")),
    (("langfuse", "web/src/"), ("product UI",
     "React components and hooks in the application's own front end: a chart "
     "filtering its series or a dialog validating a form field is not a "
     "governance decision")),
    (("langfuse", "worker/src/"), ("background migration",
     "a backfill job over historical rows")),
    (("langfuse", "packages/shared/src/features/"), ("query and config validation",
     "query, monitor and pricing validators, each producing the verdict it "
     "returns rather than weakening an earlier one")),
    (("langfuse", "packages/shared/src/server/queries/"), ("query planning",
     "SQL filter pushdown planning; deciding a filter cannot be pushed down "
     "is the planner concluding, not a verdict being relaxed")),
    (("langfuse", "packages/shared/src/server/repositories/"), ("data access",
     "repository reads with caller-supplied filters")),
    (("langfuse", "packages/shared/src/server/services/"), ("query and schema services",
     "in-memory filter evaluation and dataset schema validation")),
    (("langfuse", "packages/shared/src/utils/"), ("schema validation",
     "JSON-schema validation producing its own verdict")),
    (("eslint", "config/config.js"), ("configuration normalisation",
     "severity normalisation happens before any rule runs, so no verdict "
     "exists yet. Worth a line in the write-up anyway: an unrecognised "
     "severity resolves to 0 (off), which is the shape the LIVENESS rung asks "
     "about rather than this one")),
    (("eslint", "shared/severity.js"), ("configuration normalisation",
     "as config/config.js: maps a configured severity name to its number")),
]

# ── a whole family that shares one verdict, stated once ────────────────────
# Portkey's plugin contract is `{verdict, error, data}` where verdict is the
# PASS/FAIL of the check, so `verdict = false` means the guardrail did NOT pass
# and the request is to be denied. The lexicon reads `verdict` as risk-carrying
# and `false` as its permissive extreme, which is exactly backwards here. Four
# of the ten were read individually (javelin, acuvity, qualifire, validUrls)
# and the convention is identical in each; the rule is then applied to the
# family rather than restated ten times.
FAMILY = [
    (("portkey-gateway", "plugins/"), dict(
        verdict="WITHDRAWN", klass="FP", finding="verdict-false-means-blocked",
        why="In this codebase a plugin returns `{verdict, error, data}` and "
            "`verdict: false` means the check did not pass, so the write the "
            "scanner read as permissive is the DENY branch. The lexicon "
            "assumes low/false is the permissive extreme for a risk-carrying "
            "name; a subject whose verdict field is a pass/fail of the check "
            "rather than a level of risk inverts that assumption. This is a "
            "new false-positive mechanism, distinct from a polarity guess "
            "being wrong about a NAME, and it is reported as an instrument "
            "defect rather than patched mid-run.",
        prior_work="none", executed=False)),
]

# ── step 1+: sites read individually, keyed (subject, module, line) ────────
READ = {
    # ---------------------------------------------------------------- UPHELD
    ("retire.js", "repo.ts", 161): dict(
        verdict="UPHELD", klass="B", finding="insecure-mode-unrecorded",
        why="`options.insecure` sets `rejectUnauthorized = false` on every "
            "advisory download, disabling TLS certificate verification for the "
            "channel the scanner's own evidence arrives on. A principal waiver, "
            "so the BOUND obligation is not engaged. The AUDIT obligation is, "
            "and nothing records it: the only other occurrences of `insecure` "
            "in the package are the CLI flag's declaration and its type. The "
            "run prints its findings without stating that the advisories "
            "behind them were fetched over an unverified channel, so a reader "
            "of a clean report cannot tell which kind of clean it is.",
        prior_work="none", executed=False),
    # ------------------------------------------------------------------ PASS
    ("stylelint", "utils/suppressionsService.mjs", 183): dict(
        verdict="PASS", klass="B", finding="suppression-bounded-by-baseline",
        why="`result.warnings = result.warnings.filter(...)` drops a rule's "
            "warnings ONLY under `problemsCount <= suppressionsCount`. That is "
            "the bound obligation met in a quantitative form stronger than any "
            "site in the Python corpus: the relaxation consults a magnitude of "
            "the evidence it overrides against an operator-committed count, and "
            "if the problems exceed the count NOTHING is suppressed and every "
            "problem is reported. The audit obligation is met at the system "
            "level rather than at the site -- the committed suppressions file "
            "is itself the record of what may be suppressed, and the function "
            "returns the `unused` remainder so a stale baseline is visible. "
            "The same system-level reading was applied to detect-secrets in the "
            "Python corpus and is applied here for the same reason.",
        prior_work="none", executed=False),
    # ------------------------------------------------------- WITHDRAWN (FP)
    ("mastra", "core/src/processors/processors/pii-detector.ts", 514): dict(
        verdict="WITHDRAWN", klass="FP", finding="null-means-no-rewrite",
        why="`return null` from `handleDetectedPII` means 'no message "
            "modification', which the line's own comment says. The scanner read "
            "it as a benign verdict because the FUNCTION's name carries "
            "detection polarity and `null` is the permissive extreme for a "
            "risk-carrying name. The PII was detected; what is null is the "
            "rewrite. This shape accounts for 11 of this corpus's proposals and "
            "is the single largest false-positive class in it.",
        prior_work="none", executed=False),
    # -------------------------------------------- extension: UPHELD
    ("langfuse", "packages/shared/src/in-app-agent/server/mcpPolicy.ts", 557): dict(
        verdict="UPHELD", klass="B", finding="auto-approval-unrecorded",
        why="`withInAppAgentToolApproval` marks every tool `requireApproval: "
            "true` EXCEPT those `isInAppAgentAutoApprovedToolName` accepts, so "
            "this predicate is the stage that removes a human approval gate "
            "from an agent's tool call. It is a principal waiver -- a name "
            "prefix, a local allowlist, and a role-derived `policy.autoApproved` "
            "set -- so the bound obligation is not engaged. The audit "
            "obligation is, and the module contains ZERO logging calls: nothing "
            "records that approval was skipped, so a reader of the agent's "
            "trace cannot distinguish a tool a human approved from one the "
            "policy waved through. The finding is the missing record, not the "
            "policy, which is a considered role-based design.",
        prior_work="none", executed=False),
    # ---------------------------------------------- extension: PASS
    ("langfuse", "packages/shared/src/server/deletionGuard.ts", 23): dict(
        verdict="PASS", klass="B", finding="waiver-logged-with-its-rule",
        why="An operator-configured project id in "
            "`LANGFUSE_DELETE_SKIP_PROJECT_IDS` skips a deletion, which for a "
            "retention obligation is the permissive direction. A principal "
            "waiver, so the bound obligation is not engaged. The audit "
            "obligation is met in the same branch and in a strong form: the "
            "log names the rule that fired (`skipReason`), the project, the "
            "entity type, and every entity id skipped, so the waiver is not "
            "merely recorded but enumerable after the fact.",
        prior_work="none", executed=False),
    # ------------------------------------ extension: read and withdrawn
    ("langfuse", "packages/shared/src/server/deletionGuard.ts", 44): dict(
        verdict="WITHDRAWN", klass="D", finding="entity-no-longer-exists",
        why="The sibling branch of the site above, taken when the project has "
            "already been deleted. Nothing exists to delete, so no verdict is "
            "being weakened. It is logged too, with `skipReason: "
            "PROJECT_NOT_FOUND`.",
        prior_work="none", executed=False),
    ("promptfoo", "src/assertions/guardrails.ts", 49): dict(
        verdict="WITHDRAWN", klass="OUT", finding="liveness-not-relaxation",
        why="When the provider returned no guardrail data the assertion passes "
            "with `reason: 'Guardrail was not applied'`. That is 'the check did "
            "not run, so produce the safe value', which is the LIVENESS rung's "
            "question and not this one. Worth recording twice over: the domain "
            "classifier missed it because the falsiness test is on a value "
            "carried in the provider response rather than on a call made in "
            "this function, and the code itself discharges the trace obligation "
            "the liveness rung would ask about, because the reason string says "
            "the guardrail was not applied.",
        prior_work="none", executed=False),
    ("promptfoo", "src/providers/openai/moderation.ts", 126): dict(
        verdict="WITHDRAWN", klass="OUT", finding="liveness-not-relaxation",
        why="An empty or missing `results` array from the moderation API maps "
            "to `{ flags: [] }`, i.e. nothing flagged, with no record. Same "
            "shape as the LlamaFirewall PII scanner the liveness rung owns in "
            "the Python corpus: an absent answer rendered as a clean one. "
            "Deferred, not counted, and named in the write-up because it is "
            "the more interesting of this subject's sites.",
        prior_work="none", executed=False),
    ("promptfoo", "src/commands/validate.ts", 265): dict(
        verdict="WITHDRAWN", klass="OUT", finding="liveness-not-relaxation",
        why="`summary.sessionSkipped = true` when connectivity failed, on the "
            "line after a log saying exactly that. The liveness rung's "
            "question, and answered.",
        prior_work="none", executed=False),
    ("promptfoo", "src/server/middleware/csrfProtection.ts", 44): dict(
        verdict="WITHDRAWN", klass="D", finding="loopback-is-not-cross-site",
        why="`isAllowedCrossSite` returns true when origin and target are both "
            "loopback. This is the closest this corpus came to a second "
            "finding and we declined it: the condition is a structural fact "
            "about the two hostnames rather than a verdict being weakened, and "
            "a local development server treating localhost-to-localhost as "
            "same-site is the documented intent. Recorded as declined rather "
            "than omitted, because a reader may weigh it differently.",
        prior_work="none", executed=False),
    # ------------------------------------------------- other individual reads
    ("eslint", "services/processor-service.js", 70): dict(
        verdict="WITHDRAWN", klass="FP", finding="ok-means-not-a-promise",
        why="`ok: true` in a result object reporting that a preprocessor did "
            "not return a promise. `ok` is permit-polarity in the lexicon and "
            "means something else here.",
        prior_work="none", executed=False),
    ("langchainjs", "create-langchain-integration/helpers/validate-pkg.ts", 10): dict(
        verdict="WITHDRAWN", klass="D", finding="verdict-produced-not-weakened",
        why="`return { valid: true }` is the validator PRODUCING its verdict "
            "about an npm package name, in a project-scaffolding helper that is "
            "not on any request path.",
        prior_work="none", executed=False),
    # RETIRED 2026-08-19 by amendment A3. This entry recorded a false
    # positive at mastra `validate-agent-instructions.ts:16`, where
    # `if (!Array.isArray(x)) return undefined` reached R14 because the
    # shared EMPTINESS_CALL_LEXICON knows `isinstance` and not its JS
    # spelling. The translator now renders `Array.isArray(x)` as
    # `isinstance(x, list)`, so the site is classified STRUCTURAL at the
    # scan and never reaches adjudication. See ADJUDICATION.md.
    ("stylelint", "utils/emitWarning.mjs", 83): dict(
        verdict="WITHDRAWN", klass="OUT", finding="test-only-helper",
        why="`clearEmittedWarnings()` throws unless `NODE_ENV === 'test'`. A "
            "test helper, and its own docstring says so.",
        prior_work="none", executed=False),
    ("retire.js", "depsdev.ts", 75): dict(
        verdict="WITHDRAWN", klass="OUT", finding="verdict-produced-not-weakened",
        why="`scoreToSeverity` maps a CVSS-ish score to high/medium/low. "
            "Returning 'low' for a low score is the classification PRODUCING "
            "its verdict.",
        prior_work="none", executed=False),
}

# every `return null` in the two mastra detectors shares one verdict, and the
# rule is stated once rather than copied nine times
DETECTOR_NULL = [
    ("mastra", "core/src/processors/processors/pii-detector.ts"),
    ("mastra", "core/src/processors/processors/prompt-injection-detector.ts"),
    ("mastra", "core/src/processors/processors/language-detector.ts"),
]


def step0_rule(subject: str, module: str):
    for (subj, prefix), rule in STEP0:
        if subject == subj and module.startswith(prefix):
            return rule
    return None


def main() -> int:
    res = json.loads(RESULTS.read_text(encoding="utf-8"))
    surface_regex = json.loads(PY_ADJ.read_text(encoding="utf-8"))["_surface_regex"]
    surf = re.compile(surface_regex, re.I)

    entries, uncovered = [], []
    for s in res["subjects"]:
        if s.get("candidates") is None:
            continue
        stratum = s.get("stratum", "A")
        for c in s["candidates"]:
            if c.get("domain") != "R14":
                continue
            if not (stratum == "B" or surf.search(c["module"])):
                continue
            key = (s["key"], c["module"], c["line"])
            if key in READ:
                entries.append({"subject": key[0], "module": key[1], "line": key[2],
                                "class": READ[key]["klass"], **{
                                    k: v for k, v in READ[key].items()
                                    if k != "klass"}})
                continue
            fam = next((v for (subj, pre), v in FAMILY
                        if s["key"] == subj and c["module"].startswith(pre)), None)
            if fam is not None:
                entries.append({"subject": s["key"], "module": c["module"],
                                "line": c["line"], "class": fam["klass"],
                                **{k: v for k, v in fam.items() if k != "klass"}})
                continue
            if (s["key"], c["module"]) in DETECTOR_NULL:
                entries.append({
                    "subject": s["key"], "module": c["module"], "line": c["line"],
                    "verdict": "WITHDRAWN", "class": "FP",
                    "finding": "null-means-no-rewrite",
                    "why": "`return null` from a handler whose name carries "
                           "detection polarity means 'no message modification', "
                           "not 'nothing detected'. See the pii-detector entry "
                           "for the full reasoning; the rule is stated once and "
                           "applied to every site of this shape.",
                    "prior_work": "none", "executed": False})
                continue
            rule = step0_rule(s["key"], c["module"])
            if rule is None:
                uncovered.append(key)
                continue
            role, reason = rule
            entries.append({
                "subject": s["key"], "module": c["module"], "line": c["line"],
                "verdict": "WITHDRAWN", "class": "OUT",
                "finding": f"step0:{role.replace(' ', '-')}",
                "why": reason, "prior_work": "none", "executed": False})

    if uncovered:
        print("MODULES WITH NO STEP-0 RULE, refusing to guess:")
        for u in sorted(set((a, b) for a, b, _ in uncovered)):
            print("   ", u)
        return 1

    payload = {
        "_about": "Adjudication of the TypeScript corpus, under the rubric "
                  "fixed in ADJUDICATION.md for the Python one. Step 0 is "
                  "applied by module role and step 1+ by reading the source.",
        "_frontend": "typescript",
        "_surface_regex": surface_regex,
        "_step0_note": "A site dismissed at step 0 is NOT a scanner error. It "
                       "is a site the rung has no question about, because no "
                       "prior verdict existed for the branch to weaken.",
        "_adjudicated_subjects": sorted(
            {s["key"] for s in res["subjects"] if s.get("candidates") is not None}),
        "entries": sorted(entries, key=lambda e: (e["subject"], e["module"], e["line"])),
    }
    OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    v = Counter(e["verdict"] for e in entries)
    k = Counter(e["class"] for e in entries)
    print(f"adjudicated {len(entries)} decision-surface sites")
    print("  verdicts:", dict(v))
    print("  classes :", dict(k))
    print(f"  written : {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
