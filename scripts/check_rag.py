#!/usr/bin/env python3
"""Read-only RAG evaluation against the local embedding service, no robot dispatch."""
import argparse
import json
from pathlib import Path
import threading
import time

from roboinspect.chat import BielikPlanner
from roboinspect.operator_policy import help_topic
from roboinspect.rag import Retriever
from mlflow.tracking import MlflowClient

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--answers',action='store_true',help='Also evaluate real Bielik answers (slower)')
args=parser.parse_args()
rows=json.loads((ROOT/'config/rag-evaluation.json').read_text())
r=Retriever();results=[]
for row in rows:
    result=r.search(row['question'])
    ids=[s.id.rsplit('-',1)[0] for s in result.sources]
    correct=(row['expected'] in ids) if row['expected'] else not ids
    results.append({**row,'correct':correct,'retrieval':result.model_dump(mode='json')})
    print(row['question'],ids,'OK' if correct else 'MISS',flush=True)
answers=[]
if args.answers:
    planner=BielikPlanner()
    for row in rows[:3]+[rows[8],rows[10],rows[17]]:
        started=time.monotonic()
        answer,metrics=planner.explain(row['question'],help_topic(row['question']) or 'overview',threading.Event())
        answers.append({'question':row['question'],'answer':answer.model_dump(mode='json'),
                        'metrics':metrics,'seconds':time.monotonic()-started})
        print('ANSWER',row['question'],answer.message,flush=True)
metrics={'retrieval_accuracy_at_3':sum(x['correct'] for x in results)/len(results),
         'cases':len(results),'available_fraction':sum(x['retrieval']['available'] for x in results)/len(results),
         'mean_retrieval_seconds':sum(x['retrieval']['seconds'] for x in results)/len(results)}
report={'metrics':metrics,'results':results,'answers':answers}
client=MlflowClient(tracking_uri=f'sqlite:///{ROOT / "data/mlflow.db"}')
exp=client.get_experiment_by_name('roboinspect-rag-evaluation')
eid=exp.experiment_id if exp else client.create_experiment('roboinspect-rag-evaluation',artifact_location=(ROOT/'data/mlflow-artifacts').as_uri())
run=client.create_run(eid,tags={'purpose':'operator-retrieval-evaluation'})
for k,v in metrics.items():client.log_metric(run.info.run_id,k,v)
for k,v in {'model':result.model,'corpus_sha256':result.corpus_sha256,'weights_sha256':result.weights_sha256,'top_k':3,'min_score':.28}.items():client.log_param(run.info.run_id,k,v)
client.log_dict(run.info.run_id,report,'evaluation.json');client.set_terminated(run.info.run_id)
report['run_id']=run.info.run_id
output=ROOT/'docs/verification/rag-evaluation.json';output.parent.mkdir(parents=True,exist_ok=True)
output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(metrics), 'run',run.info.run_id)
raise SystemExit(0 if metrics['retrieval_accuracy_at_3'] >= .9 and metrics['available_fraction'] == 1 else 1)
