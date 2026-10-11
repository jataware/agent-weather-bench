"""Controller-only native-helper positive proof; never an agent substrate."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
IMAGE = "sha256:08dbb4fce25955523a4c3caa3e2efdfb75b960dae3d2b8f3b92746e7f19f7c49"
FOLDER = ROOT / "var/review/breadth-consolidation-preflight"
EVIDENCE = ROOT / "experiments/breadth-consolidation-preflight-2026-10-08.json"

CONTROL = r'''"""Trusted positive control; controller-only, never shown to models."""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from urllib.request import urlopen
import numpy as np
import xarray as xr
from africas2s import combine_terciles

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--inputs', required=True)
    parser.add_argument('--output', required=True)
    args=parser.parse_args()
    inputs=Path(args.inputs);output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    config=json.loads((inputs/'acquisition.json').read_text())
    params=json.loads((inputs/'instance.json').read_text())
    base=config['base_url'].rstrip('/')+'/'
    with urlopen(base+config['catalog_path'],timeout=30) as response:
        catalog=json.load(response)
    rows={row['path']:row for row in catalog['resources']}
    names=['observed-sst.nc','forecast-sst.nc','forecast-precip.nc']
    components=[]
    with tempfile.TemporaryDirectory() as temp:
        for name in names:
            row=rows[name]
            with urlopen(base+name,timeout=30) as response:content=response.read(row['bytes']+1)
            assert len(content)==row['bytes'] and hashlib.sha256(content).hexdigest()==row['sha256']
            path=Path(temp)/name;path.write_bytes(content)
            with xr.open_dataset(path,engine='h5netcdf') as dataset:
                fields=[dataset[c].astype('float64').load() for c in ['below','normal','above']]
            part=xr.concat(fields,dim=xr.IndexVariable('tercile',[0,1,2]))/100.0
            if components:
                assert part.lat.identical(components[0].lat) and part.lon.identical(components[0].lon)
            components.append(part.transpose('tercile','lat','lon'))
    stack=xr.concat(components,dim='component')
    complete=np.isfinite(stack).all('tercile')
    count=complete.sum('component')
    # Both delivered probability fields come directly from public native calls.
    objective=combine_terciles(components,missing='drop',renormalize=True)
    sensitivity=combine_terciles(components,weights=params['nominal_weights'],
                                missing='drop',renormalize=True)
    masked=stack.where(complete)
    maximum=masked.fillna(-np.inf).max('component')
    minimum=masked.fillna(np.inf).min('component')
    disagreement=((maximum-minimum)*100).where(count>0,0)
    result=xr.Dataset({'probability':objective.where(count>0,0),
        'nominal_weighted_probability':sensitivity.where(count>0,0),
        'available_components':count,'disagreement_pp':disagreement})
    result.to_zarr(output/'results.zarr',mode='w',zarr_format=3,consolidated=False)
    argv=['python','native_control.py','--inputs','{input_dir}','--output','{output_dir}']
    (output/'answer.json').write_text(json.dumps({'run':{'argv':argv},'claims':{}})+'\n')
    (output/'report.md').write_text('Trusted controller-only native-helper proof. Equal and explicit-weight combine_terciles returns supply delivered probability fields. Whole distributions determine support; unsupported cells use masked zero storage fills. No observed verification or operational consensus is claimed.\n')

if __name__=='__main__':main()
'''


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    from assessment.assess import assess
    from assessment.execute import Docker
    from assessment.spec import Template
    assert not EVIDENCE.exists(), "Preserve existing proof evidence"
    FOLDER.mkdir(parents=True, exist_ok=False)
    template=Template('seasonal-objective-consolidation')
    before=template.fingerprint()
    metadata={'started_at':now(),'model_calls':0,'image':IMAGE,'fingerprint_before':before,
              'template':'seasonal-objective-consolidation',
              'native_io_policy':'One reserved scientific worker; serial commands, no native I/O threads.',
              'guide':'systems/breadth-luna-accord-consolidation/API.md',
              'toy':'systems/breadth-luna-accord-consolidation/synthetic_combination.py',
              'private_control_exposed_to_agent':False}
    EVIDENCE.write_text(json.dumps(metadata,indent=2)+'\n')
    guide=(ROOT/metadata['guide']).parent
    command=['docker','run','--rm','--network','none','--memory','1536m','--cpus','2',
             '--mount',f'type=bind,src={guide},dst=/substrate,readonly',
             '--entrypoint','python',IMAGE,'/substrate/synthetic_combination.py']
    toy=subprocess.run(command,capture_output=True,text=True,timeout=120)
    (FOLDER/'toy.stdout').write_text(toy.stdout)
    (FOLDER/'toy.stderr').write_text(toy.stderr)
    metadata['toy']={'command':command,'exit_code':toy.returncode,
                     'result':json.loads(toy.stdout) if toy.returncode==0 else None}
    EVIDENCE.write_text(json.dumps(metadata,indent=2)+'\n')
    assert toy.returncode==0,toy.stderr
    params=template.instance('aso-2026--full-source-grid')
    template.hooks.stage_inputs(template.private,params,FOLDER/'inputs')
    submission=FOLDER/'submission';submission.mkdir()
    (submission/'native_control.py').write_text(CONTROL)
    executor=template.hooks.executor_factory(Docker(IMAGE,memory='1536m',cpus=2))
    record=executor.run(submission,FOLDER/'inputs',
        ['python','native_control.py','--inputs','{input_dir}','--output','{output_dir}'],
        FOLDER/'initial',seconds=120)
    (FOLDER/'initial-executor.json').write_text(json.dumps(record,indent=2,default=str)+'\n')
    assert record['exit_code']==0,record
    for name in ['results.zarr','answer.json','report.md']:
        source=Path(record['output'])/name
        shutil.copytree(source,submission/name) if source.is_dir() else shutil.copyfile(source,submission/name)
    result=assess(template,params,submission,executor,FOLDER/'assessment-work')
    result['acquisition']=template.hooks.acquisition_evidence(FOLDER/'assessment-work',FOLDER/'retained-acquisition')
    (FOLDER/'assessment.json').write_text(json.dumps(result,indent=2,default=str)+'\n')
    after=template.fingerprint()
    metadata.update(finished_at=now(),fingerprint_after=after,fingerprint_unchanged=before==after,
        computed_outcome=result['computed_outcome'],outcome=result['outcome'],
        checks={name:value['state'] for name,value in result['checks'].items()},
        acquisition=result['acquisition'],
        initial_acquisition=record['acquisition'],
        native_calls_per_command={'combine_terciles':2},
        native_call_count_method='Trusted control has two unconditional public calls; initial and replay exit codes recorded.',
        assessment=str((FOLDER/'assessment.json').relative_to(ROOT)),
        control_sha256=hashlib.sha256((submission/'native_control.py').read_bytes()).hexdigest(),
        guide_sha256=hashlib.sha256((guide/'API.md').read_bytes()).hexdigest(),
        toy_sha256=hashlib.sha256((guide/'synthetic_combination.py').read_bytes()).hexdigest())
    EVIDENCE.write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps(metadata,indent=2))
    assert before==after,'Task contract changed during proof'
    assert result['computed_outcome']=='pass',result['checks']


if __name__=='__main__':
    main()
