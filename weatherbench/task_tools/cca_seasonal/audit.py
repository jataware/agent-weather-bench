"""Construct bounded controls; these are not autonomous model attempts."""
from pathlib import Path
import json,shutil,hashlib
from .reference import build
from .checks import submission_checks
from .prepare import write_manifest

WRAPPER='''import argparse,json,shutil
from pathlib import Path
import cca_reference as reference
p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--outputs',type=Path,required=True);p.add_argument('--model',type=Path);args=p.parse_args();args.outputs.mkdir(parents=True,exist_ok=True)
if args.model:
    if CACHED:
        shutil.copyfile(Path(__file__).parent/'forecast.nc',args.outputs/'forecast.nc')
    else:
        state=json.loads(args.model.read_text());reference.from_state(state,args.inputs).to_netcdf(args.outputs/'forecast.nc')
else:
    hc,fc,state=reference.build(args.inputs,defect=DEFECT)
    hc.to_netcdf(args.outputs/'hindcasts.nc');fc.to_netcdf(args.outputs/'forecast.nc');(args.outputs/'model.json').write_text(json.dumps(state,indent=2)+'\\n')
'''

def construct(repo=None):
    repo=Path(repo) if repo is not None else Path(__file__).resolve().parents[3]
    private=repo/'var/private/tasks/cca-seasonal-reproduction';root=repo/'var/calibration/cca-seasonal-reproduction';root.mkdir(parents=True,exist_ok=True)
    records={}
    for name,defect,cached in [('baseline',None,False),('full-training-leak','full-training',False),('cached-inference',None,True)]:
        frozen=root/'controls'/name/'frozen';frozen.mkdir(parents=True,exist_ok=True)
        hc,fc,state=build(private/'agent-inputs',defect=defect)
        hc.to_netcdf(frozen/'hindcasts.nc');fc.to_netcdf(frozen/'forecast.nc');(frozen/'model.json').write_text(json.dumps(state,indent=2)+'\n')
        shutil.copyfile(repo/'weatherbench/task_tools/cca_seasonal/reference.py',frozen/'cca_reference.py')
        (frozen/'workflow.py').write_text(f'DEFECT={defect!r}\nCACHED={cached!r}\n'+WRAPPER)
        shutil.copytree(private/'agent-inputs',frozen/'inputs',dirs_exist_ok=True)
        answer={'task':'cca-seasonal-reproduction','training_years':[1993,2019],'verification_years':[2005,2019],'prediction_years':[2020,2023],'rainfall_units':'mm','rpss':{str(s):float(hc.rpss.sel(system=s)) for s in hc.system.values},'full_fit_is_cross_validated':False,'cpt_binary_executed':False,'limitations':['Constructed calibration control, not a model attempt','Retrospective final-vintage source data; 15 dependent outer years','Working Student-t uncertainty is not proven calibrated','No paper result or CPT binary numerical parity claim']}
        (frozen/'answer.json').write_text(json.dumps(answer,indent=2)+'\n')
        report='Constructed '+name+' scientific control. The pinned PyCPT code first gets deterministic CV predictions, then refits all years for probabilities with a +48-year date relabeling; probabilistic hindcast skill is not independent. This task adapts the component to antecedent SST and small East African rainfall fields, replacing source mode selection and squared-sum leverage with nested standardized MSE and rotation-invariant squared-norm leverage. A leave-one-out training residual variance and Student-t working distribution do not prove calibration. Source final-vintage observations prevent a strict real-time claim. Outer years are paired temporal cases; spatial cells are dependent, so cell count is not independent sample size. Full-fit diagnostic predictions overlap training and must not support a forecast-skill claim. The baseline is reference-generated for controller calibration and is not an autonomous solver result.\n'
        (frozen/'report.txt').write_text(report);(frozen/'handoff.txt').write_text('Run workflow.py --inputs alternate-inputs --outputs writable-output. Prediction adds --model model.json and needs no targets. Constructed calibration control.\n')
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,ax=plt.subplots(figsize=(7,3));ax.plot(hc.year,hc.prediction.sel(system='cca-nested').mean('target'),label='nested outer');ax.plot(hc.year,hc.full_fit_prediction.mean('target'),label='full-fit diagnostic');ax.set(ylabel='OND rainfall mm',xlabel='year',title='Constructed control: outer versus full-fit predictions');ax.legend();fig.tight_layout();fig.savefig(frozen/'outlook.png');plt.close(fig)
        execution={'schema_version':1,'replay':{'argv':['python','workflow.py','--inputs','{input_dir}','--outputs','{output_dir}']},'predict':{'argv':['python','workflow.py','--model','{model_path}','--inputs','{input_dir}','--outputs','{output_dir}']},'model_path':'model.json','retained_files':['workflow.py','cca_reference.py','model.json',*[str(p.relative_to(frozen)) for p in sorted((frozen/'inputs').rglob('*')) if p.is_file()]],'dependencies':['Python NumPy SciPy xarray matplotlib in pinned image']}
        (frozen/'execution.json').write_text(json.dumps(execution,indent=2)+'\n')
        sourceids=['chirps3','era5-sst','legacy-normalization','pycpt-source','africas2s-source']
        inputs=[str(p.relative_to(frozen)) for p in (frozen/'inputs').rglob('*') if p.is_file()]
        out=['hindcasts.nc','forecast.nc','model.json','answer.json','report.txt','outlook.png','handoff.txt','execution.json','workflow.py','cca_reference.py']
        files=[{'path':n,'sha256':hashlib.sha256((frozen/n).read_bytes()).hexdigest(),'source_ids':sourceids if n in inputs else []} for n in inputs+out]
        provenance={'schema_version':1,'sources':[{'id':s,'product_version':'frozen internal development source snapshot','access':'supplied','request':{'url':s,'parameters':{}},'retrieved_at':None} for s in sourceids],'files':files,'transformations':[{'operation':'Constructed controller-reference CCA calibration control','inputs':inputs,'outputs':out,'parameters':{'units':'mm','training':[1993,2019],'outer':[2005,2019],'future':[2020,2023],'defect':defect,'cached_inference':cached,'method':'algorithm.md'}}]}
        (frozen/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
        records[name]={'constructed_not_agent_attempt':True,'path':str(frozen.relative_to(repo)),'scientific_checks':submission_checks(frozen,private),'expected':{'static':'pass' if defect is None else 'fail','counterfactual':'fail' if defect else 'pass','prediction':'fail' if cached else 'pass'},'human_label':None,'docker_execution':'pending'}
    (root/'controls-index.json').write_text(json.dumps(records,indent=2)+'\n');write_manifest(repo,private);return records

if __name__=='__main__':
    result=construct();print(json.dumps({k:{n:v['state'] for n,v in r['scientific_checks'].items()} for k,r in result.items()},indent=2))
