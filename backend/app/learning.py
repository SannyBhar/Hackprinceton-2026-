"""Transparent BKT and validated challenge recommendations; no device dependency."""
from dataclasses import asdict,dataclass
import hashlib
from .models import Puzzle,Cell,Instruction
from .compiler import plan

SKILLS=('sequencing','direction','distance','spatial')
OPERATIONAL={'INSTRUCTOR_STOP','BOUNDARY','TRACKING_LOST','TRACKING_UNCERTAIN','CONNECTION_LOST','ROBOT_FAULT','INTERRUPTED'}


@dataclass(frozen=True)
class BktParameters:
    prior:float=.2
    learn:float=.1
    guess:float=.2
    slip:float=.1


def update(probability,correct,p=BktParameters()):
    likelihood=(1-p.slip) if correct else p.slip
    other=p.guess if correct else (1-p.guess)
    posterior=probability*likelihood/(probability*likelihood+(1-probability)*other)
    return posterior+(1-posterior)*p.learn


def progress(attempts,student_id):
    params=BktParameters()
    scores={s:params.prior for s in SKILLS};counts={s:0 for s in SKILLS};trend=[];excluded=0
    for a in sorted(attempts,key=lambda a:a.get('startedAt',0)):
        if a.get('studentId')!=student_id:continue
        if a.get('stopReason')!='PROGRAM_COMPLETE' or not a.get('summary'):
            excluded+=1;continue
        evidence=dict(a.get('skillEvidence',{}))
        # Derive only task-level sequencing/spatial evidence if observed path agrees
        # with commanded plan. Otherwise actuator/tracking attribution is unknown.
        puzzle=a.get('puzzleSnapshot')
        if puzzle:
            result=plan(Puzzle.model_validate(puzzle),[Instruction.model_validate(i) for i in a['program']])
            observed=[Cell.model_validate(e['actual']) for e in a.get('events',[])]
            if observed!=result.plannedEntries:
                excluded+=1;continue
            for skill in ('sequencing','spatial'):evidence.setdefault(skill,bool(a['summary'].get('success')))
        for skill,correct in evidence.items():
            if skill in SKILLS:
                scores[skill]=update(scores[skill],correct,params);counts[skill]+=1
        trend.append({'attemptId':a['id'],'startedAt':a['startedAt'],'correct':a['summary'].get('correct',0),
                      'entries':a['summary'].get('entries',0),'mastery':dict(scores)})
    return {'studentId':student_id,'parameters':asdict(params),'skills':[
        {'skill':s,'estimate':scores[s],'evidenceCount':counts[s],'uncertain':counts[s]<3} for s in SKILLS],
        'trend':trend,'excludedOperationalOrUnattributed':excluded,
        'limitations':'Illustrative unvalidated model. Direction/distance require instructor evidence; estimates are not diagnoses.'}


def candidates(skill):
    # Small deterministic pool; bounded by existing compiler, no extra language constructs.
    programs={
        'distance':[['START',('FORWARD',n),'STOP'] for n in (2,3,4)],
        'direction':[['START',('FORWARD',1),'RIGHT',('FORWARD',n),'LEFT',('FORWARD',1),'STOP'] for n in (1,2,3)],
        'sequencing':[['START',('FORWARD',n),'RIGHT',('FORWARD',1),'RIGHT',('FORWARD',1),'STOP'] for n in (1,2,3)],
        'spatial':[['START',('FORWARD',n),('BACKWARD',1),'RIGHT',('FORWARD',2),'STOP'] for n in (2,3,4)],
    }
    out=[]
    for i,spec in enumerate(programs[skill]):
        instructions=[Instruction(op=x[0],steps=x[1]) if isinstance(x,tuple) else Instruction(op=x) for x in spec]
        blank=Puzzle(id=f'challenge-{skill}-{i}',name=f'{skill.title()} practice {i+1}',rows=7,cols=7,
            startCell=Cell(row=6,col=1),startHeading='N',goalCell=Cell(row=6,col=1),targetEntries=[])
        result=plan(blank,instructions)
        if not result.ok:continue
        puzzle=blank.model_copy(update={'targetEntries':result.plannedEntries,'goalCell':result.finalCell})
        Puzzle.model_validate(puzzle.model_dump())
        out.append({'puzzle':puzzle.model_dump(mode='json'),'referenceProgram':[x.model_dump(mode='json') for x in instructions],
                    'skill':skill,'turns':sum(x.op in ('LEFT','RIGHT') for x in instructions),
                    'translations':sum(x.steps or 0 for x in instructions)})
    return out


def recommend(report):
    weakest=min(report['skills'],key=lambda s:s['estimate'])
    pool=candidates(weakest['skill'])
    desired=2+round(weakest['estimate']*6)
    pool.sort(key=lambda c:(abs(c['translations']-desired),c['puzzle']['id']))
    for c in pool:
        c['explanation']=f"Practice {weakest['skill']}: estimate {weakest['estimate']:.2f}, {weakest['evidenceCount']} observations; instructor approval required."
        c['uncertain']=weakest['uncertain']
    return pool
