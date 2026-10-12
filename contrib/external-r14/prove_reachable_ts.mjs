/**
 * Execute the TypeScript corpus's upheld finding against the shipped code.
 *
 * The twin of `prove_reachable.py`, and it exists for the same objection: a
 * static reading says a branch COULD do something, and a reader is entitled to
 * ask whether it does. This extracts the real function from the pinned
 * checkout by AST, prints its source and a hash of it, transpiles it, and runs
 * it against stubs that record and decide nothing.
 *
 * Nothing here reaches the network. `https.get` and `http.get` are replaced by
 * a recorder that captures the request options and never fires the callback,
 * so the promise the function returns is simply never settled and we read what
 * it asked for.
 *
 * FINDING: retire.js `node/src/repo.ts`, `loadJson`
 *   Under `options.insecure` the request is built with
 *   `rejectUnauthorized = false`, disabling TLS certificate verification on the
 *   channel the scanner's own advisory data arrives on, and nothing in the run
 *   records that it happened.
 *
 * CONTROL: the same function with `insecure` unset must NOT disable
 * verification. A proof whose control also "passes" has proved nothing.
 *
 * Usage: node prove_reachable_ts.mjs [--clone-root C:/r14-subjects-ts]
 * Exits non-zero if any proof OR any control fails.
 */

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { execFileSync } from "node:child_process";
import ts from "typescript";

const args = process.argv.slice(2);
const rootIdx = args.indexOf("--clone-root");
const CLONE_ROOT = rootIdx >= 0 ? args[rootIdx + 1] : "C:/r14-subjects-ts";

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

/** Pull one top-level function out of a file by name, using the AST. */
function extractFunction(file, name) {
  const text = fs.readFileSync(file, "utf8");
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true);
  let found = null;
  const visit = (n) => {
    if (ts.isFunctionDeclaration(n) && n.name && n.name.text === name) found = n;
    ts.forEachChild(n, visit);
  };
  visit(sf);
  if (!found) throw new Error(`no function ${name} in ${file}`);
  const start = sf.getLineAndCharacterOfPosition(found.getStart(sf)).line + 1;
  return { source: found.getText(sf), line: start };
}

function sha256(s) {
  return crypto.createHash("sha256").update(s, "utf8").digest("hex");
}

// ───────────────────────────────────────────────────────────────────────────

head("retire.js  node/src/repo.ts::loadJson  --  insecure mode leaves no trace");

const repo = path.join(CLONE_ROOT, "retire.js");
const file = path.join(repo, "node", "src", "repo.ts");
if (!fs.existsSync(file)) {
  console.log(`  SKIP  subject not checked out at ${file}`);
  console.log("        third-party source is deliberately never committed;");
  console.log("        run run_external_r14_ts.py first to acquire it.");
  process.exit(0);
}

let sha = "unknown";
try {
  sha = execFileSync("git", ["rev-parse", "HEAD"], { cwd: repo })
    .toString().trim();
} catch { /* a checkout without git metadata is still runnable */ }

const { source, line } = extractFunction(file, "loadJson");
console.log(`\nsubject commit : ${sha}`);
console.log(`extracted from : node/src/repo.ts:${line}`);
console.log(`sha256(source) : ${sha256(source)}`);
console.log("\n--- the shipped function, verbatim ---");
console.log(source);
console.log("--- end ---\n");

// Transpile the extracted TypeScript and bind it to stubs. The function is
// evaluated in a wrapper that supplies every free name it uses, so nothing
// resolves to a real module.
const js = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.None },
}).outputText;

function runWith(options) {
  const captured = [];
  const logged = [];
  const recorder = (reqOptions) => {
    captured.push(reqOptions);
    // never invoke the callback: the promise stays pending on purpose, and we
    // read what the function ASKED FOR rather than what any server said
    return { on() { return this; } };
  };
  const stubs = {
    https: { get: recorder, RequestOptions: {} },
    http: { get: recorder },
    URL: { parse: (u) => ({ href: u, hostname: "stub", path: "/stub" }) },
    ProxyAgent: class { constructor() { /* records nothing */ } },
  };
  const make = new Function(
    "https", "http", "URL", "ProxyAgent",
    `${js}\n;return loadJson;`);
  const loadJson = make(stubs.https, stubs.http, stubs.URL, stubs.ProxyAgent);
  const log = {
    info: (m) => logged.push(["info", String(m)]),
    warn: (m) => logged.push(["warn", String(m)]),
    error: (m) => logged.push(["error", String(m)]),
    debug: (m) => logged.push(["debug", String(m)]),
  };
  // the returned promise is deliberately never awaited; it cannot settle
  void loadJson("https://api.deps.dev/v3alpha/stub", { log, ...options });
  return { captured, logged };
}

// ── the finding ────────────────────────────────────────────────────────────
const insecure = runWith({ insecure: true });
check("the shipped function was reached and built a request",
  insecure.captured.length === 1,
  `${insecure.captured.length} request(s) built`);
check("with --insecure, TLS certificate verification is DISABLED",
  insecure.captured[0]?.rejectUnauthorized === false,
  `rejectUnauthorized = ${JSON.stringify(insecure.captured[0]?.rejectUnauthorized)}`);

const trace = insecure.logged.map(([, m]) => m).join(" | ").toLowerCase();
const mentions = /insecure|reject|unverified|certificate|tls|ssl/.test(trace);
check("and nothing in the run records that it was disabled", !mentions,
  `log lines: ${JSON.stringify(insecure.logged.map(([l, m]) => `${l}: ${m}`))}`);

// ── the control ────────────────────────────────────────────────────────────
head("CONTROL  --  the same function with insecure unset");
const secure = runWith({});
check("the control reached the same code", secure.captured.length === 1);
check("verification is left alone when the flag is not passed",
  secure.captured[0]?.rejectUnauthorized === undefined,
  `rejectUnauthorized = ${JSON.stringify(secure.captured[0]?.rejectUnauthorized)}`);

const controlSecure = runWith({ insecure: false });
check("and an explicit insecure:false also leaves it alone",
  controlSecure.captured[0]?.rejectUnauthorized === undefined,
  `rejectUnauthorized = ${JSON.stringify(controlSecure.captured[0]?.rejectUnauthorized)}`);

// ───────────────────────────────────────────────────────────────────────────
head("RESULT");
if (failures.length) {
  console.log(`  ${failures.length} check(s) failed:`);
  for (const f of failures) console.log("    -", f);
  process.exit(1);
}
console.log("  1 finding executed against shipped code, 3 controls held.");
console.log("  The finding is that the relaxation is UNRECORDED, not that the");
console.log("  flag is wrong: an operator may legitimately ask for --insecure.");
console.log("  What the run does not say is that the advisories behind its");
console.log("  verdict arrived over a channel it did not verify.");
process.exit(0);
