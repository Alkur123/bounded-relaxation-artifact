// Control for F1: the same function with the invariant satisfied.
//
// The verdict is now taken from the STRENGTH of the detection rather than from
// whether the repair happened to change the text, and the relaxation records
// that it fired. R14-a and R14-b are both met, so the certifier must report no
// violation here. A front end that convicts this control is not measuring the
// invariant, it is measuring the shape of the code.

interface Match { rule: string; start: number; end: number; score: number; }
interface Outcome { isInjection: boolean; text: string; }

declare const logger: {
  info(msg: string, ctx?: unknown): void;
  warning(msg: string): void;
};
declare function scanRules(text: string): Match[];
declare function omitInstance(text: string, m: Match): string;
declare const DETECTION_THRESHOLD: number;

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

  const strength = Math.max(...matches.map((m) => m.score));
  let isInjection = true;
  if (strength < DETECTION_THRESHOLD) {
    isInjection = false;
    logger.info("detection below threshold, releasing", { strength });
  }
  return { isInjection, text: modified };
}
