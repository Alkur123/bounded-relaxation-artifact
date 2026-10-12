/**
 * EXECUTE the Langfuse remediation, both released versions, side by side.
 *
 * `verify_langfuse_remediation.py` reads the released source at the tag. That
 * answers "what ships" and not "what it does", and the gap was recorded there
 * as a caveat. This file closes it: it fetches the shipped module at BOTH
 * releases, transpiles them, loads them with their out-of-scope imports stubbed
 * by recorders that decide nothing, and CALLS the real exported functions.
 *
 * FINDING (2026-08-20, emailed to security@langfuse.com):
 *   `packages/shared/src/in-app-agent/server/mcpPolicy.ts` --
 *   `withInAppAgentToolApproval` marks every tool `requireApproval: true`
 *   except those an allowlist / name prefix / role-derived set accepts, and the
 *   module recorded nothing when it waived the gate. A principal waiver, so
 *   R14-a is not engaged; R14-b is, and it was unmet.
 *
 * REMEDIATION: PR #16372, merged 2026-08-25T09:22:04Z, released in v4.18.0 at
 * 09:41:55Z.
 *
 * The four things this proves by running, not by reading:
 *
 *   P1  TREATMENT: waiving the gate now emits a `langfuse_tool_approval`
 *       record naming WHICH stage waived it.
 *       CONTROL: at v4.17.0 the identical tool is waived identically and the
 *       emitting function does not exist. Two runs, one output -- executed.
 *
 *   P2  The relaxation is UNCHANGED. For a matrix covering every branch, the
 *       public `withInAppAgentToolApproval` returns the same `requireApproval`
 *       at both releases. This was previously claimed from reading the diff;
 *       here it is decided by running both versions and comparing.
 *
 *   P3  The three sources are DISTINGUISHABLE -- auto, human and
 *       conversation_grant are each produced by the path that earns them.
 *
 *   P4  CONTROL on P3: a tool nobody approved yields no source and no record.
 *       A field present on every call would record nothing.
 *
 * Nothing here reaches Langfuse at runtime. The only network access is the
 * source download from raw.githubusercontent.com, and every fetched file is
 * printed with its SHA-256 so a reader can pin what was executed.
 *
 *   node prove_langfuse_remediation.mjs [--keep]
 *
 * Exits non-zero if any proof OR any control fails.
 */

import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { fileURLToPath, pathToFileURL } from "node:url";
import ts from "typescript";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const KEEP = process.argv.includes("--keep");

const TREATMENT = "v4.18.0"; // released 2026-08-25T09:41:55Z, after the merge
const CONTROL = "v4.17.0"; // released 2026-08-24T13:14:03Z, before the merge

const POLICY_PATH = "packages/shared/src/in-app-agent/server/mcpPolicy.ts";
const EVENTS_PATH = "packages/shared/src/in-app-agent/approvalEvents.ts";

const failures = [];

function head(title) {
  console.log("\n" + "=".repeat(74));
  console.log(title);
  console.log("=".repeat(74));
}

function check(label, ok, detail = "") {
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}${detail ? "  -- " + detail : ""}`);
  if (!ok) failures.push(label);
}

async function fetchSource(tag, repoPath) {
  const url = `https://raw.githubusercontent.com/langfuse/langfuse/${tag}/${repoPath}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`fetch ${res.status} ${url}`);
  const text = await res.text();
  const digest = crypto.createHash("sha256").update(text).digest("hex");
  console.log(
    `  ${tag}  ${repoPath.split("/").pop().padEnd(18)} ` +
      `${String(text.length).padStart(6)} bytes  sha256:${digest.slice(0, 16)}`,
  );
  return text;
}

/** Transpile TS to ESM and point the out-of-scope imports at local stubs. */
function toModule(source, rewrites) {
  let js = ts.transpileModule(source, {
    compilerOptions: {
      target: ts.ScriptTarget.ES2022,
      module: ts.ModuleKind.ESNext,
    },
  }).outputText;
  for (const [from, to] of Object.entries(rewrites)) {
    js = js.split(`"${from}"`).join(`"${to}"`).split(`'${from}'`).join(`"${to}"`);
  }
  return js;
}

// ---------------------------------------------------------------------------
// Stubs. Each stands in for something the finding is not about. None of them
// decides anything: the RBAC stub is never consulted because the policy object
// is built directly, and the constants carry their real shipped values.
// ---------------------------------------------------------------------------
const STUB_AGUI = `
export const EventType = {
  CUSTOM: "CUSTOM",
  TOOL_CALL_START: "TOOL_CALL_START",
  TOOL_CALL_END: "TOOL_CALL_END",
  TEXT_MESSAGE_START: "TEXT_MESSAGE_START",
};
`;

const STUB_RBAC = `
export const rbacCalls = [];
export function hasProjectAccessByRole(args) {
  rbacCalls.push(args);   // recorded, never consulted by these proofs
  return true;
}
`;

const STUB_DB = `
export const Role = {
  OWNER: "OWNER", ADMIN: "ADMIN", MEMBER: "MEMBER",
  VIEWER: "VIEWER", NONE: "NONE",
};
`;

// The real shipped value, from constants.ts at the same tag.
const STUB_CONSTANTS = `
export const IN_APP_AGENT_REDIRECT_TOOL_NAME = "langfuse_proposeRedirect";
`;

async function loadVersion(dir, tag, withEvents) {
  const policySrc = await fetchSource(tag, POLICY_PATH);
  const rewrites = {
    "@ag-ui/core": "./stub_agui.mjs",
    "../../features/rbac/projectAccessRights": "./stub_rbac.mjs",
    "../../db": "./stub_db.mjs",
    "../constants": "./stub_constants.mjs",
    "../approvalEvents": "./approvalEvents.mjs",
  };
  if (withEvents) {
    const eventsSrc = await fetchSource(tag, EVENTS_PATH);
    fs.writeFileSync(
      path.join(dir, "approvalEvents.mjs"),
      toModule(eventsSrc, { "@ag-ui/core": "./stub_agui.mjs" }),
    );
  }
  const file = path.join(dir, `mcpPolicy_${tag.replace(/\./g, "_")}.mjs`);
  fs.writeFileSync(file, toModule(policySrc, rewrites));
  return import(pathToFileURL(file).href);
}

// ---------------------------------------------------------------------------

async function main() {
  const dir = fs.mkdtempSync(path.join(HERE, ".probe-langfuse-"));
  try {
    for (const [name, body] of [
      ["stub_agui.mjs", STUB_AGUI],
      ["stub_rbac.mjs", STUB_RBAC],
      ["stub_db.mjs", STUB_DB],
      ["stub_constants.mjs", STUB_CONSTANTS],
    ]) {
      fs.writeFileSync(path.join(dir, name), body);
    }

    head("SOURCES EXECUTED (fetched, hashed, transpiled, imported)");
    const treat = await loadVersion(dir, TREATMENT, true);
    const ctrl = await loadVersion(dir, CONTROL, false);

    // A policy built by hand so the RBAC path is never the thing under test.
    // `createAnnotationQueue` is declared `approval` in the shipped table and
    // `listAnnotationQueues` is declared `auto`; both are granted here, which
    // is what a conversation-scoped "always allow" looks like.
    const GRANTED = ["listAnnotationQueues", "createAnnotationQueue"];
    const policy = {
      available: new Set(GRANTED),
      autoApproved: new Set(GRANTED),
    };
    const emptyPolicy = { available: new Set(), autoApproved: new Set() };

    // -- P2 first: establish the relaxation is identical before claiming the
    //    record is the only difference. -------------------------------------
    head("P2  THE RELAXATION IS UNCHANGED (both versions run and compared)");
    const matrix = {
      langfuseDocs_search: "name-prefix waiver",
      read: "sandbox allowlist waiver",
      bash: "sandbox allowlist waiver",
      langfuse_proposeRedirect: "redirect tool waiver",
      langfuse_listAnnotationQueues: "registry tool declared auto",
      langfuse_createAnnotationQueue: "registry tool granted for conversation",
      langfuse_deleteAnnotationQueue: "registry tool NOT granted",
      someRandomTool: "unknown tool",
    };
    const tools = Object.fromEntries(
      Object.keys(matrix).map((n) => [n, { name: n }]),
    );
    const after = treat.withInAppAgentToolApproval(tools, policy);
    const before = ctrl.withInAppAgentToolApproval(tools, policy);
    let identical = 0;
    for (const [name, why] of Object.entries(matrix)) {
      const a = after[name].requireApproval === true;
      const b = before[name].requireApproval === true;
      // A waived tool carries no `requireApproval` property at all; the gated
      // one carries `true`. Print that, not a derived boolean, so the line
      // says what the object holds.
      const word = (v) => (v ? "GATED" : "waived");
      check(
        `${name}`,
        a === b,
        `${CONTROL} ${word(b)}, ${TREATMENT} ${word(a)} (${why})`,
      );
      if (a === b) identical += 1;
    }
    check(
      "every branch decides identically",
      identical === Object.keys(matrix).length,
      `${identical}/${Object.keys(matrix).length} -- the waiver is exactly as permissive as before`,
    );

    // -- P1: the record now exists, and did not before. --------------------
    head("P1  THE WAIVER NOW LEAVES A RECORD (treatment), AND DID NOT (control)");
    const startEvent = {
      type: "TOOL_CALL_START",
      toolCallId: "tc-001",
      toolCallName: "langfuse_createAnnotationQueue",
    };
    const out = treat.withInAppAgentToolApprovalSidecars({
      events: [startEvent],
      policy,
    });
    check(
      "a record is emitted beside the tool call",
      out.length === 2,
      `${out.length} events out of 1 in`,
    );
    const sidecar = out[1];
    check(
      "the record is the approval event",
      sidecar?.name === "langfuse_tool_approval",
      `name=${sidecar?.name}`,
    );
    check(
      "it names WHICH stage waived the gate",
      sidecar?.value?.source === "conversation_grant",
      `source=${sidecar?.value?.source}`,
    );
    check(
      "it is bound to the call it describes",
      sidecar?.toolCallId === "tc-001" &&
        sidecar?.value?.toolName === "langfuse_createAnnotationQueue",
      `toolCallId=${sidecar?.toolCallId}`,
    );

    check(
      `CONTROL ${CONTROL}: no emitter exists at all`,
      ctrl.withInAppAgentToolApprovalSidecars === undefined &&
        ctrl.getInAppAgentToolApprovalSource === undefined,
      "both exports absent from the released module",
    );
    check(
      `CONTROL ${CONTROL}: yet the same tool is still waived`,
      before["langfuse_createAnnotationQueue"].requireApproval === undefined,
      "no requireApproval property -- same waiver, no record: the finding, executed",
    );

    // -- P3: the three sources are distinguishable. -------------------------
    head("P3  THE THREE APPROVAL PATHS ARE DISTINGUISHABLE");
    const src = (params) => treat.getInAppAgentToolApprovalSource(params);
    check(
      "human approval is attributed to the human",
      src({
        toolName: "langfuse_createAnnotationQueue",
        policy: emptyPolicy,
        toolCallId: "tc-9",
        humanApprovedToolCallId: "tc-9",
      }) === "human",
      "toolCallId matches the approved call",
    );
    check(
      "a conversation grant is attributed to the grant",
      src({
        toolName: "langfuse_createAnnotationQueue",
        policy,
        toolCallId: "tc-9",
      }) === "conversation_grant",
      "declared approval, granted for the conversation",
    );
    check(
      "a policy auto-allow is attributed to policy",
      src({
        toolName: "langfuseDocs_search",
        policy: emptyPolicy,
        toolCallId: "tc-9",
      }) === "auto",
      "the path the report named",
    );

    // -- P4: control on P3. -------------------------------------------------
    head("P4  CONTROL: A CALL NOBODY APPROVED PRODUCES NO RECORD");
    check(
      "no source for an unapproved tool",
      src({
        toolName: "langfuse_deleteAnnotationQueue",
        policy: emptyPolicy,
        toolCallId: "tc-9",
      }) === undefined,
      "undefined, so the field is not universally present",
    );
    const none = treat.withInAppAgentToolApprovalSidecars({
      events: [
        {
          type: "TOOL_CALL_START",
          toolCallId: "tc-002",
          toolCallName: "langfuse_deleteAnnotationQueue",
        },
      ],
      policy: emptyPolicy,
    });
    check(
      "and no sidecar is emitted for it",
      none.length === 1,
      `${none.length} event out of 1 in -- a record that is always present records nothing`,
    );

    head("VERDICT");
    if (failures.length === 0) {
      console.log(
        "  All proofs and controls hold.\n" +
          "  R14-b is satisfied by RUNNING the released module, not by reading it.\n" +
          "  The relaxation is unchanged; only the record changed.",
      );
    } else {
      console.log(`  ${failures.length} FAILED: ${failures.join(", ")}`);
    }
    return failures.length === 0 ? 0 : 1;
  } finally {
    if (KEEP) {
      console.log(`\n  (kept build dir: ${dir})`);
    } else {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  }
}

process.exit(await main());
