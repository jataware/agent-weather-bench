"""Construct bounded controls; these are not autonomous model attempts."""
from pathlib import Path
import json,shutil,hashlib
from .reference import build
from .checks import submission_checks
from .prepare import write_manifest

WRAPPER='''import argparse,json,shutil
from pathlib import Path
import monthly_reference as reference
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
    private=repo/'var/private/tasks/monthly-cycle-calibration';root=repo/'var/calibration/monthly-cycle-calibration';root.mkdir(parents=True,exist_ok=True)
    records={}
    for name,defect,cached in [('baseline',None,False),('month-only-year-leak','month-only-year-leak',False),('cached-inference',None,True)]:
        frozen=root/'controls'/name/'frozen';frozen.mkdir(parents=True,exist_ok=True)
        hc,fc,state=build(private/'agent-inputs',defect=defect)
        hc.to_netcdf(frozen/'hindcasts.nc');fc.to_netcdf(frozen/'forecast.nc');(frozen/'model.json').write_text(json.dumps(state,indent=2)+'\n')
        shutil.copyfile(repo/'weatherbench/task_tools/monthly_cycle/reference.py',frozen/'monthly_reference.py')
        (frozen/'workflow.py').write_text(f'DEFECT={defect!r}\nCACHED={cached!r}\n'+WRAPPER)
        shutil.copytree(private/'agent-inputs',frozen/'inputs',dirs_exist_ok=True)
        answer={'task':'monthly-cycle-calibration','training_years':[1993,2019],'verification_years':[2005,2019],'prediction_years':[2020,2023],'rainfall_units':'mm','msss':{str(s):float(hc.msss.sel(system=s)) for s in hc.system.values},'dynamical_hindcasts_used':False,'full_paper_reproduction':False,'limitations':['Constructed calibration control, not a model attempt','Retrospective final-vintage source data; 15 dependent outer years','Point forecasts and15 dependent outer years do not establish uncertainty or calibrated distributions','No dynamical hindcast or published-paper numerical replication claim']}
        (frozen/'answer.json').write_text(json.dumps(answer,indent=2)+'\n')
        report='Constructed '+name+' monthly forecasting control, not an autonomous agent submission. Kharin2017 motivates sharing fitted information across seasons using dynamical CanSIPS hindcasts and Gaussian smoothing. This task instead uses prior-calendar-month observed ERA5 SST to predict real monthly CHIRPS rainfall and a cyclic quadratic penalty on standardized slopes. All moments and cyclic slopes require complete training-year exclusions: retaining another month of a held year would leak through the cyclic coupling. January uses previous December SST, not current-month data. The constant comparator pools standardized monthly samples, not physical-unit slope data. Interpret outer monthly versus pooled MSSS using paired whole-year cases, not treating the36 month-region cases within a year as independent. Final-vintage ERA5 publication at the historical month start is an assumption and cannot establish strict real-time skill. Clipping negative predictions would change the public scientific contract; disclose them. Reference outcome gains or losses do not guarantee private future skill. Constructed controls have no human labels or calibration-accuracy claims.\n'
        import numpy as np
        yearly=hc.squared_error.sum('month').mean('target').values
        difference=yearly[:,3]-yearly[:,1]
        rng=np.random.default_rng(20261005);starts=rng.integers(0,len(difference),(10000,5))
        samples=np.concatenate([(starts+i)%len(difference) for i in range(3)],axis=1)[:,:len(difference)]
        lo,hi=np.quantile(difference[samples].mean(axis=1),[.025,.975])
        report+=('Actual outer MSSS by system: '+str(answer['msss'])+'. '
                 +'Minimum outer rainfall prediction '+str(float(hc.prediction.min()))+' mm; negative values are retained and imply an operational precipitation limitation. '
                 +'Minimum final forecast '+str(float(fc.prediction.min()))+' mm. '
                 +'Nested minus independent mean paired annual squared-error sum '+str(float(difference.mean()))+' mm2; positive means nested hurts. '
                 +'Descriptive circular3-year-block bootstrap95% interval '+str((float(lo),float(hi)))+' mm2,10000 replicates with seed20261005. '
                 +'This conditional interval reuses fixed outer predictions without refitting/selecting;15 annual cases provide weak serial-dependence evidence and the interval is not calibrated frequentist coverage. '
                 +'Monthly diagnostics matter because overall physical-error loss weights rainy months more. Final skill is unknown to this control.\n')
        (frozen/'report.txt').write_text(report);(frozen/'handoff.txt').write_text('Run workflow.py --inputs alternate-inputs --outputs writable-output. Prediction adds --model model.json and needs no targets. Constructed calibration control.\n')
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(2,2,figsize=(12,7));ax=axes[0,0]
        for system in hc.system.values:ax.plot(hc.month,hc.monthly_msss.sel(system=system),label=str(system))
        ax.set(ylabel='MSSS',xlabel='target month',title='Outer verification2005–2019');ax.legend(fontsize=7)
        for region in fc.target.values:
            axes[0,1].plot(fc.month,fc.standardized_coefficient.sel(system='nested-cyclic',target=region),label=str(region))
            axes[1,0].plot(fc.month,fc.coefficient.sel(system='nested-cyclic',target=region),label=str(region))
            axes[1,1].plot(fc.month,fc.prediction.sel(system='nested-cyclic',target=region).mean('year'),label=str(region))
        axes[0,1].set(ylabel='dimensionless beta',xlabel='target month',title='Saved standardized cyclic slopes')
        axes[1,0].set(ylabel='mm/degree Celsius',xlabel='target month',title='Saved physical slopes')
        axes[1,1].set(ylabel='monthly rainfall mm',xlabel='target month',title='Forecast2020–2023 average; skill unseen')
        for ax in [axes[0,1],axes[1,0],axes[1,1]]:ax.legend(fontsize=7)
        fig.suptitle('Constructed monthly-cycle calibration control');fig.tight_layout();fig.savefig(frozen/'outlook.png');plt.close(fig)
        execution={'schema_version':1,'replay':{'argv':['python','workflow.py','--inputs','{input_dir}','--outputs','{output_dir}']},'predict':{'argv':['python','workflow.py','--model','{model_path}','--inputs','{input_dir}','--outputs','{output_dir}']},'model_path':'model.json','retained_files':['workflow.py','monthly_reference.py','model.json',*[str(p.relative_to(frozen)) for p in sorted((frozen/'inputs').rglob('*')) if p.is_file()]],'dependencies':['Python NumPy SciPy xarray matplotlib in pinned image']}
        (frozen/'execution.json').write_text(json.dumps(execution,indent=2)+'\n')
        sourceids=['chirps3','era5-sst','legacy-normalization','kharin2017','africas2s-source']
        inputs=[str(p.relative_to(frozen)) for p in (frozen/'inputs').rglob('*') if p.is_file()]
        out=['hindcasts.nc','forecast.nc','model.json','answer.json','report.txt','outlook.png','handoff.txt','execution.json','workflow.py','monthly_reference.py']
        files=[{'path':n,'sha256':hashlib.sha256((frozen/n).read_bytes()).hexdigest(),'source_ids':sourceids if n in inputs else []} for n in inputs+out]
        provenance={'schema_version':1,'sources':[{'id':s,'product_version':'frozen internal development source snapshot','access':'supplied','request':{'url':s,'parameters':{}},'retrieved_at':None} for s in sourceids],'files':files,'transformations':[{'operation':'Constructed controller-reference monthly cyclic calibration control','inputs':inputs,'outputs':out,'parameters':{'units':'mm','training':[1993,2019],'outer':[2005,2019],'future':[2020,2023],'defect':defect,'cached_inference':cached,'method':'algorithm.md'}}]}
        (frozen/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
        records[name]={'constructed_not_agent_attempt':True,'path':str(frozen.relative_to(repo)),'scientific_checks':submission_checks(frozen,private),'expected':{'static':'pass' if defect is None else 'fail','counterfactual':'fail' if defect else 'pass','prediction':'fail' if cached else 'pass'},'human_label':None,'docker_execution':'pending'}
    (root/'controls-index.json').write_text(json.dumps(records,indent=2)+'\n');write_manifest(repo,private);return records

if __name__=='__main__':
    result=construct();print(json.dumps({k:{n:v['state'] for n,v in r['scientific_checks'].items()} for k,r in result.items()},indent=2))
