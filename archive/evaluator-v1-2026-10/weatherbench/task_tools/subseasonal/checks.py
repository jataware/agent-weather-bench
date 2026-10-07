"""Assess validity/metric honesty without requiring one preferred optimizer."""
import json
from pathlib import Path
from .metrics import score_file


def submission_checks(submission, private):
    submission,private=Path(submission),Path(private)
    result={}
    for split in ('development','final'):
        try:
            scores=score_file(submission/f'{split}-predictions.nc',private,split)
            result[f'{split}_prediction_schema']={'state':'pass','detail':'Exact public shape, calendar, grid, finite mm totals','evidence':[f'{split}-predictions.nc']}
        except (OSError,ValueError,KeyError,TypeError) as error:
            result[f'{split}_prediction_schema']={'state':'fail','detail':str(error),'evidence':[f'{split}-predictions.nc']}
    try:
        answer=json.loads((submission/'answer.json').read_text())
        fields=('task','method','training_rmse_mm','development_skill_claim','final_skill_claim')
        valid=all(x in answer for x in fields) and answer['task']=='subseasonal-optimization'
        result['answer_schema']={'state':'pass' if valid else 'fail','detail':'Required method and boundary fields','evidence':['answer.json']}
    except (OSError,ValueError,TypeError) as error:
        result['answer_schema']={'state':'fail','detail':str(error),'evidence':['answer.json']}
    return result
