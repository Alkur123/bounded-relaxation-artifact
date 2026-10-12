// Control for F2: the same waiver, recorded.
//
// The bound obligation stays not-engaged, because a principal waiver has no
// evidence strength to consult. The audit obligation is now met in the same
// branch that performs the skip, which is the weakest sufficient form and the
// one bandit uses in the Python corpus.

interface Entity { text: string; score: number; label: string; }

declare const logger: { debug(msg: string, e?: unknown): void };
declare const CONFIDENCE_THRESHOLD: number;

export function filterEntities(entities: Entity[], ignoreList: string[]): Entity[] {
  const kept: Entity[] = [];
  for (const entity of entities) {
    if (ignoreList.includes(entity.text)) {
      logger.debug("entity suppressed by operator ignore list", entity);
      continue;
    }
    if (entity.score < CONFIDENCE_THRESHOLD) {
      logger.debug("dropping entity below confidence threshold", entity);
      continue;
    }
    kept.push(entity);
  }
  return kept;
}
