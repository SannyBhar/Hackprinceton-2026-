import type { Instruction, Op, ScanResult } from './types';

export const isTranslation = (op: Op | null) => op === 'FORWARD' || op === 'BACKWARD';

/** Counts remain in the transport/history contract; a student block always moves one cell. */
export function unitInstruction(op: Op, cardId: number | null = null): Instruction {
  return isTranslation(op) ? {op, steps: 1, cardId} : {op, cardId};
}

/** Expand existing compressed histories/reference solutions without changing their execution. */
export function displayBlocks(program: Instruction[]) {
  return program.flatMap((instruction, sourceIndex) =>
    Array.from({length: isTranslation(instruction.op) ? instruction.steps ?? 1 : 1}, () => ({
      instruction: unitInstruction(instruction.op, instruction.cardId), sourceIndex,
    })));
}

export type ReviewBlock = {op: Op | null; cardId: number | null; issues: string[]; reviewed: boolean};
export const reviewedBlock = (op: Op): ReviewBlock => ({op,cardId:null,issues:[],reviewed:true});

export function reviewBlocks(scan: ScanResult): ReviewBlock[] {
  const rows: ReviewBlock[] = scan.cards.flatMap(card => {
    const count = !scan.unitBlocks && isTranslation(card.op) ? card.rawSteps ?? 1 : 1;
    return Array.from({length:count},()=>({op:card.op,cardId:card.cardId,issues:card.issues,reviewed:false}));
  });
  if(rows.length) {
    if(rows[0].op!=='START')rows.unshift(reviewedBlock('START'));
    if(rows[rows.length-1].op!=='STOP')rows.push(reviewedBlock('STOP'));
  }
  return rows;
}
