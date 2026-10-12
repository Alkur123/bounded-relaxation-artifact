"""Verify the Langfuse remediation against the RELEASED tag, with a control.

Finding (2026-08-20, emailed to security@langfuse.com): in
`packages/shared/src/in-app-agent/server/mcpPolicy.ts`,
`withInAppAgentToolApproval` marks every tool `requireApproval: true` except
those `isInAppAgentAutoApprovedToolName` accepts -- by name prefix, by a local
allowlist, or by the role-derived `policy.autoApproved` set. A principal waiver,
so R14-a (BOUNDED) is not engaged. R14-b (AUDITED) is, and the module contained
no logging call of any kind: nothing recorded that approval had been skipped.

Remediation: PR #16372, `feat(in-app-agent): record tool approval source in the
event stream`, merged 2026-08-25T09:22:04Z as c34022568c59a4fc31f669f5092cce4bc12201b5,
released in v4.18.0 at 2026-08-25T09:41:55Z -- 19m51s after the merge.

WHAT THIS SCRIPT IS. It checks the released source tree at the tag a user
actually deploys, and the tag before it as a control. Reading released source
tells you what ships; running it tells you what it does.

THE CAVEAT THAT USED TO LIVE HERE IS CLOSED. This file once said Langfuse is a
deployed server rather than a CLI, so there was no equivalent to
`verify_retirejs_remediation.py` installing and running the package. That was
true of a whole-product run and false of the claim: the finding is about two
exported functions, and those can be executed. `prove_langfuse_remediation.mjs`
now fetches the shipped module at BOTH releases, transpiles them, stubs only
what the finding is not about, and CALLS the real functions -- proving that the
record appears, that it names the stage, that the relaxation decides identically
at both versions, and that a call nobody approved still produces nothing.

This file is kept because the two answer different questions. This one asks
whether the code is present in the released tree, cheaply and over the whole
chain from predicate to span. The other asks what that code does. Neither
replaces the other, and only the second is execution evidence.

The control is the point. A field that is present in every version records
nothing about this fix, so "present at v4.18.0" is only half a result. The other
half is "absent at v4.17.0", the release published 2026-08-24T13:14:03Z, before
the merge.

    python verify_langfuse_remediation.py

Needs network (raw.githubusercontent.com). Exit 0 if every check behaves, 1
otherwise.
"""

import sys
import urllib.request

TREATMENT = "v4.18.0"   # published 2026-08-25T09:41:55Z, 19m51s after the merge
CONTROL = "v4.17.0"     # published 2026-08-24T13:14:03Z, before the merge
LATEST = "v4.21.0"      # published 2026-08-26T12:36:06Z, to show it was not reverted

RAW = "https://raw.githubusercontent.com/langfuse/langfuse/{tag}/{path}"

POLICY = "packages/shared/src/in-app-agent/server/mcpPolicy.ts"
EVENTS = "packages/shared/src/in-app-agent/approvalEvents.ts"
AGENT = "worker/src/features/in-app-agent/runtime/agent.ts"
INSTR = "worker/src/features/in-app-agent/runtime/instrumentation.ts"

# The audit record R14-b asks for, traced from the predicate that waives the
# gate all the way to the span a trace reader actually opens. Each entry is
# (file, token, why it matters).
CHAIN = [
    (POLICY, "getInAppAgentToolApprovalSource",
     "the predicate we named now returns WHICH stage waived approval, not a bare bool"),
    (POLICY, "withInAppAgentToolApprovalSidecars",
     "every TOOL_CALL_START in the stream gets an approval record beside it"),
    (EVENTS, "langfuse_tool_approval",
     "the record is a first-class event, not a log line"),
    (EVENTS, "conversation_grant",
     "the three sources are distinguishable, which was the whole finding"),
    (AGENT, "withInAppAgentToolApprovalSidecars",
     "the sidecar builder is CALLED on the execution path"),
    (INSTR, "toolCallApprovalSource",
     "the source reaches the TOOL span metadata a trace reader sees"),
]

# The relaxation itself must be UNCHANGED. That was never the ask, and a fix
# that quietly narrowed the auto-approval set would be a different outcome that
# happens to look like this one.
UNCHANGED = [
    (POLICY, "langfuseDocs_", "the name-prefix waiver still exists"),
    (POLICY, "IN_APP_AGENT_LOCAL_AUTO_APPROVED_TOOL_NAMES",
     "the local allowlist waiver still exists"),
    (POLICY, "policy.autoApproved", "the role-derived waiver still exists"),
]


def fetch(tag, path):
    url = RAW.format(tag=tag, path=path)
    with urllib.request.urlopen(url, timeout=60) as r:
        if r.status != 200:
            raise SystemExit("fetch failed {} {}".format(r.status, url))
        return r.read().decode("utf-8")


def main():
    results = []

    def check(label, ok, detail):
        results.append((label, ok, detail))

    cache = {}

    def get(tag, path):
        if (tag, path) not in cache:
            cache[(tag, path)] = fetch(tag, path)
        return cache[(tag, path)]

    # ---- treatment: the audit chain is present at the released tag ---------
    for path, token, why in CHAIN:
        src = get(TREATMENT, path)
        n = src.count(token)
        check("{} :: {}".format(path.rsplit("/", 1)[-1], token),
              n > 0, "{}x at {} -- {}".format(n, TREATMENT, why))

    # ---- control: absent before the merge ----------------------------------
    # Only the tokens introduced by this PR. `policy.autoApproved` and friends
    # predate it by design, so asserting their absence would be wrong.
    for path, token, _why in CHAIN:
        src = get(CONTROL, path)
        n = src.count(token)
        check("CONTROL {} :: {}".format(path.rsplit("/", 1)[-1], token),
              n == 0, "{}x at {} (expected 0)".format(n, CONTROL))

    # ---- the relaxation is unchanged, which is the rung's actual claim -----
    for path, token, why in UNCHANGED:
        before, after = get(CONTROL, path), get(TREATMENT, path)
        check("relaxation intact :: {}".format(token),
              token in before and token in after,
              "present at both {} and {} -- {}".format(CONTROL, TREATMENT, why))

    # ---- not reverted ------------------------------------------------------
    latest = get(LATEST, POLICY)
    check("still present at {}".format(LATEST),
          "getInAppAgentToolApprovalSource" in latest,
          "the fix survives into the newest release, not reverted")

    width = max(len(x) for x, _o, _d in results)
    failed = 0
    print()
    for label, ok, detail in results:
        if not ok:
            failed += 1
        print("  [{}] {:{}s}  {}".format("PASS" if ok else "FAIL",
                                         label, width, detail))
    print()
    if failed:
        print("{} of {} checks FAILED".format(failed, len(results)))
        return 1
    print("all {} checks pass -- R14-b is satisfied in released code".format(
        len(results)))
    print("audit_field = 'toolCallApprovalSource' (span) / 'source' (event)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
