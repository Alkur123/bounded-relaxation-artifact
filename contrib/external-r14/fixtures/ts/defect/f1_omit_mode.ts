// Fixture F1 — hand translation of the first upheld finding of the Python run:
// nemo-guardrails `library/injection_detection/actions.py:240`, class A.
//
// SYNTHETIC. This is a translation of a finding already adjudicated against the
// real Python source, written to test whether the TypeScript front end can see
// the same shape. It is a weaker validation than the Python front end's, whose
// two known positives were real code at two real commits, and the paper says so.
//
// The shape: the rules have already matched AND been logged, so a verdict
// exists. The stage that weakens it consults whether the REPAIR changed the
// text, not how strong the detection was.

interface Match { rule: string; start: number; end: number; }
interface Outcome { isInjection: boolean; text: string; }

declare const logger: {
  info(msg: string): void;
  warning(msg: string): void;
};
declare function scanRules(text: string): Match[];
declare function omitInstance(text: string, m: Match): string;

export function detectInjection(text: string): Outcome {
  const matches = scanRules(text);
  if (matches.length === 0) {
    return { isInjection: false, text };
  }
  logger.info(`Input matched on rule ${matches[0].rule}`);

  let modified = text;
  for (const m of matches) {
    try {
      modified = omitInstance(modified, m);
    } catch (err) {
      logger.warning(`could not decode instance for ${m.rule}`);
      continue;
    }
  }

  let isInjection = true;
  if (modified === text) {
    isInjection = false;
  }
  return { isInjection, text: modified };
}
