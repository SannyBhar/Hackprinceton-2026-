import { describe,it,expect } from 'vitest';
import { displayBlocks,unitInstruction,reviewBlocks } from './unitBlocks';

describe('one-cell student blocks',()=>{
  it('translates movement blocks to one-cell transport commands',()=>{
    expect(unitInstruction('FORWARD',0)).toEqual({op:'FORWARD',steps:1,cardId:0});
    expect(unitInstruction('BACKWARD',1)).toEqual({op:'BACKWARD',steps:1,cardId:1});
    expect(unitInstruction('RIGHT',2)).toEqual({op:'RIGHT',cardId:2});
  });
  it('expands compressed history while retaining the active command index',()=>{
    const blocks=displayBlocks([{op:'START'},{op:'BACKWARD',steps:3},{op:'RIGHT'},{op:'STOP'}]);
    expect(blocks.map(b=>b.instruction.op)).toEqual(['START','BACKWARD','BACKWARD','BACKWARD','RIGHT','STOP']);
    expect(blocks.slice(1,4).map(b=>b.sourceIndex)).toEqual([1,1,1]);
    expect(blocks.slice(1,4).every(b=>b.instruction.steps===1)).toBe(true);
  });
});

it('adds only missing bookends, preserves duplicate markers and requires review',()=>{
  const scan={unitBlocks:true,scanId:'s',source:'opencv',errors:[],needsReview:true,cards:
    [0,0,2,1,3].map((cardId,order)=>({order,cardId,op:({0:'FORWARD',1:'BACKWARD',2:'RIGHT',3:'LEFT'} as const)[cardId as 0|1|2|3],rawSteps:cardId<2?1:null,stepsConfidence:null,markerConfidence:1,cropDataUrl:null,issues:[]}))};
  const rows=reviewBlocks(scan);
  expect(rows.map(r=>r.op)).toEqual(['START','FORWARD','FORWARD','RIGHT','BACKWARD','LEFT','STOP']);
  expect(rows.filter(r=>!r.reviewed)).toHaveLength(5);
  expect(reviewBlocks({...scan,cards:[]})).toEqual([]);
});
