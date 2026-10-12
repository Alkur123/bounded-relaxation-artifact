/**
 * A second front end for R14's site proposer: TypeScript and JavaScript.
 *
 * WHAT THIS IS, AND DELIBERATELY IS NOT
 * -------------------------------------
 * Paper 14's proposer is a Python AST tool, so the population it can speak
 * about is Python guardrails rather than guardrails. This file exists to test
 * whether that is a limit of the rung or a limit of the tool.
 *
 * It is a PURE SYNTAX EXTRACTOR. It decides nothing. Every judgement that
 * involves a lexicon -- is this name risk-carrying, is this value the
 * permissive extreme, does this guard consult a magnitude, does this block
 * leave a trace, which rung owns this site -- stays in the shipped Python
 * (`backend/engine/maryada_discover.py`), which `ts_frontend.py` calls with
 * what this file emits. Two front ends that each decided what a risk-carrying
 * name is would eventually disagree, and the disagreement would be invisible.
 *
 * So this file answers only questions that need an AST of THIS language:
 *
 *   - which conditions dominate this statement, by nesting or by a bail-out
 *   - what is written, to what name, in what kind of position
 *   - what calls, assignment targets and object keys appear in the block
 *   - is this inside a catch clause
 *   - what are the enclosing function's parameters, and which locals were
 *     bound from a call
 *
 * Guard conditions are emitted TWICE: once as they read in the source, and
 * once translated into Python expression text, so the shipped
 * `_GuardInspector` and `classify_domain` can be run over them unmodified.
 * The translation is lossy in one direction only: an expression it cannot
 * render is emitted as raw source, which Python then fails to parse and
 * skips. A skipped guard cannot supply a bound, so the effect is to
 * UNDER-report bounds and therefore OVER-report R14-a. That is the same
 * direction the Python front end already errs in, and it is declared here
 * rather than discovered later.
 *
 * KNOWN ASYMMETRY WITH THE PYTHON FRONT END, stated up front: the Python one
 * resolves a guard through same-module helpers two levels deep; this one
 * resolves one. A bound reached two helpers away reads as unbounded here.
 *
 * Usage:  node ts_propose.mjs <root> [--subject NAME] [--json OUT]
 */

import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import ts from "typescript";

// ───────────────────────────────────────────────────────────────────────────
// File discovery. Mirrors iter_python_files: shipped source only.
// ───────────────────────────────────────────────────────────────────────────

const SKIP_DIRS = new Set([
  "node_modules", "dist", "build", "out", "lib-esm", "coverage",
  ".git", ".github", ".yarn", ".turbo", ".next", "docs", "examples",
  "example", "fixtures", "__fixtures__", "__snapshots__", "benchmarks",
  "scripts", "website", "site", "e2e",
]);

const TEST_RE = /(^|[.\-/])(test|tests|spec|__tests__)([.\-/]|$)/i;
const SRC_RE = /\.(ts|tsx|mts|cts|js|mjs|cjs|jsx)$/;
const DECL_RE = /\.d\.(ts|mts|cts)$/;

function* iterSourceFiles(root, { skipTests = true } = {}) {
  const stack = [root];
  while (stack.length) {
    const dir = stack.pop();
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const e of entries) {
      const full = path.join(dir, e.name);
      if (e.isDirectory()) {
        if (SKIP_DIRS.has(e.name)) continue;
        if (skipTests && TEST_RE.test(e.name)) continue;
        stack.push(full);
      } else if (e.isFile()) {
        if (!SRC_RE.test(e.name) || DECL_RE.test(e.name)) continue;
        if (skipTests && TEST_RE.test(e.name)) continue;
        yield full;
      }
    }
  }
}

// ───────────────────────────────────────────────────────────────────────────
// Rendering a TS expression as Python expression text.
// ───────────────────────────────────────────────────────────────────────────

const BINOP = new Map([
  [ts.SyntaxKind.AmpersandAmpersandToken, " and "],
  [ts.SyntaxKind.BarBarToken, " or "],
  [ts.SyntaxKind.EqualsEqualsToken, " == "],
  [ts.SyntaxKind.EqualsEqualsEqualsToken, " == "],
  [ts.SyntaxKind.ExclamationEqualsToken, " != "],
  [ts.SyntaxKind.ExclamationEqualsEqualsToken, " != "],
  [ts.SyntaxKind.LessThanToken, " < "],
  [ts.SyntaxKind.LessThanEqualsToken, " <= "],
  [ts.SyntaxKind.GreaterThanToken, " > "],
  [ts.SyntaxKind.GreaterThanEqualsToken, " >= "],
  [ts.SyntaxKind.PlusToken, " + "],
  [ts.SyntaxKind.MinusToken, " - "],
  [ts.SyntaxKind.AsteriskToken, " * "],
  [ts.SyntaxKind.SlashToken, " / "],
  [ts.SyntaxKind.PercentToken, " % "],
  [ts.SyntaxKind.InKeyword, " in "],
]);

/** Membership methods that read as `x in collection` in Python. */
const MEMBERSHIP = new Set(["includes", "has", "contains"]);

function pyString(s) {
  return "'" + String(s).replace(/\\/g, "\\\\").replace(/'/g, "\\'")
    .replace(/\n/g, "\\n").replace(/\r/g, "") + "'";
}

/** Translate a TS expression to Python source text, or null if we cannot. */
function toPy(node) {
  if (!node) return null;
  switch (node.kind) {
    case ts.SyntaxKind.Identifier:
      return node.text === "undefined" ? "None" : node.text;
    case ts.SyntaxKind.ThisKeyword:
      return "self";
    case ts.SyntaxKind.TrueKeyword:
      return "True";
    case ts.SyntaxKind.FalseKeyword:
      return "False";
    case ts.SyntaxKind.NullKeyword:
      return "None";
    case ts.SyntaxKind.NumericLiteral:
      return node.text;
    case ts.SyntaxKind.StringLiteral:
    case ts.SyntaxKind.NoSubstitutionTemplateLiteral:
      return pyString(node.text);
    case ts.SyntaxKind.ArrayLiteralExpression:
      return node.elements.length === 0 ? "[]" : null;
    case ts.SyntaxKind.ObjectLiteralExpression:
      return node.properties.length === 0 ? "{}" : null;
    case ts.SyntaxKind.ParenthesizedExpression: {
      const inner = toPy(node.expression);
      return inner === null ? null : `(${inner})`;
    }
    case ts.SyntaxKind.NonNullExpression:
    case ts.SyntaxKind.AsExpression:
    case ts.SyntaxKind.TypeAssertionExpression:
    case ts.SyntaxKind.SatisfiesExpression:
      return toPy(node.expression);
    case ts.SyntaxKind.PrefixUnaryExpression: {
      const inner = toPy(node.operand);
      if (inner === null) return null;
      if (node.operator === ts.SyntaxKind.ExclamationToken) return `not (${inner})`;
      if (node.operator === ts.SyntaxKind.MinusToken) return `-${inner}`;
      if (node.operator === ts.SyntaxKind.PlusToken) return inner;
      return null;
    }
    case ts.SyntaxKind.PropertyAccessExpression: {
      const base = toPy(node.expression);
      if (base === null) return null;
      // `xs.length` is `len(xs)`; the evidence lexicon knows `len`.
      if (node.name.text === "length") return `len(${base})`;
      return `${base}.${node.name.text}`;
    }
    case ts.SyntaxKind.ElementAccessExpression: {
      const base = toPy(node.expression);
      const arg = toPy(node.argumentExpression);
      return base === null || arg === null ? null : `${base}[${arg}]`;
    }
    case ts.SyntaxKind.CallExpression: {
      const callee = node.expression;
      // `Array.isArray(x)` is exactly Python's `isinstance(x, list)`, which the
      // shared EMPTINESS_CALL_LEXICON knows and classifies as STRUCTURAL. Added
      // 2026-08-19 as amendment A3: without it a JS type guard reached R14
      // while its Python twin did not, which is the instrument reporting on a
      // spelling difference. A translation rule, not a lexicon change -- the
      // same kind already applied to `.length` and `.includes()`.
      if (ts.isPropertyAccessExpression(callee)
          && callee.name.text === "isArray"
          && ts.isIdentifier(callee.expression)
          && callee.expression.text === "Array"
          && node.arguments.length === 1) {
        const arg = toPy(node.arguments[0]);
        if (arg !== null) return `isinstance(${arg}, list)`;
      }
      // `xs.includes(y)` / `set.has(y)` is `y in xs`, which is the form the
      // waiver-skip detector and R3's classifiers are written against.
      if (ts.isPropertyAccessExpression(callee)
          && MEMBERSHIP.has(callee.name.text) && node.arguments.length === 1) {
        const base = toPy(callee.expression);
        const arg = toPy(node.arguments[0]);
        if (base !== null && arg !== null) return `${arg} in ${base}`;
      }
      const fn = toPy(callee);
      if (fn === null) return null;
      const args = [];
      for (const a of node.arguments) {
        const rendered = toPy(a);
        if (rendered === null) return null;
        args.push(rendered);
      }
      return `${fn}(${args.join(", ")})`;
    }
    case ts.SyntaxKind.BinaryExpression: {
      const op = BINOP.get(node.operatorToken.kind);
      if (!op) return null;
      const l = toPy(node.left);
      const r = toPy(node.right);
      if (l === null || r === null) return null;
      // `x === null` and `x == undefined` are `x is None` for R3's classifier.
      if ((op === " == " || op === " != ") && (r === "None" || l === "None")) {
        const other = r === "None" ? l : r;
        return op === " == " ? `${other} is None` : `${other} is not None`;
      }
      return `${l}${op}${r}`;
    }
    case ts.SyntaxKind.ConditionalExpression: {
      const c = toPy(node.condition);
      const w = toPy(node.whenTrue);
      const e = toPy(node.whenFalse);
      return c === null || w === null || e === null ? null : `(${w} if ${c} else ${e})`;
    }
    default:
      return null;
  }
}

// ───────────────────────────────────────────────────────────────────────────
// Small AST queries
// ───────────────────────────────────────────────────────────────────────────

/** Dotted callee name, as `_callee_name` produces in Python. */
function calleeName(expr) {
  const parts = [];
  let f = expr;
  while (ts.isPropertyAccessExpression(f)) {
    parts.push(f.name.text);
    f = f.expression;
  }
  if (ts.isIdentifier(f)) parts.push(f.text);
  else if (f.kind === ts.SyntaxKind.ThisKeyword) parts.push("self");
  else if (parts.length === 0) return null;
  return parts.reverse().join(".");
}

/** (name, kind) for an assignment target we can reason about. */
function targetName(node) {
  if (ts.isIdentifier(node)) return [node.text, "assign"];
  if (ts.isPropertyAccessExpression(node)) return [node.name.text, "assign"];
  if (ts.isElementAccessExpression(node)) {
    const a = node.argumentExpression;
    if (a && ts.isStringLiteralLike(a)) return [a.text, "subscript"];
  }
  return null;
}

function statementsOf(node) {
  if (!node) return [];
  if (ts.isBlock(node)) return Array.from(node.statements);
  return [node];
}

/** Does control always leave this block? Mirrors `_always_exits`. */
function alwaysExits(node) {
  const stmts = statementsOf(node);
  if (!stmts.length) return false;
  const last = stmts[stmts.length - 1];
  if (ts.isReturnStatement(last) || ts.isThrowStatement(last)
      || ts.isContinueStatement(last) || ts.isBreakStatement(last)) return true;
  if (ts.isIfStatement(last)) {
    return Boolean(last.elseStatement) && alwaysExits(last.thenStatement)
      && alwaysExits(last.elseStatement);
  }
  if (ts.isTryStatement(last)) {
    return alwaysExits(last.tryBlock)
      && (!last.catchClause || alwaysExits(last.catchClause.block));
  }
  return false;
}

const FN_KINDS = new Set([
  ts.SyntaxKind.FunctionDeclaration, ts.SyntaxKind.FunctionExpression,
  ts.SyntaxKind.ArrowFunction, ts.SyntaxKind.MethodDeclaration,
  ts.SyntaxKind.Constructor, ts.SyntaxKind.GetAccessor,
  ts.SyntaxKind.SetAccessor,
]);

function isFunctionLike(node) {
  return FN_KINDS.has(node.kind);
}

function functionName(node, fallback) {
  if (node.name && ts.isIdentifier(node.name)) return node.name.text;
  if (node.kind === ts.SyntaxKind.Constructor) return "constructor";
  return fallback;
}

function paramNames(node) {
  const out = [];
  for (const p of node.parameters || []) {
    if (ts.isIdentifier(p.name)) out.push(p.name.text);
    else {
      // destructured parameter: every bound name is a parameter
      const walk = (b) => {
        for (const el of b.elements || []) {
          if (!el.name) continue;
          if (ts.isIdentifier(el.name)) out.push(el.name.text);
          else walk(el.name);
        }
      };
      walk(p.name);
    }
  }
  return out;
}

// ───────────────────────────────────────────────────────────────────────────
// The walker
// ───────────────────────────────────────────────────────────────────────────

class Walker {
  constructor(subject, moduleRel, sourceFile) {
    this.subject = subject;
    this.module = moduleRel;
    this.sf = sourceFile;
    this.out = [];
    this.guards = [];            // [{src, py, line}]
    this.inHandler = 0;
    this.fnStack = ["<module>"];
    this.blockStack = [];
    this.boundScopes = [new Set()];
    this.paramStack = [new Set()];
    this.fromCallStack = [new Set()];
    this.localFns = new Map();   // same-file functions, for one-level guards
  }

  line(node) {
    return this.sf.getLineAndCharacterOfPosition(node.getStart(this.sf)).line + 1;
  }

  src(node) {
    try {
      return node.getText(this.sf);
    } catch {
      return "";
    }
  }

  guardOf(expr) {
    const py = toPy(expr);
    return { src: this.src(expr), py, line: this.line(expr) };
  }

  negated(guard) {
    return {
      src: `!(${guard.src})`,
      py: guard.py === null ? null : `not (${guard.py})`,
      line: guard.line,
    };
  }

  isBound(name) {
    return this.boundScopes.some((s) => s.has(name));
  }

  bind(name) {
    if (name) this.boundScopes[this.boundScopes.length - 1].add(name);
  }

  bindPattern(nameNode) {
    if (!nameNode) return;
    if (ts.isIdentifier(nameNode)) {
      this.bind(nameNode.text);
      return;
    }
    for (const el of nameNode.elements || []) {
      if (el.name) this.bindPattern(el.name);
    }
  }

  under(guard, body) {
    this.guards.push(guard);
    this.walkBlock(statementsOf(body));
    this.guards.pop();
  }

  walkBlock(stmts) {
    const depth = this.guards.length;
    this.blockStack.push(stmts);
    for (const st of stmts) {
      this.stmt(st);
      this.absorbFlowGuard(st);
    }
    this.blockStack.pop();
    this.guards.length = depth;
  }

  absorbFlowGuard(st) {
    if (!ts.isIfStatement(st)) return;
    const g = this.guardOf(st.expression);
    if (alwaysExits(st.thenStatement)) this.guards.push(this.negated(g));
    if (st.elseStatement && alwaysExits(st.elseStatement)) this.guards.push(g);
  }

  // -- collect same-file functions so a guard can be resolved one level -----
  collectLocalFunctions(node) {
    const visit = (n) => {
      if (ts.isFunctionDeclaration(n) && n.name) {
        this.localFns.set(n.name.text, n);
      } else if (ts.isMethodDeclaration(n) && n.name && ts.isIdentifier(n.name)) {
        this.localFns.set(n.name.text, n);
      } else if (ts.isVariableDeclaration(n) && n.name && ts.isIdentifier(n.name)
                 && n.initializer && isFunctionLike(n.initializer)) {
        this.localFns.set(n.name.text, n.initializer);
      }
      ts.forEachChild(n, visit);
    };
    visit(node);
  }

  /**
   * Boolean-ish sub-expressions of same-file helpers called in the guards.
   * The Python front end resolves two levels; this resolves one, and the
   * difference is declared in the module header.
   */
  helperExprs() {
    const out = [];
    for (const g of this.guards) {
      const node = g.node;
      if (!node) continue;
      const seen = new Set();
      const visit = (n) => {
        if (ts.isCallExpression(n)) {
          const name = calleeName(n.expression);
          const leaf = name ? name.split(".").pop() : null;
          if (leaf && this.localFns.has(leaf) && !seen.has(leaf)) {
            seen.add(leaf);
            const fn = this.localFns.get(leaf);
            const grab = (m) => {
              if (ts.isBinaryExpression(m) || ts.isCallExpression(m)) {
                const py = toPy(m);
                if (py) out.push({ py, via: leaf });
              }
              ts.forEachChild(m, grab);
            };
            if (fn.body) grab(fn.body);
          }
        }
        ts.forEachChild(n, visit);
      };
      visit(node);
    }
    return out;
  }

  /** Calls, assignment targets and object keys anywhere in the current block. */
  blockTrace() {
    const calls = [];
    const targets = [];
    const keys = [];
    const stmts = this.blockStack.length
      ? this.blockStack[this.blockStack.length - 1] : [];
    const visit = (n) => {
      if (ts.isCallExpression(n)) {
        const name = calleeName(n.expression);
        if (name) calls.push(name);
      } else if (ts.isBinaryExpression(n)
                 && n.operatorToken.kind === ts.SyntaxKind.EqualsToken) {
        const t = targetName(n.left);
        if (t) targets.push(t[0]);
      } else if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name)) {
        targets.push(n.name.text);
      } else if (ts.isPropertyAssignment(n)) {
        if (ts.isIdentifier(n.name) || ts.isStringLiteralLike(n.name)) {
          keys.push(n.name.text);
        }
      }
      ts.forEachChild(n, visit);
    };
    for (const s of stmts) visit(s);
    return { calls, targets, keys };
  }

  /** Container names on the right of a membership test in a positive guard. */
  membershipContainers() {
    const out = [];
    for (const g of this.guards) {
      if (!g.node) continue;
      if (g.py && g.py.startsWith("not (")) continue;
      const visit = (n) => {
        if (ts.isCallExpression(n) && ts.isPropertyAccessExpression(n.expression)
            && MEMBERSHIP.has(n.expression.name.text)) {
          const base = n.expression.expression;
          if (ts.isIdentifier(base)) out.push(base.text);
          else if (ts.isPropertyAccessExpression(base)) out.push(base.name.text);
        }
        if (ts.isBinaryExpression(n)
            && n.operatorToken.kind === ts.SyntaxKind.InKeyword) {
          const r = n.right;
          if (ts.isIdentifier(r)) out.push(r.text);
          else if (ts.isPropertyAccessExpression(r)) out.push(r.name.text);
        }
        ts.forEachChild(n, visit);
      };
      visit(g.node);
    }
    return out;
  }

  emit(fields) {
    const trace = this.blockTrace();
    this.out.push({
      subject: this.subject,
      module: this.module,
      function: this.fnStack[this.fnStack.length - 1],
      from_handler: this.inHandler > 0,
      guards_src: this.guards.map((g) => g.src),
      guards_py: this.guards.map((g) => g.py),
      guard_lines: this.guards.map((g) => g.line),
      helper_exprs: this.helperExprs(),
      params: Array.from(this.paramStack[this.paramStack.length - 1]),
      from_call: Array.from(this.fromCallStack[this.fromCallStack.length - 1]),
      block_calls: trace.calls,
      block_targets: trace.targets,
      block_keys: trace.keys,
      ...fields,
    });
  }

  consider(name, kind, valueNode, line) {
    if (!this.guards.length) return;      // unguarded: an initialiser
    const py = toPy(valueNode);
    this.emit({
      line,
      target: name,
      kind,
      shape: "benign-write",
      written_py: py,
      written_src: this.src(valueNode).slice(0, 80),
    });
  }

  expandObjectLiteral(valueNode, line) {
    if (!valueNode || !ts.isObjectLiteralExpression(valueNode)) return;
    for (const prop of valueNode.properties) {
      if (!ts.isPropertyAssignment(prop)) continue;
      const key = prop.name;
      if (!(ts.isIdentifier(key) || ts.isStringLiteralLike(key))) continue;
      this.consider(key.text, "dict-key", prop.initializer, this.line(prop));
    }
  }

  // -- shape 2: narrowing a collection of detections ------------------------
  scanNarrowing(node) {
    if (!this.guards.length) return;
    if (ts.isExpressionStatement(node) && ts.isBinaryExpression(node.expression)
        && node.expression.operatorToken.kind === ts.SyntaxKind.EqualsToken) {
      const t = targetName(node.expression.left);
      const rhs = node.expression.right;
      if (t && ts.isCallExpression(rhs) && ts.isPropertyAccessExpression(rhs.expression)) {
        const method = rhs.expression.name.text;
        const base = calleeName(rhs.expression.expression) || "";
        if (method === "filter" && base.split(".").pop() === t[0]) {
          this.emit({
            line: this.line(node), target: t[0], kind: "filter", shape: "narrowing",
            collection: t[0], written_py: null,
            written_src: "rebound to a filtered subset of itself",
          });
          return;
        }
      }
      // xs.length = 0
      if (ts.isPropertyAccessExpression(node.expression.left)
          && node.expression.left.name.text === "length"
          && toPy(rhs) === "0") {
        const base = calleeName(node.expression.left.expression);
        if (base) {
          this.emit({
            line: this.line(node), target: base, kind: "mutation",
            shape: "narrowing", collection: base.split(".").pop(),
            written_py: null, written_src: "length = 0 empties a detection list",
          });
          return;
        }
      }
    }
    if (ts.isExpressionStatement(node) && ts.isCallExpression(node.expression)) {
      const callee = node.expression.expression;
      if (ts.isPropertyAccessExpression(callee)) {
        const method = callee.name.text;
        const base = calleeName(callee.expression);
        if (base && ["splice", "pop", "shift", "clear", "delete"].includes(method)) {
          this.emit({
            line: this.line(node), target: base, kind: "mutation",
            shape: "narrowing", collection: base.split(".").pop(),
            written_py: null, written_src: `${method}() removes a detection`,
          });
        }
      }
    }
    if (ts.isExpressionStatement(node)
        && ts.isDeleteExpression(node.expression)) {
      const t = targetName(node.expression.expression);
      if (t) {
        this.emit({
          line: this.line(node), target: t[0], kind: "mutation",
          shape: "narrowing", collection: t[0], written_py: null,
          written_src: "delete removes a detection",
        });
      }
    }
  }

  // -- shape 3: arithmetic that moves a score toward benign -----------------
  scanDiscount(node) {
    if (!this.guards.length) return;
    if (!ts.isExpressionStatement(node) || !ts.isBinaryExpression(node.expression)) return;
    const be = node.expression;
    const t = targetName(be.left);
    if (!t) return;
    const kind = be.operatorToken.kind;
    let down = kind === ts.SyntaxKind.MinusEqualsToken
      || kind === ts.SyntaxKind.SlashEqualsToken;
    if (kind === ts.SyntaxKind.AsteriskEqualsToken
        && ts.isNumericLiteral(be.right) && Number(be.right.text) < 1) down = true;
    if (down) {
      this.emit({
        line: this.line(node), target: t[0], kind: "augassign", shape: "discount",
        written_py: null,
        written_src: `discounted by ${this.src(be.right).slice(0, 40)}`,
      });
      return;
    }
    if (kind !== ts.SyntaxKind.EqualsToken) return;
    const rhs = be.right;
    // score = Math.min(score, cap)
    if (ts.isCallExpression(rhs) && (calleeName(rhs.expression) || "").endsWith("min")
        && this.src(rhs).includes(t[0])) {
      this.emit({
        line: this.line(node), target: t[0], kind: "clamp", shape: "discount",
        written_py: null, written_src: "clamped down by min()",
      });
      return;
    }
    if (ts.isBinaryExpression(rhs) && this.src(rhs).includes(t[0])) {
      const op = rhs.operatorToken.kind;
      let isDown = op === ts.SyntaxKind.MinusToken || op === ts.SyntaxKind.SlashToken;
      if (op === ts.SyntaxKind.AsteriskToken) {
        for (const side of [rhs.left, rhs.right]) {
          if (ts.isNumericLiteral(side) && Number(side.text) < 1) isDown = true;
        }
      }
      if (isDown) {
        this.emit({
          line: this.line(node), target: t[0], kind: "assign", shape: "discount",
          written_py: null,
          written_src: `discounted: ${this.src(rhs).slice(0, 60)}`,
        });
      }
    }
  }

  // -- shape 4: a waiver that skips the check entirely ----------------------
  scanWaiverSkip(node) {
    if (!this.guards.length) return;
    const bareExit = ts.isContinueStatement(node) || ts.isBreakStatement(node)
      || (ts.isReturnStatement(node) && !node.expression);
    if (!bareExit) return;
    const containers = this.membershipContainers();
    if (!containers.length) return;
    this.emit({
      line: this.line(node), target: containers[0], kind: "skip",
      shape: "waiver-skip", membership_containers: containers,
      written_py: null, written_src: "check skipped for a listed subject",
    });
  }

  // -- statements -----------------------------------------------------------
  stmt(node) {
    if (isFunctionLike(node)) {
      this.enterFunction(node, functionName(node, "<anonymous>"));
      return;
    }
    if (ts.isClassDeclaration(node) || ts.isClassExpression(node)) {
      for (const m of node.members) this.stmt(m);
      return;
    }
    if (ts.isVariableStatement(node)) {
      for (const d of node.declarationList.declarations) {
        if (d.initializer && isFunctionLike(d.initializer)) {
          this.bindPattern(d.name);
          this.enterFunction(
            d.initializer,
            ts.isIdentifier(d.name) ? d.name.text : "<anonymous>");
          continue;
        }
        // A declaration is a FIRST binding: it establishes a value and cannot
        // weaken one. Same rule as the Python front end's `_weakens_existing`.
        this.bindPattern(d.name);
        if (d.initializer && ts.isCallExpression(d.initializer)
            && ts.isIdentifier(d.name)) {
          this.fromCallStack[this.fromCallStack.length - 1].add(d.name.text);
        }
        if (d.initializer) this.scanInner(d.initializer);
      }
      return;
    }
    if (ts.isIfStatement(node)) {
      const g = this.guardOf(node.expression);
      g.node = node.expression;
      this.under(g, node.thenStatement);
      if (node.elseStatement) {
        const n = this.negated(g);
        n.node = node.expression;
        this.under(n, node.elseStatement);
      }
      return;
    }
    if (ts.isForOfStatement(node) || ts.isForInStatement(node)) {
      if (node.initializer && ts.isVariableDeclarationList(node.initializer)) {
        for (const d of node.initializer.declarations) this.bindPattern(d.name);
      }
      const kw = ts.isForOfStatement(node) ? "in" : "in";
      const g = {
        src: `for ${this.src(node.initializer)} ${kw} ${this.src(node.expression)}`,
        py: null, line: this.line(node), node: node.expression,
      };
      this.under(g, node.statement);
      return;
    }
    if (ts.isForStatement(node)) {
      if (node.initializer && ts.isVariableDeclarationList(node.initializer)) {
        for (const d of node.initializer.declarations) this.bindPattern(d.name);
      }
      const g = { src: `for (${this.src(node.condition)})`, py: null,
        line: this.line(node), node: node.condition };
      this.under(g, node.statement);
      return;
    }
    if (ts.isWhileStatement(node) || ts.isDoStatement(node)) {
      const g = { src: `while ${this.src(node.expression)}`, py: null,
        line: this.line(node), node: node.expression };
      this.under(g, node.statement);
      return;
    }
    if (ts.isTryStatement(node)) {
      this.walkBlock(statementsOf(node.tryBlock));
      if (node.catchClause) {
        if (node.catchClause.variableDeclaration) {
          this.bindPattern(node.catchClause.variableDeclaration.name);
        }
        this.inHandler += 1;
        this.under({ src: "except Exception", py: null,
          line: this.line(node.catchClause), node: null },
        node.catchClause.block);
        this.inHandler -= 1;
      }
      if (node.finallyBlock) this.walkBlock(statementsOf(node.finallyBlock));
      return;
    }
    if (ts.isSwitchStatement(node)) {
      const subj = this.src(node.expression);
      for (const clause of node.caseBlock.clauses) {
        const label = ts.isCaseClause(clause) ? this.src(clause.expression) : "default";
        this.under({ src: `match ${subj} case ${label}`, py: null,
          line: this.line(clause), node: null }, { statements: clause.statements,
          kind: ts.SyntaxKind.Block });
      }
      return;
    }
    if (ts.isBlock(node)) {
      this.walkBlock(Array.from(node.statements));
      return;
    }
    if (ts.isReturnStatement(node) && node.expression) {
      this.consider(this.fnStack[this.fnStack.length - 1], "return",
        node.expression, this.line(node));
      this.expandObjectLiteral(node.expression, this.line(node));
      this.scanInner(node.expression);
      return;
    }
    if (ts.isExpressionStatement(node) && ts.isBinaryExpression(node.expression)
        && node.expression.operatorToken.kind === ts.SyntaxKind.EqualsToken) {
      const be = node.expression;
      const t = targetName(be.left);
      // An identifier target must already be bound; a property or element
      // target always qualifies, because the object came from elsewhere.
      if (t && (!ts.isIdentifier(be.left) || this.isBound(t[0]))) {
        this.consider(t[0], t[1], be.right, this.line(node));
      }
      this.expandObjectLiteral(be.right, this.line(node));
      this.scanNarrowing(node);
      this.scanDiscount(node);
      this.scanInner(be.right);
      if (ts.isIdentifier(be.left)) this.bind(be.left.text);
      return;
    }
    this.scanNarrowing(node);
    this.scanDiscount(node);
    this.scanWaiverSkip(node);
    this.scanInner(node);
  }

  /** Function bodies nested inside an expression still get walked. */
  scanInner(node) {
    if (!node) return;
    const visit = (n) => {
      if (isFunctionLike(n)) {
        this.enterFunction(n, "<anonymous>");
        return;              // enterFunction walks its body
      }
      ts.forEachChild(n, visit);
    };
    ts.forEachChild(node, visit);
  }

  enterFunction(node, name) {
    const params = new Set(paramNames(node));
    this.fnStack.push(name);
    this.boundScopes.push(new Set(params));
    this.paramStack.push(params);
    this.fromCallStack.push(new Set());
    const savedGuards = this.guards;
    this.guards = [];
    if (node.body) {
      if (ts.isBlock(node.body)) this.walkBlock(Array.from(node.body.statements));
      else this.scanInner(node.body);           // concise arrow body
    }
    this.guards = savedGuards;
    this.fromCallStack.pop();
    this.paramStack.pop();
    this.boundScopes.pop();
    this.fnStack.pop();
  }
}

// ───────────────────────────────────────────────────────────────────────────
// Entry point
// ───────────────────────────────────────────────────────────────────────────

function scanFile(subject, root, file) {
  const text = fs.readFileSync(file, "utf8");
  const rel = path.relative(root, file).split(path.sep).join("/");
  const kind = /\.(tsx|jsx)$/.test(file) ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const sf = ts.createSourceFile(rel, text, ts.ScriptTarget.Latest, true, kind);
  const w = new Walker(subject, rel, sf);
  w.collectLocalFunctions(sf);
  w.walkBlock(Array.from(sf.statements));
  return w.out;
}

// ───────────────────────────────────────────────────────────────────────────
// R14-c: does this subject declare a category it treats as unreleasable?
//
// The ONE place this file consults a lexicon, because the decision has to be
// made while the AST is in hand. Both patterns are read out of the shipped
// Python module by `ts_frontend.py` and passed in, never restated here.
// ───────────────────────────────────────────────────────────────────────────

function scanHardBlock(root, file, lexicon) {
  const decls = [];
  const vocab = new Set();
  if (!lexicon) return { decls, vocab };
  const declRe = new RegExp(lexicon.hard_block_declaration, "i");
  const tokenRe = new RegExp(lexicon.category_token);
  const text = fs.readFileSync(file, "utf8");
  const rel = path.relative(root, file).split(path.sep).join("/");

  text.split(/\r?\n/).forEach((line, i) => {
    const t = line.trimStart();
    if (t.startsWith("//") || t.startsWith("*") || t.startsWith("/*")) return;
    const m = declRe.exec(line);
    if (m) decls.push({ module: rel, line: i + 1, symbol: m[0] });
  });

  const kind = /\.(tsx|jsx)$/.test(file) ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const sf = ts.createSourceFile(rel, text, ts.ScriptTarget.Latest, true, kind);
  const collectStrings = (node) => {
    const visit = (n) => {
      if (ts.isStringLiteralLike(n)) {
        const tok = n.text.trim();
        if (tok && tok.length <= 48 && tokenRe.test(tok)) vocab.add(tok);
      }
      ts.forEachChild(n, visit);
    };
    visit(node);
  };
  const visit = (n) => {
    let named = null;
    let init = null;
    if (ts.isVariableDeclaration(n) && n.name && ts.isIdentifier(n.name)) {
      named = n.name.text;
      init = n.initializer;
    } else if (ts.isPropertyDeclaration(n) && n.name && ts.isIdentifier(n.name)) {
      named = n.name.text;
      init = n.initializer;
    } else if (ts.isEnumDeclaration(n) && n.name) {
      named = n.name.text;
      init = n;
    }
    if (named && declRe.test(named)) {
      vocab.add(named);
      if (init) collectStrings(init);
    }
    ts.forEachChild(n, visit);
  };
  visit(sf);
  return { decls, vocab };
}

function main() {
  const args = process.argv.slice(2);
  if (!args.length) {
    process.stderr.write("usage: node ts_propose.mjs <root> [--subject NAME] [--json OUT]\n");
    process.exit(2);
  }
  const root = path.resolve(args[0]);
  const subjIdx = args.indexOf("--subject");
  const subject = subjIdx >= 0 ? args[subjIdx + 1] : path.basename(root);
  const outIdx = args.indexOf("--json");
  const lexIdx = args.indexOf("--lexicon");
  const lexicon = lexIdx >= 0
    ? JSON.parse(fs.readFileSync(args[lexIdx + 1], "utf8")) : null;

  const candidates = [];
  const hardBlockDecls = [];
  const hardBlockVocab = new Set();
  const stats = { files: 0, parsed: 0, parse_errors: 0 };
  for (const file of iterSourceFiles(root)) {
    stats.files += 1;
    try {
      candidates.push(...scanFile(subject, root, file));
      const hb = scanHardBlock(root, file, lexicon);
      hardBlockDecls.push(...hb.decls);
      for (const v of hb.vocab) hardBlockVocab.add(v);
      stats.parsed += 1;
    } catch (err) {
      stats.parse_errors += 1;
      if (process.env.R14_TS_DEBUG) {
        process.stderr.write(`parse error ${file}: ${err.message}\n`);
      }
    }
  }
  candidates.sort((a, b) => (a.module.localeCompare(b.module)) || (a.line - b.line));
  const payload = {
    subject,
    root,
    stats,
    candidates,
    hard_block_decls: hardBlockDecls.slice(0, 200),
    hard_block_vocab: Array.from(hardBlockVocab).sort(),
  };
  const text = JSON.stringify(payload, null, 1);
  if (outIdx >= 0) fs.writeFileSync(args[outIdx + 1], text, "utf8");
  else process.stdout.write(text);
}

main();
