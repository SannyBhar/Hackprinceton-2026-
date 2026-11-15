"""Create explicitly SYNTHETIC learners/attempts for an instructor demo. Never real history."""
import argparse
import time
from pathlib import Path
from app.sqlite_store import SQLiteStorage


def seed(data_dir):
    store=SQLiteStorage(Path(data_dir))
    for id,weak in [('synthetic-distance','distance'),('synthetic-direction','direction')]:
        store.put_record('students',id,{'id':id,'name':f'SYNTHETIC {weak} practice','synthetic':True})
        for index in range(5):
            attempt_id=f'{id}-{index}'
            store.save_attempt(attempt_id,{'id':attempt_id,'studentId':id,'source':'synthetic',
                'startedAt':int(time.time()*1000)+index,'endedAt':int(time.time()*1000)+index,
                'program':[],'events':[],'warnings':[],'stopReason':'PROGRAM_COMPLETE',
                'summary':{'correct':3,'entries':4,'success':False},
                'skillEvidence':{s:s!=weak for s in ('sequencing','direction','distance','spatial')}})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--data-dir',required=True)
    seed(parser.parse_args().data_dir)
